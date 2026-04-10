/**
 * 下拉单选填充器
 *
 * 处理下拉单选控件，如：学历要求、性别、工作年限等
 *
 * 支持的控件：
 * - 关键词模式：AND/OR 切换
 * - 学历要求：下拉选择（需点击确定）+ 支持自定义范围 + 有二级选项
 * - 工作年限：下拉选择（需点击确定）
 * - 性别：下拉选择
 *
 * 重要：学历要求等控件有二级选项，必须点击到末级选项才算完成选择
 */

import type { ControlConfig, FieldFillResult, SelectOptions } from '../types';
import { BaseFiller } from './base';
import type { MaimaiFormExecutor } from '../browser-executor';

/** 预设学历选项（页面上的快捷选项） */
const PRESET_EDUCATION_OPTIONS = [
  '专科及以上',
  '本科及以上',
  '硕士及以上',
  '博士',
  '不限',
];

export class SelectFiller extends BaseFiller {
  readonly type = 'select' as const;

  async fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult> {
    const startTime = Date.now();
    const selectValue = this.normalizeSingleValue(value);
    const fieldName = config.name;

    if (!selectValue) {
      return this.createErrorResult(fieldName, '值为空', 0);
    }

    const options = config.options as SelectOptions | undefined;

    // Dry-run 模式：只返回操作指令
    if (this.isDryRun()) {
      return this.createSuccessResult(fieldName, selectValue, 0);
    }

    const executor = this.getExecutor();
    if (!executor) {
      return this.createErrorResult(fieldName, '浏览器执行器未初始化', Date.now() - startTime);
    }

    try {
      // 1. 展开下拉面板
      if (options?.locateText && options.locateStrategy === 'text') {
        const expanded = await executor.expandFilterPanel(options.locateText);
        if (!expanded) {
          return this.createErrorResult(fieldName, `无法展开下拉: ${options.locateText}`, Date.now() - startTime);
        }
        await this.delay();
      }

      // 2. 检查是否为学历要求且需要自定义模式
      if (fieldName === '学历要求' && !PRESET_EDUCATION_OPTIONS.includes(selectValue)) {
        // 使用自定义模式
        return await this.fillEducationCustom(executor, selectValue, startTime);
      }

      // 3. 标准选择模式
      const selectResult = await executor.selectOptionByText(selectValue);
      if (!selectResult.success) {
        // 尝试模糊匹配
        const snapshot = await executor.snapshot();
        const fuzzyMatch = snapshot.elements.find((el) =>
          el.type === 'clickable' &&
          el.text &&
          (el.text.includes(selectValue) || selectValue.includes(el.text))
        );

        if (fuzzyMatch) {
          await executor.click(fuzzyMatch.ref);
        } else {
          return this.createErrorResult(fieldName, selectResult.error ?? '选择失败', Date.now() - startTime);
        }
      }

      await this.delay(300);

      // 4. 检查是否有二级选项（学历要求等）
      if (fieldName === '学历要求') {
        const subResult = await this.checkAndSelectSubOption(executor, selectValue);
        if (subResult) {
          await this.delay(200);
        }
      }

      // 5. 如果需要点击确定
      if (options?.needsConfirm) {
        const confirmed = await executor.clickByText('确定');
        if (!confirmed) {
          console.log(`[SelectFiller] 未找到确定按钮，可能不需要确认`);
        }
        await this.delay();
      }

      // 慢速模式延迟
      if (this.context?.slow) {
        await this.delay(this.context.delay ?? 500);
      }

      return this.createSuccessResult(fieldName, selectValue, Date.now() - startTime);
    } catch (error) {
      return this.createErrorResult(fieldName, String(error), Date.now() - startTime);
    }
  }

  /**
   * 检查并选择二级选项
   *
   * 某些控件（如学历要求）点击父选项后会展开二级选项列表
   * 需要点击二级选项才算完成选择
   *
   * 学历二级选项示例：
   * - 本科及以上 → [本科, 不限, 只看统招本科]
   * - 硕士及以上 → [硕士, 不限]
   */
  private async checkAndSelectSubOption(
    executor: NonNullable<ReturnType<typeof this.getExecutor>>,
    parentValue: string
  ): Promise<boolean> {
    // 等待 DOM 更新
    await this.delay(300);

    const snapshot = await executor.snapshot();

    // 学历二级选项的关键词（用于识别真正的子选项）
    const subOptionKeywords = ['本科', '硕士', '博士', '专科', '不限', '统招'];

    // 过滤出可能的二级选项
    const subOptions = snapshot.elements.filter((el) => {
      if (el.type !== 'clickable' || !el.text) return false;

      const text = el.text.trim();

      // 排除父选项本身
      if (text === parentValue || text === parentValue.replace('及以上', '')) return false;

      // 排除按钮
      if (text.includes('确定') || text.includes('取消') || text.includes('自定义')) return false;

      // 排除其他父级选项
      if (text.includes('及以上') || text === '博士') return false;

      // 检查是否为有效的二级选项
      return subOptionKeywords.some(keyword => text.includes(keyword));
    });

    if (subOptions.length === 0) {
      return false;
    }

    console.log(`[SelectFiller] 发现 ${subOptions.length} 个二级选项: ${subOptions.map(e => e.text).join(', ')}`);

    // 查找与父选项匹配的二级选项
    // 例如 "本科及以上" -> 优先找 "本科"
    const targetText = parentValue.replace('及以上', '');
    let targetOption = subOptions.find((el) =>
      el.text === targetText || el.text?.includes(targetText)
    );

    // 如果没有精确匹配，选择第一个（通常是"不限"）
    if (!targetOption && subOptions.length > 0) {
      targetOption = subOptions[0];
    }

    if (targetOption) {
      console.log(`[SelectFiller] 选择二级选项: ${targetOption.text}`);
      await executor.click(targetOption.ref);
      return true;
    }

    return false;
  }

  /**
   * 使用自定义模式填充学历要求
   */
  private async fillEducationCustom(
    executor: NonNullable<ReturnType<typeof this.getExecutor>>,
    value: string,
    startTime: number
  ): Promise<FieldFillResult> {
    const fieldName = '学历要求';

    // 解析学历范围
    const { minEducation, maxEducation } = this.parseEducationRange(value);
    console.log(`[SelectFiller] 学历自定义模式: 最低="${minEducation}", 最高="${maxEducation}"`);

    try {
      // 1. 点击"自定义"按钮
      const customClicked = await executor.clickByText('自定义');
      if (!customClicked) {
        console.log(`[SelectFiller] 未找到"自定义"按钮，尝试直接选择`);
        return this.createErrorResult(fieldName, '未找到自定义按钮', Date.now() - startTime);
      }
      await this.delay(300);

      // 2. 选择最低学历（第一个下拉框）
      const snapshot1 = await executor.snapshot();
      const minCombobox = snapshot1.elements.find((el) =>
        el.type === 'combobox' || (el.type === 'clickable' && el.text?.includes('最低'))
      );

      if (minCombobox) {
        await executor.click(minCombobox.ref);
        await this.delay(200);

        // 选择最低学历选项
        const minSnapshot = await executor.snapshot();
        const minOption = minSnapshot.elements.find((el) =>
          el.type === 'clickable' && el.text?.includes(minEducation.replace('及以上', ''))
        );
        if (minOption) {
          await executor.click(minOption.ref);
          await this.delay(200);
        }
      }

      // 3. 选择最高学历（第二个下拉框）
      const snapshot2 = await executor.snapshot();
      const maxCombobox = snapshot2.elements.filter((el) =>
        el.type === 'combobox'
      )[1] || snapshot2.elements.find((el) =>
        el.type === 'clickable' && el.text?.includes('最高')
      );

      if (maxCombobox) {
        await executor.click(maxCombobox.ref);
        await this.delay(200);

        // 选择最高学历选项
        const maxSnapshot = await executor.snapshot();
        const maxOption = maxSnapshot.elements.find((el) =>
          el.type === 'clickable' && el.text?.includes(maxEducation.replace('及以上', ''))
        );
        if (maxOption) {
          await executor.click(maxOption.ref);
          await this.delay(200);
        }
      }

      // 4. 点击确定
      const confirmed = await executor.clickByText('确定');
      if (!confirmed) {
        console.log(`[SelectFiller] 未找到确定按钮`);
      }
      await this.delay();

      // 慢速模式延迟
      if (this.context?.slow) {
        await this.delay(this.context.delay ?? 500);
      }

      return this.createSuccessResult(fieldName, `${minEducation}-${maxEducation}`, Date.now() - startTime);
    } catch (error) {
      return this.createErrorResult(fieldName, String(error), Date.now() - startTime);
    }
  }

  /**
   * 解析学历范围
   */
  private parseEducationRange(value: string): { minEducation: string; maxEducation: string } {
    const rangeMatch = value.match(/^(.+?)[-~到](.+)$/);

    if (rangeMatch) {
      const min = this.normalizeEducationName(rangeMatch[1].trim());
      const max = this.normalizeEducationName(rangeMatch[2].trim());
      return { minEducation: min, maxEducation: max };
    }

    const normalized = this.normalizeEducationName(value);
    return { minEducation: normalized, maxEducation: '不限' };
  }

  /**
   * 标准化学历名称
   */
  private normalizeEducationName(name: string): string {
    const aliasMap: Record<string, string> = {
      '大专': '专科',
      '大本': '本科',
      '研究生': '硕士',
      '博士生': '博士',
    };

    return aliasMap[name] || name;
  }
}

/**
 * 学历值映射（基于实际页面分析）
 */
export const EDUCATION_VALUE_MAP: Record<string, string> = {
  '专科及以上': '1',
  '本科及以上': '2',
  '硕士及以上': '3',
  '博士': '4',
  '不限': '0',
};

/**
 * 性别值映射
 */
export const GENDER_VALUE_MAP: Record<string, string> = {
  '不限': '0',
  '男': '1',
  '女': '2',
};

/**
 * 工作年限值映射（基于实际页面分析）
 */
export const WORK_YEARS_VALUE_MAP: Record<string, string> = {
  '在校/应届': '0',
  '1年以内': '1',
  '1-3年': '2',
  '3-5年': '3',
  '5-10年': '4',
  '10年以上': '5',
  '不限': '6',
};

/**
 * 关键词模式值映射
 */
export const KEYWORD_MODE_VALUE_MAP: Record<string, string> = {
  'AND': 'and',
  'OR': 'or',
};
