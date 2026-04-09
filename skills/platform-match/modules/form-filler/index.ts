/**
 * 表单填充模块 - 主入口
 *
 * 整合 Excel 读取、字段映射、控件填充的完整流程
 */

import type {
  DebugOptions,
  FillOperation,
  FillReport,
  FieldFillResult,
  ParsedSearchRow,
  RowFillResult,
} from './types';
import { fillerRegistry, type FillerContext } from './fillers/base';
import { TextFiller } from './fillers/text';
import { SelectFiller } from './fillers/select';
import { CascadeFiller } from './fillers/cascade';
import { TagsFiller } from './fillers/tags';
import { RangeFiller } from './fillers/range';
import { FieldMapper, defaultFieldMapper } from './mapper';
import { ExcelReader, defaultExcelReader } from './reader';
import { MaimaiFormExecutor, type BrowserExecutorConfig } from './browser-executor';

// 注册所有填充器
function registerFillers(): void {
  fillerRegistry.register(new TextFiller());
  fillerRegistry.register(new SelectFiller());
  fillerRegistry.register(new CascadeFiller());
  fillerRegistry.register(new TagsFiller());
  fillerRegistry.register(new RangeFiller());
}

// 模块加载时注册
registerFillers();

/**
 * 表单填充器类
 *
 * 完整的表单填充流程：读取 Excel -> 解析行 -> 生成操作 -> 执行填充
 */
export class FormFiller {
  private reader: ExcelReader;
  private mapper: FieldMapper;
  private debugOptions: DebugOptions;
  private executor?: MaimaiFormExecutor;

  constructor(options?: {
    reader?: ExcelReader;
    mapper?: FieldMapper;
    debug?: DebugOptions;
    browserConfig?: BrowserExecutorConfig;
  }) {
    this.reader = options?.reader ?? defaultExcelReader;
    this.mapper = options?.mapper ?? defaultFieldMapper;
    this.debugOptions = options?.debug ?? {};

    // 初始化浏览器执行器
    if (options?.browserConfig) {
      this.executor = new MaimaiFormExecutor(options.browserConfig);
    }
  }

  /**
   * 设置浏览器执行器
   */
  setExecutor(executor: MaimaiFormExecutor): void {
    this.executor = executor;
  }

  /**
   * 获取浏览器执行器
   */
  getExecutor(): MaimaiFormExecutor | undefined {
    return this.executor;
  }

  /**
   * 从 Excel 文件填充表单
   *
   * @param filePath Excel 文件路径
   * @param options 调试选项
   * @returns 填充报告
   */
  async fillFromFile(filePath: string, options?: DebugOptions): Promise<FillReport> {
    const debug = { ...this.debugOptions, ...options };
    const startTime = Date.now();

    // 1. 读取并解析 Excel
    const parsedRows = await this.reader.parseRows(filePath);

    // 2. 筛选要处理的行
    let rowsToProcess = parsedRows;
    if (debug.row !== undefined) {
      rowsToProcess = parsedRows.filter((row) => row.rowNumber === debug.row);
    }

    // 3. 生成填充操作
    const allOperations: Array<{ row: ParsedSearchRow; operations: FillOperation[] }> =
      rowsToProcess.map((row) => ({
        row,
        operations: this.mapper.generateFillOperations(row),
      }));

    // 4. 如果是 dry-run 模式，只返回模拟结果
    if (debug.dryRun) {
      return this.generateDryRunReport(filePath, allOperations, startTime);
    }

    // 5. 执行填充（实际操作由 agent-browser 完成）
    const rowResults = await this.executeFillOperations(allOperations, debug);

    // 6. 生成报告
    return this.generateReport(filePath, rowResults, startTime);
  }

  /**
   * 执行填充操作
   *
   * 使用 agent-browser 实际执行浏览器操作
   */
  private async executeFillOperations(
    allOperations: Array<{ row: ParsedSearchRow; operations: FillOperation[] }>,
    debug: DebugOptions
  ): Promise<RowFillResult[]> {
    const results: RowFillResult[] = [];

    // 创建填充器上下文
    const fillerContext: FillerContext = {
      executor: this.executor!,
      dryRun: debug.dryRun,
      slow: debug.slow,
      delay: debug.delay,
    };

    // 设置所有填充器的上下文
    fillerRegistry.setContextForAll(fillerContext);

    for (const { row, operations } of allOperations) {
      const rowStartTime = Date.now();
      const fieldResults: FieldFillResult[] = [];

      // 筛选要处理的字段
      let opsToProcess = operations;
      if (debug.onlyFields && debug.onlyFields.length > 0) {
        opsToProcess = operations.filter((op) =>
          debug.onlyFields!.includes(op.field)
        );
      }

      for (const operation of opsToProcess) {
        // 获取对应的填充器
        const filler = fillerRegistry.get(operation.control.type);
        if (!filler) {
          fieldResults.push({
            field: operation.field,
            success: false,
            error: `未找到填充器: ${operation.control.type}`,
          });
          continue;
        }

        // 执行填充
        const result = await filler.fill(operation.control, operation.value);
        fieldResults.push(result);

        // 慢速模式延迟
        if (debug.slow) {
          await this.delay(debug.delay ?? 500);
        }

        // 单步确认
        if (debug.stepByStep) {
          console.log(`[Step] 已填充 ${operation.field}: ${JSON.stringify(operation.value)}`);
          // 等待用户确认
          await this.waitForConfirmation();
        }
      }

      const rowDuration = Date.now() - rowStartTime;
      results.push({
        rowNumber: row.rowNumber,
        fields: fieldResults,
        successCount: fieldResults.filter((f) => f.success).length,
        failCount: fieldResults.filter((f) => !f.success).length,
        duration: rowDuration,
      });
    }

    return results;
  }

  /**
   * 生成 dry-run 报告
   */
  private generateDryRunReport(
    filePath: string,
    allOperations: Array<{ row: ParsedSearchRow; operations: FillOperation[] }>,
    startTime: number
  ): FillReport {
    const rowResults: RowFillResult[] = allOperations.map(({ row, operations }) => ({
      rowNumber: row.rowNumber,
      fields: operations.map((op) => ({
        field: op.field,
        success: true,
        value: op.value,
        duration: 0,
      })),
      successCount: operations.length,
      failCount: 0,
      duration: 0,
    }));

    return this.generateReport(filePath, rowResults, startTime);
  }

  /**
   * 生成填充报告
   */
  private generateReport(
    filePath: string,
    rowResults: RowFillResult[],
    startTime: number
  ): FillReport {
    // 统计各字段成功率
    const fieldStats: Record<string, { success: number; fail: number }> = {};

    for (const row of rowResults) {
      for (const field of row.fields) {
        if (!fieldStats[field.field]) {
          fieldStats[field.field] = { success: 0, fail: 0 };
        }
        if (field.success) {
          fieldStats[field.field].success++;
        } else {
          fieldStats[field.field].fail++;
        }
      }
    }

    return {
      filePath,
      totalRows: rowResults.length,
      processedRows: rowResults.length,
      successRows: rowResults.filter((r) => r.failCount === 0).length,
      partialRows: rowResults.filter((r) => r.failCount > 0 && r.successCount > 0)
        .length,
      failedRows: rowResults.filter((r) => r.successCount === 0).length,
      rowResults,
      fieldStats,
      duration: Date.now() - startTime,
      generatedAt: new Date().toISOString(),
    };
  }

  /**
   * 延迟
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * 等待用户确认
   */
  private waitForConfirmation(): Promise<void> {
    // 在实际使用中，这里会等待用户输入
    // 目前返回一个空 Promise
    return Promise.resolve();
  }

  /**
   * 打印报告摘要
   */
  printReportSummary(report: FillReport): void {
    console.log('\n=== 表单填充报告 ===');
    console.log(`Excel 文件: ${report.filePath}`);
    console.log(`总行数: ${report.totalRows}`);
    console.log(`处理行数: ${report.processedRows}`);
    console.log(`成功: ${report.successRows} / 部分成功: ${report.partialRows} / 失败: ${report.failedRows}`);
    console.log(`耗时: ${report.duration}ms\n`);

    for (const row of report.rowResults) {
      console.log(`--- 第 ${row.rowNumber} 行 ---`);
      for (const field of row.fields) {
        const status = field.success ? '✓' : '✗';
        const value = Array.isArray(field.value)
          ? field.value.join(',')
          : field.value;
        console.log(`${status} ${field.field}: ${value ?? field.error}`);
      }
      console.log('');
    }
  }
}

// 导出类型
export * from './types';

// 导出填充器
export { BaseFiller, fillerRegistry, FillerRegistry, type FillerContext } from './fillers/base';
export { TextFiller } from './fillers/text';
export { SelectFiller } from './fillers/select';
export { CascadeFiller } from './fillers/cascade';
export { TagsFiller } from './fillers/tags';
export { RangeFiller } from './fillers/range';

// 导出映射器和读取器
export { FieldMapper, defaultFieldMapper, CONTROL_SELECTORS } from './mapper';
export { ExcelReader, defaultExcelReader, readSearchConditions } from './reader';

// 导出浏览器执行器
export {
  BrowserExecutor,
  MaimaiFormExecutor,
  defaultBrowserExecutor,
  defaultMaimaiExecutor,
  type BrowserExecutorConfig,
  type FillResult,
  type SnapshotResult,
  type ElementRef,
} from './browser-executor';

// 默认表单填充器实例
export const defaultFormFiller = new FormFiller();
