/**
 * 循环编排模块 - 类型定义
 *
 * 定义多条件搜索的编排流程和状态管理
 */

import type { DebugOptions, ParsedSearchRow } from '../form-filler/types';
import type { MergedResult, MergeOptions } from '../result-merger/types';
import type { ScrapeResult } from '../../scripts/types';

/**
 * 执行模式
 */
export type ExecutionMode =
  | 'full' // 完整模式：登录 → 循环抓取 → 导出
  | 'fill-only' // 仅填充：只填表单，不抓取
  | 'scrape-only' // 仅抓取：手动填好后执行抓取
  | 'debug'; // 调试模式：单步执行

/**
 * 工作流阶段
 */
export type WorkflowPhase =
  | 'init' // 初始化
  | 'login' // 登录验证
  | 'read-excel' // 读取 Excel
  | 'loop' // 循环处理
  | 'fill' // 填充表单
  | 'filter' // 设置筛选
  | 'scrape' // 抓取候选人
  | 'merge' // 合并结果
  | 'export' // 导出 Excel
  | 'complete' // 完成
  | 'error'; // 错误

/**
 * 单次迭代状态
 */
export interface IterationState {
  /** 当前行号 */
  rowNumber: number;

  /** 条件组编号 */
  groupNumber: number;

  /** 解析后的搜索条件 */
  searchRow: ParsedSearchRow;

  /** 当前阶段 */
  phase: WorkflowPhase;

  /** 抓取结果 */
  scrapeResult?: ScrapeResult;

  /** 错误信息 */
  error?: string;

  /** 开始时间 */
  startedAt: string;

  /** 结束时间 */
  finishedAt?: string;
}

/**
 * 工作流状态
 */
export interface WorkflowState {
  /** 当前阶段 */
  phase: WorkflowPhase;

  /** 执行模式 */
  mode: ExecutionMode;

  /** Excel 文件路径 */
  excelPath?: string;

  /** 总行数 */
  totalRows: number;

  /** 当前行索引（0-based） */
  currentRowIndex: number;

  /** 迭代状态历史 */
  iterations: IterationState[];

  /** 当前迭代 */
  currentIteration?: IterationState;

  /** 合并结果 */
  mergedResult?: MergedResult;

  /** 输出文件路径 */
  outputPath?: string;

  /** 开始时间 */
  startedAt: string;

  /** 错误信息 */
  error?: string;
}

/**
 * 工作流配置
 */
export interface WorkflowConfig {
  /** Excel 文件路径 */
  excelPath: string;

  /** 执行模式 */
  mode: ExecutionMode;

  /** 调试选项 */
  debug: DebugOptions;

  /** 合并选项 */
  merge: MergeOptions;

  /** 输出目录 */
  outputDir?: string;

  /** 失败重试次数 */
  retryCount: number;

  /** 遇到错误是否继续 */
  continueOnError: boolean;

  /** 每次迭代后的延迟（毫秒） */
  iterationDelay: number;
}

/**
 * 默认工作流配置
 */
export const DEFAULT_WORKFLOW_CONFIG: Partial<WorkflowConfig> = {
  mode: 'full',
  debug: {},
  merge: {},
  retryCount: 2,
  continueOnError: true,
  iterationDelay: 2000,
};

/**
 * 工作流事件
 */
export type WorkflowEvent =
  | { type: 'phase_change'; phase: WorkflowPhase; previousPhase: WorkflowPhase }
  | { type: 'iteration_start'; groupNumber: number; rowNumber: number }
  | { type: 'iteration_complete'; groupNumber: number; result: ScrapeResult }
  | { type: 'iteration_error'; groupNumber: number; error: string }
  | { type: 'workflow_complete'; result: MergedResult }
  | { type: 'workflow_error'; error: string; phase: WorkflowPhase };

/**
 * 工作流事件监听器
 */
export type WorkflowEventListener = (event: WorkflowEvent) => void | Promise<void>;

/**
 * 步骤执行器接口
 */
export interface IStepExecutor {
  /**
   * 执行步骤
   * @param state 当前迭代状态
   * @returns 是否成功
   */
  execute(state: IterationState): Promise<boolean>;

  /**
   * 步骤名称
   */
  readonly name: string;
}

/**
 * 工作流报告
 */
export interface WorkflowReport {
  /** 配置 */
  config: WorkflowConfig;

  /** 状态 */
  state: WorkflowState;

  /** 合并结果 */
  mergedResult?: MergedResult;

  /** 执行摘要 */
  summary: {
    totalIterations: number;
    successfulIterations: number;
    failedIterations: number;
    totalCandidates: number;
    uniqueCandidates: number;
    duration: string;
  };

  /** 生成时间 */
  generatedAt: string;
}
