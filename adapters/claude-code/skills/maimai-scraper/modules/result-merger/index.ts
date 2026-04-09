/**
 * 结果合并模块 - 主入口
 *
 * 合并多组搜索条件的结果，去重并生成统计报告
 */

import type { Candidate, FilterReason, ScrapeResult } from '../../scripts/types';
import type {
  CandidateWithSource,
  GroupExecutionDetail,
  GroupExecutionDetail as GroupExecutionDetailType,
  MergeOptions,
  MergeStatistics,
  MergedResult,
  SearchGroupResult,
  DeduplicationStrategy,
} from './types';
import { DEFAULT_MERGE_OPTIONS } from './types';

/**
 * 结果合并器
 */
export class ResultMerger {
  private options: MergeOptions;
  private groupResults: SearchGroupResult[] = [];
  private startTime: string;

  constructor(options?: Partial<MergeOptions>) {
    this.options = { ...DEFAULT_MERGE_OPTIONS, ...options };
    this.startTime = new Date().toISOString();
  }

  /**
   * 添加一组搜索结果
   */
  addGroupResult(result: SearchGroupResult): void {
    this.groupResults.push(result);
  }

  /**
   * 添加原始抓取结果
   */
  addScrapeResult(
    result: ScrapeResult,
    groupNumber: number,
    rowNumber: number,
    keywords?: string[],
    keywordMode?: 'AND' | 'OR'
  ): void {
    const groupResult: SearchGroupResult = {
      ...result,
      groupNumber,
      rowNumber,
      keywords,
      keywordMode,
      status: result.candidates.length > 0 ? 'completed' : 'no_results',
    };
    this.addGroupResult(groupResult);
  }

  /**
   * 执行合并
   */
  merge(): MergedResult {
    const mergedCandidates = this.mergeCandidates();
    const statistics = this.calculateStatistics(mergedCandidates);
    const groupDetails = this.generateGroupDetails();

    return {
      candidates: mergedCandidates,
      statistics,
      groupDetails,
      generatedAt: new Date().toISOString(),
    };
  }

  /**
   * 合并候选人并去重
   */
  private mergeCandidates(): CandidateWithSource[] {
    const candidateMap = new Map<string, CandidateWithSource>();
    let totalBeforeMerge = 0;

    for (const group of this.groupResults) {
      if (group.status === 'failed') continue;

      for (const candidate of group.candidates) {
        totalBeforeMerge++;

        const dedupKey = this.generateDedupKey(candidate);
        const existing = candidateMap.get(dedupKey);

        if (existing) {
          // 已存在，添加来源组
          if (!existing.sourceGroups.includes(group.groupNumber)) {
            existing.sourceGroups.push(group.groupNumber);
            existing.lastUpdatedAt = new Date().toISOString();
          }
        } else {
          // 新候选人
          const candidateWithSource: CandidateWithSource = {
            ...candidate,
            sourceGroups: [group.groupNumber],
            firstSeenAt: candidate.scrapedAt || new Date().toISOString(),
            lastUpdatedAt: new Date().toISOString(),
          };
          candidateMap.set(dedupKey, candidateWithSource);
        }
      }
    }

    let candidates = Array.from(candidateMap.values());

    // 按匹配度排序
    if (this.options.sortByMatchScore) {
      candidates.sort((a, b) => b.sourceGroups.length - a.sourceGroups.length);
    }

    // 限制数量
    if (this.options.maxCandidates > 0) {
      candidates = candidates.slice(0, this.options.maxCandidates);
    }

    return candidates;
  }

  /**
   * 生成去重键
   */
  private generateDedupKey(candidate: Candidate): string {
    switch (this.options.deduplicationStrategy) {
      case 'url':
        if (candidate.sourceUrl) {
          return candidate.sourceUrl;
        }
        // 降级到 name_company
        return this.generateNameCompanyKey(candidate);

      case 'name_company':
        return this.generateNameCompanyKey(candidate);

      case 'name_education':
        return this.generateNameEducationKey(candidate);

      case 'name_only':
        return candidate.name.toLowerCase().trim();

      default:
        return this.generateNameCompanyKey(candidate);
    }
  }

  private generateNameCompanyKey(candidate: Candidate): string {
    const currentCompany = this.getCurrentCompany(candidate);
    return `${candidate.name.toLowerCase().trim()}_${(currentCompany || '').toLowerCase().trim()}`;
  }

  private generateNameEducationKey(candidate: Candidate): string {
    const latestSchool = this.getLatestSchool(candidate);
    return `${candidate.name.toLowerCase().trim()}_${(latestSchool || '').toLowerCase().trim()}`;
  }

  /**
   * 获取当前公司
   */
  private getCurrentCompany(candidate: Candidate): string | undefined {
    if (candidate.workHistory && candidate.workHistory.length > 0) {
      return candidate.workHistory[0].company;
    }
    return undefined;
  }

  /**
   * 获取最近学校
   */
  private getLatestSchool(candidate: Candidate): string | undefined {
    if (candidate.educationHistory && candidate.educationHistory.length > 0) {
      return candidate.educationHistory[0].school;
    }
    return undefined;
  }

  /**
   * 计算合并统计
   */
  private calculateStatistics(mergedCandidates: CandidateWithSource[]): MergeStatistics {
    const totalBeforeMerge = this.groupResults.reduce(
      (sum, g) => sum + (g.status !== 'failed' ? g.candidates.length : 0),
      0
    );

    const totalAfterMerge = mergedCandidates.length;

    const completedGroups = this.groupResults.filter(
      (g) => g.status === 'completed' || g.status === 'no_results'
    ).length;

    const failedGroups = this.groupResults.filter((g) => g.status === 'failed').length;

    const noResultGroups = this.groupResults.filter((g) => g.status === 'no_results').length;

    const totalPassed = this.groupResults.reduce(
      (sum, g) => sum + g.candidates.length,
      0
    );

    const totalFiltered = this.groupResults.reduce(
      (sum, g) => sum + g.filteredCount,
      0
    );

    // 合并淘汰原因
    const filterReasonsMap = new Map<string, number>();
    for (const group of this.groupResults) {
      for (const reason of group.filterReasons) {
        const current = filterReasonsMap.get(reason.reason) || 0;
        filterReasonsMap.set(reason.reason, current + reason.count);
      }
    }

    const filterReasons: FilterReason[] = Array.from(filterReasonsMap.entries())
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count);

    // 计算总耗时
    const totalDuration = this.calculateTotalDuration();

    return {
      totalGroups: this.groupResults.length,
      completedGroups,
      failedGroups,
      noResultGroups,
      totalCandidatesBeforeMerge: totalBeforeMerge,
      totalCandidatesAfterMerge: totalAfterMerge,
      duplicateCount: totalBeforeMerge - totalAfterMerge,
      totalPassed,
      totalFiltered,
      filterReasons,
      totalDuration,
      startedAt: this.startTime,
      finishedAt: new Date().toISOString(),
    };
  }

  /**
   * 计算总耗时
   */
  private calculateTotalDuration(): string {
    // 解析 duration 字符串并累加
    let totalMs = 0;

    for (const group of this.groupResults) {
      const duration = group.duration;
      if (!duration) continue;

      // 支持格式: "5m30s", "10s", "1h20m", "15分32秒"
      const match = duration.match(/(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?|(?:(\d+)小时)?(?:(\d+)分)?(?:(\d+)秒)?/);
      if (match) {
        const hours = parseInt(match[1] || match[4] || '0', 10);
        const minutes = parseInt(match[2] || match[5] || '0', 10);
        const seconds = parseInt(match[3] || match[6] || '0', 10);
        totalMs += (hours * 3600 + minutes * 60 + seconds) * 1000;
      }
    }

    // 格式化输出
    const hours = Math.floor(totalMs / 3600000);
    const minutes = Math.floor((totalMs % 3600000) / 60000);
    const seconds = Math.floor((totalMs % 60000) / 1000);

    if (hours > 0) {
      return `${hours}h${minutes}m${seconds}s`;
    }
    if (minutes > 0) {
      return `${minutes}m${seconds}s`;
    }
    return `${seconds}s`;
  }

  /**
   * 生成条件组执行明细
   */
  private generateGroupDetails(): GroupExecutionDetail[] {
    return this.groupResults.map((group) => ({
      groupNumber: group.groupNumber,
      rowNumber: group.rowNumber,
      keywords: group.keywords?.join(',') || '',
      keywordMode: group.keywordMode || 'AND',
      conditionsSummary: this.formatConditionsSummary(group.searchConditions),
      filterRules: group.filterRules.join('; '),
      scrapedCount: group.totalCount,
      passedCount: group.candidates.length,
      status: group.status,
    }));
  }

  /**
   * 格式化搜索条件摘要
   */
  private formatConditionsSummary(conditions: Record<string, string>): string {
    const parts: string[] = [];

    if (conditions.city) parts.push(conditions.city);
    if (conditions.education) parts.push(conditions.education);
    if (conditions.workYears) parts.push(conditions.workYears);
    if (conditions.position) parts.push(conditions.position);

    return parts.slice(0, 3).join(', ') + (parts.length > 3 ? '...' : '');
  }

  /**
   * 打印合并报告摘要
   */
  printSummary(result: MergedResult): void {
    const { statistics, groupDetails } = result;

    console.log('\n=== 结果合并报告 ===');
    console.log(`\n[统计概览]`);
    console.log(`条件组数: ${statistics.totalGroups}`);
    console.log(`成功: ${statistics.completedGroups} | 失败: ${statistics.failedGroups} | 无结果: ${statistics.noResultGroups}`);
    console.log(`\n[候选人统计]`);
    console.log(`去重前: ${statistics.totalCandidatesBeforeMerge}`);
    console.log(`去重后: ${statistics.totalCandidatesAfterMerge}`);
    console.log(`重复数: ${statistics.duplicateCount}`);
    console.log(`\n[筛选统计]`);
    console.log(`通过: ${statistics.totalPassed}`);
    console.log(`淘汰: ${statistics.totalFiltered}`);
    console.log(`总耗时: ${statistics.totalDuration}`);

    if (statistics.filterReasons.length > 0) {
      console.log(`\n[淘汰原因]`);
      for (const reason of statistics.filterReasons) {
        console.log(`  - ${reason.reason}: ${reason.count}`);
      }
    }

    console.log(`\n[条件组执行明细]`);
    for (const detail of groupDetails) {
      console.log(`  组${detail.groupNumber}: ${detail.keywords}(${detail.keywordMode}) -> ${detail.passedCount}/${detail.scrapedCount} [${detail.status}]`);
    }
  }
}

// 导出类型
export * from './types';

// 默认合并器实例
export const defaultResultMerger = new ResultMerger();

/**
 * 快捷函数：合并多个抓取结果
 */
export function mergeResults(
  results: ScrapeResult[],
  options?: Partial<MergeOptions>
): MergedResult {
  const merger = new ResultMerger(options);

  results.forEach((result, index) => {
    merger.addScrapeResult(result, index + 1, index + 2);
  });

  return merger.merge();
}
