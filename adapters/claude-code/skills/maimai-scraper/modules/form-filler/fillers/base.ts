/**
 * 填充器基类
 *
 * 所有控件填充器的基类，提供通用功能和浏览器执行器集成
 */

import type { ControlConfig, ControlType, FieldFillResult, IFiller } from '../types';
import type { MaimaiFormExecutor } from '../browser-executor';

/**
 * 填充器上下文
 */
export interface FillerContext {
  /** 浏览器执行器 */
  executor: MaimaiFormExecutor;
  /** 是否为 dry-run 模式 */
  dryRun?: boolean;
  /** 慢速模式 */
  slow?: boolean;
  /** 操作延迟（毫秒） */
  delay?: number;
}

/**
 * 填充器抽象基类
 *
 * 子类需要实现 fill 方法
 */
export abstract class BaseFiller implements IFiller {
  abstract readonly type: ControlType;

  /** 填充器上下文 */
  protected context?: FillerContext;

  /**
   * 设置上下文
   */
  setContext(context: FillerContext): void {
    this.context = context;
  }

  /**
   * 填充控件 - 子类实现
   */
  abstract fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult>;

  /**
   * 创建成功结果
   */
  protected createSuccessResult(field: string, value: string | string[], duration: number): FieldFillResult {
    return {
      field,
      success: true,
      value,
      duration,
    };
  }

  /**
   * 创建失败结果
   */
  protected createErrorResult(field: string, error: string, duration: number): FieldFillResult {
    return {
      field,
      success: false,
      error,
      duration,
    };
  }

  /**
   * 计时包装器
   */
  protected async withTiming<T>(
    fn: () => Promise<T>
  ): Promise<{ result: T; duration: number }> {
    const start = Date.now();
    const result = await fn();
    const duration = Date.now() - start;
    return { result, duration };
  }

  /**
   * 延迟（用于放慢操作）
   */
  protected async delay(ms?: number): Promise<void> {
    const delayMs = ms ?? this.context?.delay ?? 300;
    return new Promise((resolve) => setTimeout(resolve, delayMs));
  }

  /**
   * 获取执行器
   */
  protected getExecutor(): MaimaiFormExecutor | undefined {
    return this.context?.executor;
  }

  /**
   * 检查是否为 dry-run 模式
   */
  protected isDryRun(): boolean {
    return this.context?.dryRun ?? false;
  }

  /**
   * 标准化值为字符串数组
   */
  protected normalizeValue(value: string | string[]): string[] {
    if (Array.isArray(value)) {
      return value;
    }
    // 处理逗号分隔的多值
    if (typeof value === 'string' && value.includes(',')) {
      return value.split(',').map((v) => v.trim());
    }
    return [value];
  }

  /**
   * 标准化值为单个字符串
   */
  protected normalizeSingleValue(value: string | string[]): string {
    if (Array.isArray(value)) {
      return value.join(',');
    }
    return value;
  }

  /**
   * 解析范围值
   */
  protected parseRangeValue(value: string): { min: string; max: string } | null {
    // 支持 "25-35" 或 "25K-40K" 格式
    const match = value.match(/^(\d+(?:K|k)?)-(\d+(?:K|k)?)$/);
    if (!match) {
      return null;
    }
    return { min: match[1], max: match[2] };
  }
}

/**
 * 填充器注册表
 */
export class FillerRegistry {
  private fillers: Map<ControlType, IFiller> = new Map();

  /**
   * 注册填充器
   */
  register(filler: IFiller): void {
    this.fillers.set(filler.type, filler);
  }

  /**
   * 获取填充器
   */
  get(type: ControlType): IFiller | undefined {
    return this.fillers.get(type);
  }

  /**
   * 检查是否已注册
   */
  has(type: ControlType): boolean {
    return this.fillers.has(type);
  }

  /**
   * 获取所有已注册的类型
   */
  getRegisteredTypes(): ControlType[] {
    return Array.from(this.fillers.keys());
  }

  /**
   * 设置所有填充器的上下文
   */
  setContextForAll(context: FillerContext): void {
    for (const filler of this.fillers.values()) {
      if (filler instanceof BaseFiller) {
        filler.setContext(context);
      }
    }
  }
}

// 全局填充器注册表实例
export const fillerRegistry = new FillerRegistry();
