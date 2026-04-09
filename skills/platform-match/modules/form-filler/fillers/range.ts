/**
 * 范围滑块填充器
 *
 * 处理范围选择控件，如：年龄、期望月薪等
 *
 * 支持的控件：
 * - 年龄：双下拉范围选择（需要滚动查找目标值）
 * - 期望月薪：双下拉范围选择（需要滚动查找目标值）
 *
 * 重要：年龄/期望月薪的下拉选项较多，目标值可能需要滚动才能看到
 */

import type { ControlConfig, FieldFillResult, RangeOptions } from '../types';
import { BaseFiller } from './base';
import type { MaimaiFormExecutor } from '../browser-executor';

export class RangeFiller extends BaseFiller {
  readonly type = 'range' as const;

  async fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult> {
    const startTime = Date.now();
    const rangeValue = this.normalizeSingleValue(value);
    const fieldName = config.name;

    if (!rangeValue) {
      return this.createErrorResult(fieldName, '值为空', 0);
    }

    const options = config.options as RangeOptions | undefined;

    // 解析范围值
    const parsed = this.parseRangeValue(rangeValue, options?.format ?? 'number');

    if (!parsed) {
      return this.createErrorResult(fieldName, `无法解析范围值: ${rangeValue}`, 0);
    }

    // Dry-run 模式：只返回操作指令
    if (this.isDryRun()) {
      return this.createSuccessResult(fieldName, rangeValue, 0);
    }

    const executor = this.getExecutor();
    if (!executor) {
      return this.createErrorResult(fieldName, '浏览器执行器未初始化', Date.now() - startTime);
    }

    try {
      // 1. 展开范围面板
      if (options?.locateText && options.locateStrategy === 'text') {
        const expanded = await executor.expandFilterPanel(options.locateText);
        if (!expanded) {
          return this.createErrorResult(fieldName, `无法展开面板: ${options.locateText}`, Date.now() - startTime);
        }
        await this.delay();
      }

      // 2. 获取快照，找到下拉触发器（"不限"按钮或 combobox）
      const snapshot = await executor.snapshot();

      // 脉脉的年龄/薪资选择器实际上是 clickable 类型，text="不限"
      const unlimitedBtns = snapshot.elements.filter((el) => el.text === '不限');
      const comboboxes = snapshot.elements.filter((el) => el.type === 'combobox');

      // 优先使用"不限"按钮（脉脉实际 DOM 结构）
      const useUnlimitedBtns = unlimitedBtns.length >= 2;

      if (!useUnlimitedBtns && comboboxes.length < 2) {
        return this.createErrorResult(
          fieldName,
          `找不到范围选择下拉框`,
          Date.now() - startTime
        );
      }

      // 3. 选择最小值
      const minTargetText = this.formatTargetValue(parsed.min, options?.format, fieldName);
      console.log(`[RangeFiller] 选择最小值: ${minTargetText}`);

      if (useUnlimitedBtns) {
        // 点击第一个"不限"按钮
        await executor.click(unlimitedBtns[0].ref);
        await this.delay(300);

        // 使用滚动查找并选择选项
        const minResult = await (executor as MaimaiFormExecutor).selectDropdownOptionWithScroll(minTargetText, 5);
        if (!minResult.success) {
          console.log(`[RangeFiller] 最小值选择失败: ${minResult.error}`);
        }
      } else if (comboboxes[0]) {
        await executor.click(comboboxes[0].ref);
        await this.delay(200);
        await this.selectOptionWithScroll(executor, minTargetText);
      }

      await this.delay(300);

      // 4. 选择最大值
      const maxTargetText = this.formatTargetValue(parsed.max, options?.format, fieldName);
      console.log(`[RangeFiller] 选择最大值: ${maxTargetText}`);

      // 重新获取快照
      const maxSnapshot = await executor.snapshot();
      const updatedUnlimitedBtns = maxSnapshot.elements.filter((el) => el.text === '不限');

      if (updatedUnlimitedBtns.length >= 1) {
        // 点击"不限"按钮（最大值）
        await executor.click(updatedUnlimitedBtns[0].ref);
        await this.delay(300);

        // 使用滚动查找并选择选项
        const maxResult = await (executor as MaimaiFormExecutor).selectDropdownOptionWithScroll(maxTargetText, 5);
        if (!maxResult.success) {
          console.log(`[RangeFiller] 最大值选择失败: ${maxResult.error}`);
        }
      } else if (comboboxes[1]) {
        await executor.click(comboboxes[1].ref);
        await this.delay(200);
        await this.selectOptionWithScroll(executor, maxTargetText);
      }

      await this.delay(200);

      // 5. 点击确定按钮（如果有）
      const confirmSnapshot = await executor.snapshot();
      const confirmBtn = confirmSnapshot.elements.find((el) => el.text === '确定');
      if (confirmBtn) {
        await executor.click(confirmBtn.ref);
        await this.delay(200);
      }

      // 慢速模式延迟
      if (this.context?.slow) {
        await this.delay(this.context.delay ?? 500);
      }

      return this.createSuccessResult(fieldName, rangeValue, Date.now() - startTime);
    } catch (error) {
      return this.createErrorResult(fieldName, String(error), Date.now() - startTime);
    }
  }

  /**
   * 格式化目标值文本
   */
  private formatTargetValue(value: number, format?: 'number' | 'salary', fieldName?: string): string {
    if (format === 'salary') {
      return `${value}K`;
    }
    if (fieldName === '年龄') {
      return `${value}岁`;
    }
    return String(value);
  }

  /**
   * 使用滚动选择选项（备选方法）
   */
  private async selectOptionWithScroll(
    executor: NonNullable<ReturnType<typeof this.getExecutor>>,
    targetText: string
  ): Promise<boolean> {
    const snapshot = await executor.snapshot();
    const option = snapshot.elements.find((el) =>
      el.text === targetText || el.text?.includes(targetText.replace('岁', '').replace('K', ''))
    );

    if (option) {
      await executor.click(option.ref);
      return true;
    }

    // 如果直接找不到，使用滚动查找
    const result = await (executor as MaimaiFormExecutor).selectDropdownOptionWithScroll(targetText, 5);
    return result.success;
  }

  /**
   * 解析范围值
   *
   * 支持格式:
   * - "25-35" -> { min: 25, max: 35 }
   * - "25K-40K" -> { min: 25, max: 40 } (保留 K 单位)
   */
  private parseRangeValue(
    value: string,
    format: 'number' | 'salary'
  ): { min: number; max: number } | null {
    // 尝试匹配范围格式
    const rangeMatch = value.match(/(\d+(?:\.\d+)?)[Kk]?\s*[-~到]\s*(\d+(?:\.\d+)?)[Kk]?/);

    if (!rangeMatch) {
      return null;
    }

    let min = parseFloat(rangeMatch[1]);
    let max = parseFloat(rangeMatch[2]);

    return { min, max };
  }

  /**
   * 查找最接近的选项
   */
  private findClosestOption(
    elements: Array<{ ref: string; type: string; text?: string }>,
    targetValue: number,
    format?: 'number' | 'salary',
    isMax?: boolean
  ): { ref: string; text?: string } | null {
    // 找到所有可点击的选项
    const options = elements.filter((el) =>
      el.type === 'clickable' || el.type === 'option'
    );

    // 尝试精确匹配
    const exactMatch = options.find((el) => {
      const num = this.extractNumber(el.text ?? '', format);
      return num === targetValue;
    });
    if (exactMatch) return exactMatch;

    // 找最接近的选项
    let closest: { ref: string; text?: string; diff: number } | null = null;

    for (const opt of options) {
      const num = this.extractNumber(opt.text ?? '', format);
      if (num === null) continue;

      const diff = isMax
        ? Math.abs(num - targetValue) // 最大值找最接近的
        : Math.abs(num - targetValue); // 最小值找最接近的

      if (!closest || diff < closest.diff) {
        closest = { ...opt, diff };
      }
    }

    return closest;
  }

  /**
   * 从文本中提取数字
   */
  private extractNumber(text: string, format?: 'number' | 'salary'): number | null {
    // 匹配 "25K" 或 "25" 或 "25k-40k" 中的数字
    const match = text.match(/(\d+(?:\.\d+)?)/);
    if (!match) return null;

    const num = parseFloat(match[1]);

    // 如果是薪资格式且有 K，转换为实际数值
    if (format === 'salary' && text.toLowerCase().includes('k')) {
      return num; // 保持原值，因为页面显示就是 K
    }

    return num;
  }
}

/**
 * 预定义薪资范围（页面下拉选项）
 */
export const SALARY_OPTIONS = [
  '不限', '10K', '15K', '20K', '25K', '30K', '40K', '50K', '60K', '80K', '100K'
];

/**
 * 预定义年龄范围（页面下拉选项）
 */
export const AGE_OPTIONS = [
  '不限', '20', '22', '25', '28', '30', '32', '35', '38', '40', '45', '50'
];
