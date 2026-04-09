/**
 * 日志工具模块
 *
 * 提供统一的日志记录功能，支持不同级别和格式化输出
 */

import type { WorkflowPhase } from './loop-orchestrator/types';

/**
 * 日志级别
 */
export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'silent';

/**
 * 日志配置
 */
export interface LoggerConfig {
  /** 日志级别 */
  level: LogLevel;

  /** 是否输出时间戳 */
  timestamp: boolean;

  /** 是否使用颜色 */
  colorize: boolean;

  /** 前缀 */
  prefix?: string;
}

/**
 * 默认配置
 */
const DEFAULT_CONFIG: LoggerConfig = {
  level: 'info',
  timestamp: true,
  colorize: true,
};

/**
 * ANSI 颜色代码
 */
const COLORS = {
  reset: '\x1b[0m',
  dim: '\x1b[2m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
};

/**
 * 日志级别优先级
 */
const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  silent: 999,
};

/**
 * 阶段图标映射
 */
const PHASE_ICONS: Record<WorkflowPhase | string, string> = {
  init: '🚀',
  login: '🔐',
  'read-excel': '📊',
  loop: '🔄',
  fill: '📝',
  filter: '🔍',
  scrape: '🕷️',
  merge: '🔗',
  export: '📁',
  complete: '✅',
  error: '❌',
};

/**
 * Logger 类
 */
export class Logger {
  private config: LoggerConfig;

  constructor(config?: Partial<LoggerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 设置日志级别
   */
  setLevel(level: LogLevel): void {
    this.config.level = level;
  }

  /**
   * 设置前缀
   */
  setPrefix(prefix: string): void {
    this.config.prefix = prefix;
  }

  /**
   * 检查是否应该输出
   */
  private shouldLog(level: LogLevel): boolean {
    return LEVEL_PRIORITY[level] >= LEVEL_PRIORITY[this.config.level];
  }

  /**
   * 格式化时间戳
   */
  private formatTimestamp(): string {
    if (!this.config.timestamp) return '';

    const now = new Date();
    const time = now.toTimeString().slice(0, 8);
    const ms = String(now.getMilliseconds()).padStart(3, '0');

    if (this.config.colorize) {
      return `${COLORS.dim}[${time}.${ms}]${COLORS.reset} `;
    }
    return `[${time}.${ms}] `;
  }

  /**
   * 格式化前缀
   */
  private formatPrefix(): string {
    if (!this.config.prefix) return '';

    if (this.config.colorize) {
      return `${COLORS.cyan}[${this.config.prefix}]${COLORS.reset} `;
    }
    return `[${this.config.prefix}] `;
  }

  /**
   * 格式化阶段
   */
  formatPhase(phase: WorkflowPhase | string): string {
    const icon = PHASE_ICONS[phase] || '📌';

    if (this.config.colorize) {
      return `${icon} ${COLORS.bright}${phase}${COLORS.reset}`;
    }
    return `${icon} ${phase}`;
  }

  /**
   * Debug 日志
   */
  debug(message: string, ...args: unknown[]): void {
    if (!this.shouldLog('debug')) return;

    const prefix = this.config.colorize
      ? `${COLORS.dim}[DEBUG]${COLORS.reset} `
      : '[DEBUG] ';

    console.log(
      this.formatTimestamp() + prefix + this.formatPrefix() + message,
      ...args
    );
  }

  /**
   * Info 日志
   */
  info(message: string, ...args: unknown[]): void {
    if (!this.shouldLog('info')) return;

    console.log(
      this.formatTimestamp() + this.formatPrefix() + message,
      ...args
    );
  }

  /**
   * 成功日志
   */
  success(message: string, ...args: unknown[]): void {
    if (!this.shouldLog('info')) return;

    const prefix = this.config.colorize
      ? `${COLORS.green}✓${COLORS.reset} `
      : '✓ ';

    console.log(
      this.formatTimestamp() + prefix + this.formatPrefix() + message,
      ...args
    );
  }

  /**
   * 警告日志
   */
  warn(message: string, ...args: unknown[]): void {
    if (!this.shouldLog('warn')) return;

    const prefix = this.config.colorize
      ? `${COLORS.yellow}⚠${COLORS.reset} `
      : '⚠ ';

    console.warn(
      this.formatTimestamp() + prefix + this.formatPrefix() + message,
      ...args
    );
  }

  /**
   * 错误日志
   */
  error(message: string, ...args: unknown[]): void {
    if (!this.shouldLog('error')) return;

    const prefix = this.config.colorize
      ? `${COLORS.red}✗${COLORS.reset} `
      : '✗ ';

    console.error(
      this.formatTimestamp() + prefix + this.formatPrefix() + message,
      ...args
    );
  }

  /**
   * 阶段日志
   */
  phase(phase: WorkflowPhase, message: string): void {
    if (!this.shouldLog('info')) return;

    const formattedPhase = this.formatPhase(phase);
    console.log(
      this.formatTimestamp() + formattedPhase + ' ' + message
    );
  }

  /**
   * 进度日志
   */
  progress(current: number, total: number, message: string): void {
    if (!this.shouldLog('info')) return;

    const percent = Math.round((current / total) * 100);
    const bar = this.config.colorize
      ? `${COLORS.green}${'█'.repeat(Math.floor(percent / 5))}${COLORS.reset}${'░'.repeat(20 - Math.floor(percent / 5))}`
      : `${'█'.repeat(Math.floor(percent / 5))}${'░'.repeat(20 - Math.floor(percent / 5))}`;

    process.stdout.write(
      `\r${this.formatTimestamp()}[${bar}] ${percent}% (${current}/${total}) ${message}`
    );

    if (current === total) {
      process.stdout.write('\n');
    }
  }

  /**
   * 分隔线
   */
  separator(char = '─', length = 50): void {
    if (!this.shouldLog('info')) return;

    const line = char.repeat(length);
    if (this.config.colorize) {
      console.log(`${COLORS.dim}${line}${COLORS.reset}`);
    } else {
      console.log(line);
    }
  }

  /**
   * 标题
   */
  title(text: string): void {
    if (!this.shouldLog('info')) return;

    this.separator();
    if (this.config.colorize) {
      console.log(`${COLORS.bright}${COLORS.cyan}${text}${COLORS.reset}`);
    } else {
      console.log(text);
    }
    this.separator();
  }

  /**
   * 表格输出
   */
  table(data: Record<string, unknown>[]): void {
    if (!this.shouldLog('info')) return;
    console.table(data);
  }

  /**
   * 空行
   */
  newline(count = 1): void {
    for (let i = 0; i < count; i++) {
      console.log();
    }
  }
}

// 默认 logger 实例
export const logger = new Logger();

/**
 * 创建带前缀的 logger
 */
export function createLogger(prefix: string, config?: Partial<LoggerConfig>): Logger {
  return new Logger({ ...config, prefix });
}
