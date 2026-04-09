/**
 * Excel 读取器
 *
 * 读取 Excel 文件并解析为搜索条件行
 */

import type { ExcelReadResult, ExcelRow, ParsedSearchRow } from './types';
import { FieldMapper, defaultFieldMapper } from './mapper';

/**
 * Excel 读取器类
 *
 * 注意：这是一个框架实现，实际 Excel 读取需要依赖 xlsx 库
 * 在 Claude Code 环境中，可以使用 Node.js 的 xlsx 包
 */
export class ExcelReader {
  private mapper: FieldMapper;

  constructor(mapper: FieldMapper = defaultFieldMapper) {
    this.mapper = mapper;
  }

  /**
   * 读取 Excel 文件
   *
   * @param filePath Excel 文件路径
   * @returns 读取结果
   */
  async read(filePath: string): Promise<ExcelReadResult> {
    const errors: string[] = [];

    try {
      // 动态导入 xlsx 库
      const XLSX = await this.importXlsx();

      // 读取文件
      const workbook = XLSX.readFile(filePath);
      const sheetName = workbook.SheetNames[0];
      const sheet = workbook.Sheets[sheetName];

      // 转换为 JSON
      const rawData = XLSX.utils.sheet_to_json<ExcelRow>(sheet, {
        defval: '',
      });

      // 获取表头
      const headers = this.extractHeaders(sheet);

      return {
        filePath,
        totalRows: rawData.length,
        headers,
        rows: rawData,
        errors: errors.length > 0 ? errors : undefined,
      };
    } catch (error) {
      return {
        filePath,
        totalRows: 0,
        headers: [],
        rows: [],
        errors: [`读取失败: ${error}`],
      };
    }
  }

  /**
   * 解析 Excel 行数据
   */
  async parseRows(filePath: string): Promise<ParsedSearchRow[]> {
    const readResult = await this.read(filePath);

    if (readResult.errors && readResult.errors.length > 0) {
      throw new Error(`Excel 读取失败: ${readResult.errors.join(', ')}`);
    }

    return readResult.rows.map((row, index) => this.mapper.parseRow(row, index + 1));
  }

  /**
   * 解析单行
   */
  parseRow(row: ExcelRow, rowNumber: number): ParsedSearchRow {
    return this.mapper.parseRow(row, rowNumber);
  }

  /**
   * 动态导入 xlsx 库
   */
  private async importXlsx(): Promise<typeof import('xlsx')> {
    try {
      // 尝试导入 xlsx
      return await import('xlsx');
    } catch {
      throw new Error(
        'xlsx 库未安装。请运行: npm install xlsx 或 pnpm add xlsx'
      );
    }
  }

  /**
   * 提取表头
   */
  private extractHeaders(sheet: unknown): string[] {
    // 简化实现，实际需要处理合并单元格等情况
    const XLSX = require('xlsx');
    const range = XLSX.utils.decode_range((sheet as { ['!ref']?: string })['!ref'] || 'A1');

    const headers: string[] = [];
    for (let col = range.s.c; col <= range.e.c; col++) {
      const cell = (sheet as Record<string, { v?: string }>)[XLSX.utils.encode_cell({ r: 0, c: col })];
      headers.push(cell?.v ?? '');
    }

    return headers;
  }

  /**
   * 验证 Excel 格式
   */
  async validate(filePath: string): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = [];

    try {
      const readResult = await this.read(filePath);

      // 检查是否有数据
      if (readResult.totalRows === 0) {
        errors.push('Excel 文件没有数据行');
      }

      // 检查必需列
      const validColumns = this.mapper.getExcelColumns();
      const missingColumns = validColumns.filter(
        (col) => !readResult.headers.includes(col)
      );

      // 只报告关键缺失列（关键词）
      if (!readResult.headers.includes('关键词')) {
        errors.push('缺少必需列: 关键词');
      }

      return {
        valid: errors.length === 0,
        errors,
      };
    } catch (error) {
      return {
        valid: false,
        errors: [`验证失败: ${error}`],
      };
    }
  }
}

// 默认读取器实例
export const defaultExcelReader = new ExcelReader();

/**
 * 快捷函数：读取并解析 Excel
 */
export async function readSearchConditions(
  filePath: string
): Promise<ParsedSearchRow[]> {
  return defaultExcelReader.parseRows(filePath);
}
