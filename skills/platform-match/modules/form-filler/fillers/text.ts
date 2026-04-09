/**
 * 文本输入填充器
 *
 * 处理普通文本输入框，如：关键词、职位名称、专业等
 *
 * 支持的控件：
 * - 关键词：主搜索框（需要精确定位，避免填充到导航栏搜索框）
 * - 专业：搜索输入 + 点选首位推荐 + 点空白关闭
 * - 家乡：搜索输入 + 点选首位推荐 + 点空白关闭
 */

import type { ControlConfig, FieldFillResult, TextOptions } from '../types';
import { BaseFiller } from './base';
import type { MaimaiFormExecutor } from '../browser-executor';

export class TextFiller extends BaseFiller {
  readonly type = 'text' as const;

  async fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult> {
    const startTime = Date.now();
    const textValue = this.normalizeSingleValue(value);
    const fieldName = config.name;

    if (!textValue) {
      return this.createErrorResult(fieldName, '值为空', 0);
    }

    // Dry-run 模式：只返回操作指令
    if (this.isDryRun()) {
      return this.createSuccessResult(fieldName, textValue, 0);
    }

    const executor = this.getExecutor();
    if (!executor) {
      return this.createErrorResult(fieldName, '浏览器执行器未初始化', Date.now() - startTime);
    }

    try {
      const options = config.options as TextOptions | undefined;

      // 判断是否需要展开面板
      if (options?.locateText && options.locateStrategy === 'text') {
        // 需要先点击展开面板
        const expanded = await executor.expandFilterPanel(options.locateText);
        if (!expanded) {
          return this.createErrorResult(fieldName, `无法展开面板: ${options.locateText}`, Date.now() - startTime);
        }
        await this.delay();
      }

      // 判断是否需要"输入 + 点选首位推荐"模式
      if (options?.needsSuggestSelect) {
        return await this.fillWithSuggestSelect(executor, fieldName, textValue, options, startTime);
      }

      // 普通填充模式
      return await this.fillNormal(executor, fieldName, textValue, options, startTime);
    } catch (error) {
      return this.createErrorResult(fieldName, String(error), Date.now() - startTime);
    }
  }

  /**
   * 普通填充模式（关键词等）
   */
  private async fillNormal(
    executor: NonNullable<ReturnType<typeof this.getExecutor>>,
    fieldName: string,
    textValue: string,
    options?: TextOptions,
    startTime?: number
  ): Promise<FieldFillResult> {
    const actualStartTime = startTime ?? Date.now();
    let fillResult;

    // 特殊处理关键词输入框 - 使用专用方法避免填充到导航栏
    if (fieldName === '关键词') {
      fillResult = await (executor as MaimaiFormExecutor).fillKeywordInput(textValue);
    } else if (options?.inputSelector) {
      // 通过占位符查找输入框
      const placeholder = this.extractPlaceholder(options.inputSelector);
      if (placeholder) {
        fillResult = await executor.fillByPlaceholder(placeholder, textValue);
      }
    }

    // 如果通过占位符填充失败，尝试通过 snapshot 查找
    if (!fillResult || !fillResult.success) {
      const snapshot = await executor.snapshot();

      // 查找包含控件名称或占位符的输入框
      const input = snapshot.elements.find((el) =>
        el.type === 'textbox' && (
          el.text?.includes(fieldName) ||
          (options?.inputSelector && el.text?.includes(options.inputSelector))
        )
      );

      if (input) {
        await executor.fill(input.ref, textValue);
        fillResult = { success: true, duration: Date.now() - actualStartTime };
      }
    }

    if (!fillResult || !fillResult.success) {
      return this.createErrorResult(
        fieldName,
        fillResult?.error ?? '找不到输入框',
        Date.now() - actualStartTime
      );
    }

    // 慢速模式延迟
    if (this.context?.slow) {
      await this.delay(this.context.delay ?? 500);
    }

    return this.createSuccessResult(fieldName, textValue, Date.now() - actualStartTime);
  }

  /**
   * 搜索建议选择模式（专业、家乡等）
   * 流程：展开面板 → 输入 → 等待推荐 → 点选首位 → 点空白关闭
   */
  private async fillWithSuggestSelect(
    executor: NonNullable<ReturnType<typeof this.getExecutor>>,
    fieldName: string,
    textValue: string,
    options: TextOptions,
    startTime: number
  ): Promise<FieldFillResult> {
    const maimaiExecutor = executor as MaimaiFormExecutor;
    const placeholder = options.inputSelector ? this.extractPlaceholder(options.inputSelector) : fieldName;

    // 使用 fillAndSelectFirstSuggest 方法
    const result = await maimaiExecutor.fillAndSelectFirstSuggest(placeholder ?? fieldName, textValue, {
      closeAfterSelect: options.closeByBlankClick ?? false,
    });

    if (!result.success) {
      return this.createErrorResult(fieldName, result.error ?? '点选推荐项失败', Date.now() - startTime);
    }

    // 慢速模式延迟
    if (this.context?.slow) {
      await this.delay(this.context.delay ?? 500);
    }

    return this.createSuccessResult(fieldName, textValue, Date.now() - startTime);
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
 * 文本输入操作指令
 */
export interface TextFillOperation {
  type: 'fill';
  field: string;
  value: string;
  selector?: string;
  placeholder?: string;
}
