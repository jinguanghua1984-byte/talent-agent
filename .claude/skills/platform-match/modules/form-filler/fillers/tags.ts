/**
 * 标签输入填充器
 *
 * 处理带智能提示的标签输入控件，如：就职公司、毕业学校、职位名称等
 *
 * 支持的控件：
 * - 就职公司：搜索 + 标签选择 + 复选框（正任职/曾任职）
 * - 毕业学校：搜索 + 标签选择（985/211等）
 * - 职位名称：搜索 + 标签选择
 */

import type { ControlConfig, FieldFillResult, TagsOptions } from '../types';
import { BaseFiller } from './base';

export class TagsFiller extends BaseFiller {
  readonly type = 'tags' as const;

  async fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult> {
    const startTime = Date.now();
    const values = this.normalizeValue(value);
    const fieldName = config.name;

    if (values.length === 0 || !values.every((v) => v)) {
      return this.createErrorResult(fieldName, '值为空', 0);
    }

    const options = config.options as TagsOptions | undefined;

    // Dry-run 模式：只返回操作指令
    if (this.isDryRun()) {
      return this.createSuccessResult(fieldName, values, 0);
    }

    const executor = this.getExecutor();
    if (!executor) {
      return this.createErrorResult(fieldName, '浏览器执行器未初始化', Date.now() - startTime);
    }

    try {
      // 1. 展开标签面板
      if (options?.locateText && options.locateStrategy === 'text') {
        const expanded = await executor.expandFilterPanel(options.locateText);
        if (!expanded) {
          return this.createErrorResult(fieldName, `无法展开面板: ${options.locateText}`, Date.now() - startTime);
        }
        await this.delay();
      }

      // 2. 处理复选框选项（如：正任职/曾任职）
      if (options?.checkboxOptions && options.checkboxOptions.length > 0) {
        // 默认都勾选，不做修改
      }

      // 3. 逐个添加标签
      for (const tagValue of values) {
        // 首先尝试点击热门标签
        if (options?.hotTags && options.hotTags.includes(tagValue)) {
          const tagResult = await executor.clickTag(tagValue);
          if (tagResult.success) {
            console.log(`[TagsFiller] 热门标签选中: ${tagValue}`);
            await this.delay(200);
            continue;
          }
        }

        // 尝试在搜索框中输入并点选首位推荐
        if (options?.inputSelector) {
          const placeholder = this.extractPlaceholder(options.inputSelector);
          if (placeholder) {
            const filled = await this.fillTagWithSuggest(executor, placeholder, tagValue);
            if (filled) {
              continue;
            }
          }
        }

        // 直接点击选项（备选方案）
        const clickResult = await executor.clickByText(tagValue);
        if (clickResult) {
          console.log(`[TagsFiller] 直接点击选中: ${tagValue}`);
          await this.delay(200);
        } else {
          console.log(`[TagsFiller] 警告: 未能添加标签 "${tagValue}"`);
        }
      }

      // 慢速模式延迟
      if (this.context?.slow) {
        await this.delay(this.context.delay ?? 500);
      }

      return this.createSuccessResult(fieldName, values, Date.now() - startTime);
    } catch (error) {
      return this.createErrorResult(fieldName, String(error), Date.now() - startTime);
    }
  }

  /**
   * 从选择器中提取占位符文本
   */
  private extractPlaceholder(selector: string): string | null {
    const match = selector.match(/placeholder\*?=["']([^"']+)["']/);
    return match ? match[1] : null;
  }

  /**
   * 通过搜索框输入并点选首位推荐项
   *
   * 用于毕业学校等需要搜索并选择推荐项的控件
   */
  private async fillTagWithSuggest(
    executor: NonNullable<ReturnType<typeof this.getExecutor>>,
    placeholder: string,
    tagValue: string
  ): Promise<boolean> {
    try {
      // 1. 查找搜索框
      const snapshot = await executor.snapshot();
      const searchInput = snapshot.elements.find((el) =>
        el.type === 'textbox' && el.text?.includes(placeholder)
      );

      if (!searchInput) {
        console.log(`[TagsFiller] 未找到搜索框: ${placeholder}`);
        return false;
      }

      // 2. 输入值
      await executor.fill(searchInput.ref, tagValue);
      await this.delay(500); // 等待推荐列表出现

      // 3. 点选首位推荐项
      const suggestSnapshot = await executor.snapshot();
      const firstSuggest = suggestSnapshot.elements.find((el) =>
        el.type === 'clickable' &&
        (el.text === tagValue || el.text?.includes(tagValue)) &&
        el.text !== placeholder
      );

      if (!firstSuggest) {
        console.log(`[TagsFiller] 未找到推荐项: ${tagValue}`);
        return false;
      }

      await executor.click(firstSuggest.ref);
      console.log(`[TagsFiller] 搜索并选中: ${tagValue}`);
      await this.delay(200);

      return true;
    } catch (error) {
      console.log(`[TagsFiller] fillTagWithSuggest 失败: ${error}`);
      return false;
    }
  }
}

/**
 * 热门公司标签
 */
export const HOT_COMPANY_TAGS = ['BAT', 'TMDJ', '一线互联网公司', '二线互联网公司'];

/**
 * 热门学校标签
 */
export const HOT_SCHOOL_TAGS = ['985', '211', 'QS排名Top500', '海外Top500'];

/**
 * 热门职位标签
 */
export const HOT_POSITION_TAGS = [
  '运营', '销售', '算法', '设计师',
  '产品经理', '前端开发', '后端开发', '数据分析', '人力资源'
];
