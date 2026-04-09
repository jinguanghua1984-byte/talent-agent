/**
 * 结果合并模块 - 类型定义
 *
 * 用于多组搜索条件的结果合并与去重
 */

import type { Candidate, FilterReason, ScrapeResult } from '../../scripts/types';

/**
 * 带来源标记的候选人
 */
export interface CandidateWithSource extends Candidate {
  /** 来源条件组编号（从1开始） */
  sourceGroups: number[];

  /** 首次发现时间 */
  firstSeenAt: string;

  /** 最后更新时间 */
  lastUpdatedAt: string;
}

/**
 * 单次搜索执行结果（扩展版）
 */
export interface SearchGroupResult extends ScrapeResult {
  /** 条件组编号 */
  groupNumber: number;

  /** Excel 行号 */
  rowNumber: number;

  /** 关键词 */
  keywords?: string[];

  /** 关键词模式 */
  keywordMode?: 'AND' | 'OR';

  /** 执行状态 */
  status: 'pending' | 'running' | 'completed' | 'failed' | 'no_results';

  /** 错误信息 */
  error?: string;
}

/**
 * 合并统计
 */
export interface MergeStatistics {
  /** 条件组数量 */
  totalGroups: number;

  /** 成功执行的组数 */
  completedGroups: number;

  /** 失败的组数 */
  failedGroups: number;

  /** 无结果的组数 */
  noResultGroups: number;

  /** 总抓取数量（去重前） */
  totalCandidatesBeforeMerge: number;

  /** 去重后数量 */
  totalCandidatesAfterMerge: number;

  /** 重复数量 */
  duplicateCount: number;

  /** 总通过筛选数量 */
  totalPassed: number;

  /** 总淘汰数量 */
  totalFiltered: number;

  /** 淘汰原因分布 */
  filterReasons: FilterReason[];

  /** 总耗时 */
  totalDuration: string;

  /** 开始时间 */
  startedAt: string;

  /** 结束时间 */
  finishedAt: string;
}

/**
 * 条件组执行明细
 */
export interface GroupExecutionDetail {
  /** 组编号 */
  groupNumber: number;

  /** 行号 */
  rowNumber: number;

  /** 关键词 */
  keywords: string;

  /** 关键词模式 */
  keywordMode: string;

  /** 主要搜索条件摘要 */
  conditionsSummary: string;

  /** 筛选规则 */
  filterRules: string;

  /** 抓取数量 */
  scrapedCount: number;

  /** 通过数量 */
  passedCount: number;

  /** 状态 */
  status: string;
}

/**
 * 合并结果
 */
export interface MergedResult {
  /** 合并后的候选人列表 */
  candidates: CandidateWithSource[];

  /** 统计信息 */
  statistics: MergeStatistics;

  /** 条件组执行明细 */
  groupDetails: GroupExecutionDetail[];

  /** 生成时间 */
  generatedAt: string;
}

/**
 * 去重键生成策略
 */
export type DeduplicationStrategy =
  | 'url' // 按 sourceUrl 去重（最准确）
  | 'name_company' // 按姓名+当前公司去重
  | 'name_education' // 按姓名+学校去重
  | 'name_only'; // 仅按姓名去重（可能误删）

/**
 * 合并选项
 */
export interface MergeOptions {
  /** 去重策略 */
  deduplicationStrategy: DeduplicationStrategy;

  /** 是否保留重复候选人（标记为重复而非删除） */
  keepDuplicates: boolean;

  /** 是否按匹配度排序（来源组越多越靠前） */
  sortByMatchScore: boolean;

  /** 最大保留数量（0表示不限制） */
  maxCandidates: number;
}

/**
 * 默认合并选项
 */
export const DEFAULT_MERGE_OPTIONS: MergeOptions = {
  deduplicationStrategy: 'url',
  keepDuplicates: false,
  sortByMatchScore: true,
  maxCandidates: 0,
};
