/**
 * 循环编排模块 - 主入口
 *
 * 协调多条件搜索的完整工作流
 */

import type { DebugOptions, ParsedSearchRow } from '../form-filler/types';
import { FormFiller, defaultFormFiller } from '../form-filler';
import { ResultMerger } from '../result-merger';
import type { MergedResult } from '../result-merger/types';
import type { ScrapeResult } from '../../scripts/types';
import type {
  ExecutionMode,
  IterationState,
  MergeOptions,
  WorkflowConfig,
  WorkflowEventListener,
  WorkflowEvent,
  WorkflowPhase,
  WorkflowReport,
  WorkflowState,
} from './types';
import { DEFAULT_WORKFLOW_CONFIG, WorkflowPhase as Phase } from './types';

/**
 * 工作流编排器
 *
 * 管理多条件搜索的完整生命周期
 */
export class LoopOrchestrator {
  private config: WorkflowConfig;
  private state: WorkflowState;
  private formFiller: FormFiller;
  private resultMerger: ResultMerger;
  private eventListeners: WorkflowEventListener[] = [];

  constructor(config: Partial<WorkflowConfig> & { excelPath: string }) {
    this.config = { ...DEFAULT_WORKFLOW_CONFIG, ...config } as WorkflowConfig;
    this.formFiller = new FormFiller({ debug: this.config.debug });
    this.resultMerger = new ResultMerger(this.config.merge);

    this.state = {
      phase: 'init',
      mode: this.config.mode,
      totalRows: 0,
      currentRowIndex: 0,
      iterations: [],
      startedAt: new Date().toISOString(),
    };
  }

  /**
   * 添加事件监听器
   */
  on(listener: WorkflowEventListener): void {
    this.eventListeners.push(listener);
  }

  /**
   * 移除事件监听器
   */
  off(listener: WorkflowEventListener): void {
    const index = this.eventListeners.indexOf(listener);
    if (index > -1) {
      this.eventListeners.splice(index, 1);
    }
  }

  /**
   * 发送事件
   */
  private emit(event: WorkflowEvent): void {
    for (const listener of this.eventListeners) {
      try {
        listener(event);
      } catch (error) {
        console.error('Event listener error:', error);
      }
    }
  }

  /**
   * 获取当前状态
   */
  getState(): WorkflowState {
    return { ...this.state };
  }

  /**
   * 执行完整工作流
   */
  async run(): Promise<WorkflowReport> {
    try {
      // Phase 1: 读取 Excel
      await this.transitionTo('read-excel');
      const searchRows = await this.readExcel();

      if (searchRows.length === 0) {
        throw new Error('Excel 文件没有数据');
      }

      this.state.totalRows = searchRows.length;

      // Phase 2: 登录验证（如果是 full 模式）
      if (this.config.mode === 'full') {
        await this.transitionTo('login');
        await this.verifyLogin();
      }

      // Phase 3: 循环处理每一行
      await this.transitionTo('loop');

      for (let i = 0; i < searchRows.length; i++) {
        this.state.currentRowIndex = i;
        const row = searchRows[i];

        // 创建迭代状态
        const iteration: IterationState = {
          rowNumber: row.rowNumber,
          groupNumber: i + 1,
          searchRow: row,
          phase: 'fill',
          startedAt: new Date().toISOString(),
        };

        this.state.currentIteration = iteration;
        this.emit({
          type: 'iteration_start',
          groupNumber: iteration.groupNumber,
          rowNumber: iteration.rowNumber,
        });

        try {
          // 执行单次迭代
          const result = await this.executeIteration(iteration);
          iteration.scrapeResult = result;
          iteration.phase = 'complete';
          iteration.finishedAt = new Date().toISOString();

          // 添加到合并器
          if (result) {
            this.resultMerger.addScrapeResult(
              result,
              iteration.groupNumber,
              iteration.rowNumber,
              row.keywords,
              row.keywordMode
            );
          }

          this.emit({
            type: 'iteration_complete',
            groupNumber: iteration.groupNumber,
            result: result!,
          });
        } catch (error) {
          iteration.phase = 'error';
          iteration.error = String(error);
          iteration.finishedAt = new Date().toISOString();

          this.emit({
            type: 'iteration_error',
            groupNumber: iteration.groupNumber,
            error: String(error),
          });

          if (!this.config.continueOnError) {
            throw error;
          }
        }

        this.state.iterations.push(iteration);

        // 迭代间延迟
        if (i < searchRows.length - 1 && this.config.iterationDelay > 0) {
          await this.delay(this.config.iterationDelay);
        }
      }

      // Phase 4: 合并结果
      await this.transitionTo('merge');
      this.state.mergedResult = this.resultMerger.merge();

      // Phase 5: 导出
      await this.transitionTo('export');
      await this.exportResults();

      // 完成
      await this.transitionTo('complete');
      this.emit({
        type: 'workflow_complete',
        result: this.state.mergedResult,
      });

      return this.generateReport();
    } catch (error) {
      this.state.phase = 'error';
      this.state.error = String(error);

      this.emit({
        type: 'workflow_error',
        error: String(error),
        phase: this.state.phase,
      });

      throw error;
    }
  }

  /**
   * 阶段转换
   */
  private async transitionTo(phase: WorkflowPhase): Promise<void> {
    const previousPhase = this.state.phase;
    this.state.phase = phase;
    this.emit({ type: 'phase_change', phase, previousPhase });
  }

  /**
   * 读取 Excel
   */
  private async readExcel(): Promise<ParsedSearchRow[]> {
    const { readSearchConditions } = await import('../form-filler/reader');
    return readSearchConditions(this.config.excelPath);
  }

  /**
   * 验证登录
   *
   * 注意：实际登录由 agent-browser 完成，这里只是状态管理
   */
  private async verifyLogin(): Promise<void> {
    // 登录验证逻辑由 SKILL.md 中定义的流程执行
    // 这里只是等待登录完成
    console.log('[登录] 请在浏览器中完成登录...');
  }

  /**
   * 执行单次迭代
   */
  private async executeIteration(iteration: IterationState): Promise<ScrapeResult | null> {
    const { searchRow } = iteration;

    // Step 1: 填充表单
    iteration.phase = 'fill';
    const fillReport = await this.formFiller.fillFromFile(
      this.config.excelPath,
      { row: searchRow.rowNumber, dryRun: this.config.debug.dryRun }
    );

    if (fillReport.failedRows > 0 && !this.config.continueOnError) {
      throw new Error(`表单填充失败: 第 ${searchRow.rowNumber} 行`);
    }

    // 如果是 fill-only 模式，到此结束
    if (this.config.mode === 'fill-only') {
      return null;
    }

    // Step 2: 设置筛选（如果有筛选规则）
    if (searchRow.filterRules.length > 0) {
      iteration.phase = 'filter';
      await this.setupFilters(searchRow.filterRules);
    }

    // Step 3: 抓取候选人
    iteration.phase = 'scrape';
    const scrapeResult = await this.scrapeCandidates(searchRow);

    return scrapeResult;
  }

  /**
   * 设置筛选规则
   *
   * 注意：实际筛选设置由 agent-browser 完成
   */
  private async setupFilters(rules: string[]): Promise<void> {
    console.log(`[筛选] 设置 ${rules.length} 条筛选规则`);
    // 实际筛选逻辑在 SKILL.md 中定义
  }

  /**
   * 抓取候选人
   *
   * 注意：实际抓取由 agent-browser + subagent 完成
   * 这里返回模拟结果，实际使用时替换
   */
  private async scrapeCandidates(searchRow: ParsedSearchRow): Promise<ScrapeResult> {
    // 模拟抓取结果
    // 实际实现由 scraper 模块或 SKILL.md 中定义的流程完成
    const result: ScrapeResult = {
      candidates: [],
      totalCount: 0,
      filteredCount: 0,
      filterReasons: [],
      searchConditions: searchRow.conditions as Record<string, string>,
      filterRules: searchRow.filterRules,
      scrapedAt: new Date().toISOString(),
      duration: '0s',
    };

    console.log(`[抓取] 搜索条件: ${JSON.stringify(searchRow.conditions)}`);
    console.log(`[抓取] 筛选规则: ${searchRow.filterRules.join('; ')}`);

    return result;
  }

  /**
   * 导出结果
   */
  private async exportResults(): Promise<void> {
    if (!this.state.mergedResult) return;

    const outputPath = this.generateOutputPath();
    this.state.outputPath = outputPath;

    console.log(`[导出] 输出文件: ${outputPath}`);
    // 实际导出逻辑由 exporter 模块完成
  }

  /**
   * 生成输出路径
   */
  private generateOutputPath(): string {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const outputDir = this.config.outputDir || 'data';
    return `${outputDir}/candidates_脉脉_${timestamp}.xlsx`;
  }

  /**
   * 生成报告
   */
  private generateReport(): WorkflowReport {
    const successfulIterations = this.state.iterations.filter(
      (i) => i.phase === 'complete'
    ).length;

    const failedIterations = this.state.iterations.filter(
      (i) => i.phase === 'error'
    ).length;

    const startTime = new Date(this.state.startedAt).getTime();
    const endTime = Date.now();
    const durationMs = endTime - startTime;
    const duration = this.formatDuration(durationMs);

    return {
      config: this.config,
      state: this.state,
      mergedResult: this.state.mergedResult,
      summary: {
        totalIterations: this.state.iterations.length,
        successfulIterations,
        failedIterations,
        totalCandidates: this.state.mergedResult?.statistics.totalCandidatesBeforeMerge || 0,
        uniqueCandidates: this.state.mergedResult?.statistics.totalCandidatesAfterMerge || 0,
        duration,
      },
      generatedAt: new Date().toISOString(),
    };
  }

  /**
   * 格式化持续时间
   */
  private formatDuration(ms: number): string {
    const hours = Math.floor(ms / 3600000);
    const minutes = Math.floor((ms % 3600000) / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);

    if (hours > 0) {
      return `${hours}h${minutes}m${seconds}s`;
    }
    if (minutes > 0) {
      return `${minutes}m${seconds}s`;
    }
    return `${seconds}s`;
  }

  /**
   * 延迟
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * 打印工作流报告
   */
  printReport(report: WorkflowReport): void {
    console.log('\n=== 工作流执行报告 ===');
    console.log(`\n[配置]`);
    console.log(`Excel: ${report.config.excelPath}`);
    console.log(`模式: ${report.config.mode}`);
    console.log(`\n[执行摘要]`);
    console.log(`总迭代: ${report.summary.totalIterations}`);
    console.log(`成功: ${report.summary.successfulIterations}`);
    console.log(`失败: ${report.summary.failedIterations}`);
    console.log(`总候选人: ${report.summary.totalCandidates}`);
    console.log(`唯一候选人: ${report.summary.uniqueCandidates}`);
    console.log(`耗时: ${report.summary.duration}`);

    if (report.mergedResult) {
      this.resultMerger.printSummary(report.mergedResult);
    }
  }
}

// 导出类型
export * from './types';

/**
 * 快捷函数：执行完整工作流
 */
export async function runWorkflow(
  excelPath: string,
  options?: Partial<WorkflowConfig>
): Promise<WorkflowReport> {
  const orchestrator = new LoopOrchestrator({ excelPath, ...options });
  return orchestrator.run();
}
