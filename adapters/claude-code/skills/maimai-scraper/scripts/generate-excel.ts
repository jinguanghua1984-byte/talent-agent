/**
 * 脉脉候选人信息 Excel 生成脚本
 *
 * 功能：
 * 1. 生成包含统计概览和候选人详情的 Excel 文件
 * 2. 支持工作履历、教育履历的结构化展示
 *
 * 依赖：ExcelJS (npm install exceljs)
 *
 * 使用方式：
 * npx ts-node scripts/generate-excel.ts <candidates.json>
 */

import ExcelJS from 'exceljs';
import type { Candidate, ScrapeResult, FilterReason } from './types';

// 类型定义
export interface WorkHistory {
  timeRange: string;
  company: string;
  position: string;
  description?: string;
}

export interface EducationHistory {
  timeRange: string;
  school: string;
  major: string;
  degree: string;
}

export interface Candidate {
  // 基础信息
  name: string;
  activeStatus: string; // 活跃度
  age?: number;
  workYears?: number;
  education?: string;
  workLocation?: string;
  expectedLocation?: string;
  expectedSalary?: string;
  expectedPosition?: string;

  // 标签
  careerTags: string[];

  // 履历
  workHistory: WorkHistory[];
  educationHistory: EducationHistory[];

  // 元信息
  sourceUrl?: string;
  scrapedAt: string;
}

export interface FilterReason {
  reason: string;
  count: number;
}

export interface ScrapeResult {
  candidates: Candidate[];
  filteredCount: number;
  filterReasons: FilterReason[];
  searchConditions: Record<string, string>;
  filterRules: string[];
  scrapedAt: string;
  duration: string;
}

/**
 * 生成候选人 Excel 报告
 */
export async function generateCandidateExcel(
  result: ScrapeResult,
  outputPath: string
): Promise<string> {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'maimai-scraper';
  workbook.created = new Date();

  // Sheet 1: 统计概览
  const statsSheet = workbook.addWorksheet('统计概览');

  // 标题样式
  const titleStyle = {
    font: { bold: true, size: 14 },
    fill: { type: 'pattern' as const, pattern: 'solid' as const, fgColor: { argb: 'FFE0E0E0' } },
  };

  const headerStyle = {
    font: { bold: true },
    fill: { type: 'pattern' as const, pattern: 'solid' as const, fgColor: { argb: 'FFF0F0F0' } },
  };

  // 基础统计
  statsSheet.addRow(['脉脉候选人抓取报告']).font = { bold: true, size: 16 };
  statsSheet.mergeCells('A1:B1');
  statsSheet.addRow([]);

  statsSheet.addRow(['基础统计', '']).eachCell(cell => Object.assign(cell, titleStyle));
  statsSheet.addRow(['总抓取数量', result.candidates.length + result.filteredCount]);
  statsSheet.addRow(['通过筛选数量', result.candidates.length]);
  statsSheet.addRow(['淘汰数量', result.filteredCount]);
  const passRate = result.candidates.length + result.filteredCount > 0
    ? ((result.candidates.length / (result.candidates.length + result.filteredCount)) * 100).toFixed(1)
    : '0';
  statsSheet.addRow(['通过率', `${passRate}%`]);
  statsSheet.addRow(['抓取时间', result.scrapedAt]);
  statsSheet.addRow(['抓取耗时', result.duration]);
  statsSheet.addRow([]);

  // 搜索条件
  statsSheet.addRow(['搜索条件', '']).eachCell(cell => Object.assign(cell, titleStyle));
  Object.entries(result.searchConditions).forEach(([key, value]) => {
    if (value) {
      statsSheet.addRow([key, value]);
    }
  });
  statsSheet.addRow([]);

  // 筛选规则
  statsSheet.addRow(['筛选规则', '']).eachCell(cell => Object.assign(cell, titleStyle));
  result.filterRules.forEach((rule, index) => {
    statsSheet.addRow([`规则${index + 1}`, rule]);
  });
  statsSheet.addRow([]);

  // 淘汰原因分布
  statsSheet.addRow(['淘汰原因分布', '']).eachCell(cell => Object.assign(cell, titleStyle));
  statsSheet.addRow(['原因', '数量']).eachCell(cell => Object.assign(cell, headerStyle));
  result.filterReasons.forEach(({ reason, count }) => {
    statsSheet.addRow([reason, count]);
  });

  // 调整列宽
  statsSheet.columns.forEach((column, index) => {
    column.width = index === 0 ? 20 : 50;
  });

  // Sheet 2: 候选人详情
  const detailSheet = workbook.addWorksheet('候选人详情');

  // 表头
  const headers = [
    '序号', '姓名', '活跃度', '年龄', '工作年限', '学历', '工作地点',
    '期望地点', '期望薪资', '期望职位', '职业标签',
    '工作履历', '教育履历', '抓取时间'
  ];
  detailSheet.addRow(headers).eachCell(cell => Object.assign(cell, headerStyle));

  // 数据行
  result.candidates.forEach((candidate, index) => {
    detailSheet.addRow([
      index + 1,
      candidate.name,
      candidate.activeStatus,
      candidate.age ?? '',
      candidate.workYears ? `${candidate.workYears}年` : '',
      candidate.education ?? '',
      candidate.workLocation ?? '',
      candidate.expectedLocation ?? '',
      candidate.expectedSalary ?? '',
      candidate.expectedPosition ?? '',
      candidate.careerTags.join(', '),
      formatWorkHistory(candidate.workHistory),
      formatEducationHistory(candidate.educationHistory),
      candidate.scrapedAt,
    ]);
  });

  // 调整列宽
  const columnWidths = [6, 10, 12, 8, 10, 10, 12, 12, 12, 15, 30, 50, 40, 20];
  detailSheet.columns.forEach((column, index) => {
    column.width = columnWidths[index] || 15;
  });

  // 设置自动换行
  detailSheet.eachRow((row, rowNumber) => {
    if (rowNumber > 1) {
      row.eachCell(cell => {
        cell.alignment = { wrapText: true, vertical: 'top' };
      });
    }
  });

  // 保存文件
  await workbook.xlsx.writeFile(outputPath);
  return outputPath;
}

/**
 * 格式化工作履历为字符串
 */
function formatWorkHistory(history: WorkHistory[]): string {
  if (!history || history.length === 0) return '';

  return history.map(item =>
    `${item.timeRange}\n${item.company} - ${item.position}` +
    (item.description ? `\n${item.description}` : '')
  ).join('\n\n');
}

/**
 * 格式化教育履历为字符串
 */
function formatEducationHistory(history: EducationHistory[]): string {
  if (!history || history.length === 0) return '';

  return history.map(item =>
    `${item.timeRange}\n${item.school} - ${item.major} (${item.degree})`
  ).join('\n\n');
}

/**
 * 生成默认输出路径
 */
export function generateOutputPath(): string {
  const timestamp = new Date().toISOString()
    .replace(/[:.]/g, '-')
    .replace('T', '_')
    .slice(0, 19);
  return `candidates_脉脉_${timestamp}.xlsx`;
}

// CLI 入口
if (require.main === module) {
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.error('Usage: npx ts-node generate-excel.ts <candidates.json>');
    process.exit(1);
  }

  import('fs').then(fs => {
    const data = JSON.parse(fs.readFileSync(inputPath, 'utf-8')) as ScrapeResult;
    const outputPath = generateOutputPath();

    generateCandidateExcel(data, outputPath)
      .then(path => console.log(`Excel 文件已生成: ${path}`))
      .catch(err => console.error('生成失败:', err));
  });
}
