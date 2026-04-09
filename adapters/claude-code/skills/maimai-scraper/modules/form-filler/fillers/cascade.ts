/**
 * 级联选择填充器
 *
 * 处理级联选择控件，如：城市地区、行业方向等
 *
 * 支持的控件：
 * - 城市地区：搜索 + 级联选择 + 复选框（期望/现居）+ 支持多选
 * - 行业方向：搜索 + 级联选择（需点击确定）
 *
 * 重要特性：
 * - 城市地区支持多选，多个城市是独立的点选操作
 * - 省市级联需要点击到最末级
 */

import type { CascadeOptions, ControlConfig, FieldFillResult } from '../types';
import { BaseFiller } from './base';

export class CascadeFiller extends BaseFiller {
  readonly type = 'cascade' as const;

  async fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult> {
    const startTime = Date.now();
    const values = this.normalizeValue(value);
    const fieldName = config.name;

    if (values.length === 0 || !values[0]) {
      return this.createErrorResult(fieldName, '值为空', 0);
    }

    const options = config.options as CascadeOptions | undefined;

    // Dry-run 模式：只返回操作指令
    if (this.isDryRun()) {
      return this.createSuccessResult(fieldName, values, 0);
    }

    const executor = this.getExecutor();
    if (!executor) {
      return this.createErrorResult(fieldName, '浏览器执行器未初始化', Date.now() - startTime);
    }

    try {
      // 1. 展开级联面板
      if (options?.locateText && options.locateStrategy === 'text') {
        const expanded = await executor.expandFilterPanel(options.locateText);
        if (!expanded) {
          return this.createErrorResult(fieldName, `无法展开面板: ${options.locateText}`, Date.now() - startTime);
        }
        await this.delay();
      }

      // 2. 处理复选框选项（如：期望/现居）
      if (options?.checkboxOptions && options.checkboxOptions.length > 0) {
        // 默认都勾选，不做修改
      }

      // 3. 判断是否为多选模式（城市地区支持多选）
      const isMultiSelect = fieldName === '城市地区' && values.length > 1;

      if (isMultiSelect) {
        // 多选模式：每个城市独立点选
        console.log(`[CascadeFiller] 多选模式，共 ${values.length} 个值: ${values.join(', ')}`);

        for (let i = 0; i < values.length; i++) {
          const cityValue = values[i];
          if (!cityValue) continue;

          const selected = await this.selectSingleCascade(executor as NonNullable<typeof executor>, cityValue, options);

          if (!selected) {
            console.log(`[CascadeFiller] 警告: 未能选择城市 "${cityValue}"`);
          }

          // 城市之间增加延迟，确保 DOM 更新
          if (i < values.length - 1) {
            await this.delay(400);
          }
        }
      } else {
        // 单选模式
        const firstValue = values[0];
        if (firstValue) {
          await this.selectSingleCascade(executor as NonNullable<typeof executor>, firstValue, options);

          // 如果有二级选择（非城市地区）
          if (values.length > 1 && values[1] && fieldName !== '城市地区') {
            await this.delay(200);
            const secondValue = values[1];
            const clickResult = await executor.clickByText(secondValue);
            if (clickResult) {
              await this.delay();
            }
          }
        }
      }

      // 4. 如果需要点击确定
      if (options?.needsConfirm) {
        await this.delay(200);

        // 重新获取快照查找确定按钮
        const confirmSnapshot = await executor.snapshot();
        const confirmBtn = confirmSnapshot.elements.find((el) =>
          el.text === '确定' || el.text?.trim() === '确 定'
        );

        if (confirmBtn) {
          await executor.click(confirmBtn.ref);
          console.log(`[CascadeFiller] 已点击确定按钮`);
        } else {
          console.log(`[CascadeFiller] 未找到确定按钮，可能不需要确认`);
        }
        await this.delay();
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
   * 选择单个级联项
   *
   * 对于城市地区：
   * - 优先点击热门标签
   * - 如果没有热门标签，通过搜索框输入 + 点选首位匹配
   *
   * 对于行业方向：
   * - 可以搜索或直接点击一级行业
   * - 再点击二级行业
   */
  private async selectSingleCascade(
    executor: ReturnType<typeof this.getExecutor> & NonNullable<ReturnType<typeof this.getExecutor>>,
    value: string,
    options?: CascadeOptions
  ): Promise<boolean> {
    // 1. 首先尝试直接点击热门标签/选项
    const directClick = await executor.clickByText(value);
    if (directClick) {
      console.log(`[CascadeFiller] 直接点击选中: ${value}`);
      await this.delay(300);
      return true;
    }

    // 2. 如果直接点击失败，尝试搜索框输入 + 点选首位匹配
    if (options?.inputSelector) {
      const placeholder = this.extractPlaceholder(options.inputSelector);
      if (placeholder) {
        // 清空搜索框并输入新值
        const snapshot = await executor.snapshot();
        const searchInput = snapshot.elements.find((el) =>
          el.type === 'textbox' && el.text?.includes(placeholder)
        );

        if (searchInput) {
          // 清空并输入
          await executor.fill(searchInput.ref, '');
          await this.delay(100);
          await executor.fill(searchInput.ref, value);
          await this.delay(500); // 等待搜索结果

          // 点选首位匹配项
          const resultSnapshot = await executor.snapshot();
          const matchElement = resultSnapshot.elements.find((el) =>
            el.type === 'clickable' &&
            (el.text === value || el.text?.includes(value)) &&
            el.text !== placeholder
          );

          if (matchElement) {
            await executor.click(matchElement.ref);
            console.log(`[CascadeFiller] 搜索并选中: ${value}`);
            await this.delay(200);
            return true;
          }
        }
      }
    }

    // 3. 尝试点击包含该值的元素
    const snapshot = await executor.snapshot();
    const element = snapshot.elements.find((el) =>
      el.type === 'clickable' && el.text?.includes(value)
    );

    if (element) {
      await executor.click(element.ref);
      console.log(`[CascadeFiller] 模糊匹配选中: ${value}`);
      await this.delay(200);
      return true;
    }

    console.log(`[CascadeFiller] 未能选中: ${value}`);
    return false;
  }

  /**
   * 从选择器中提取占位符文本
   */
  private extractPlaceholder(selector: string): string | null {
    const match = selector.match(/placeholder\*?=["']([^"']+)["']/);
    return match ? match[1] : null;
  }
}

/**
 * 常见城市级联值
 *
 * 格式: [省份/城市]
 * 脉脉支持直接选择城市，不一定需要省份
 */
export const CITY_CASCADE_VALUES: Record<string, string[]> = {
  '北京': ['北京'],
  '上海': ['上海'],
  '广州': ['广州'],
  '深圳': ['深圳'],
  '杭州': ['杭州'],
  '南京': ['南京'],
  '苏州': ['苏州'],
  '成都': ['成都'],
  '武汉': ['武汉'],
  '西安': ['西安'],
  '重庆': ['重庆'],
  '天津': ['天津'],
};

/**
 * 行业方向级联值（基于实际页面分析）
 */
export const INDUSTRY_CASCADE_VALUES: Record<string, string[]> = {
  '互联网': ['IT/互联网/游戏'],
  '电商': ['IT/互联网/游戏', '电子商务'],
  '云计算': ['IT/互联网/游戏', '云计算/大数据/人工智能'],
  '金融': ['金融业'],
  '教育': ['教育/培训/科研'],
  '医疗': ['医疗/医药'],
  '制造业': ['制造业'],
  '汽车': ['汽车'],
  '房地产': ['房地产业/建筑业'],
};
