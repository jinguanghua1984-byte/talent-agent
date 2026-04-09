#!/usr/bin/env ts-node
/**
 * 创建示例 Excel 模板
 *
 * 用法:
 *   npx tsx create-template.ts [output-path]
 *
 * 默认输出到 data/search-template.xlsx
 */

// @ts-ignore
import XLSX from 'xlsx';
import { dirname } from 'node:path';
import { existsSync, mkdirSync } from 'node:fs';

/**
 * Excel 列定义
 */
const COLUMNS = [
  { name: '关键词', example: 'Java,后端,架构', width: 20 },
  { name: '关键词模式', example: 'AND', width: 12 },
  { name: '城市地区', example: '上海,杭州', width: 15 },
  { name: '学历要求', example: '本科', width: 12 },
  { name: '工作年限', example: '3-5年', width: 12 },
  { name: '就职公司', example: '阿里,腾讯', width: 20 },
  { name: '职位名称', example: 'Java开发', width: 15 },
  { name: '行业方向', example: '互联网', width: 15 },
  { name: '毕业学校', example: '985', width: 15 },
  { name: '专业', example: '计算机', width: 15 },
  { name: '性别', example: '', width: 8 },
  { name: '年龄', example: '25-35', width: 10 },
  { name: '期待月薪', example: '25K-40K', width: 12 },
  { name: '家乡', example: '', width: 10 },
  { name: '筛选规则', example: '近三年跳槽不超过2次;有Spring经验', width: 40 },
];

/**
 * 示例数据行
 */
const SAMPLE_DATA = [
  {
    关键词: 'Java,后端,架构',
    关键词模式: 'AND',
    城市地区: '上海',
    学历要求: '本科',
    工作年限: '5-10年',
    就职公司: '',
    职位名称: '',
    行业方向: '互联网',
    毕业学校: '985',
    专业: '',
    性别: '',
    年龄: '28-38',
    期待月薪: '30K-50K',
    家乡: '',
    筛选规则: '近三年跳槽不超过2次',
  },
  {
    关键词: 'Java,后端,架构',
    关键词模式: 'AND',
    城市地区: '杭州',
    学历要求: '本科',
    工作年限: '5-10年',
    就职公司: '',
    职位名称: '',
    行业方向: '互联网',
    毕业学校: '985',
    专业: '',
    性别: '',
    年龄: '28-38',
    期待月薪: '30K-50K',
    家乡: '',
    筛选规则: '近三年跳槽不超过2次',
  },
  {
    关键词: 'Go,后端',
    关键词模式: 'AND',
    城市地区: '上海,杭州',
    学历要求: '本科',
    工作年限: '3-5年',
    就职公司: '',
    职位名称: '',
    行业方向: '互联网',
    毕业学校: '',
    专业: '',
    性别: '',
    年龄: '25-32',
    期待月薪: '25K-40K',
    家乡: '',
    筛选规则: '有微服务经验;熟悉分布式系统',
  },
];

/**
 * 创建模板文件
 */
function createTemplate(outputPath: string): void {
  // 创建工作簿
  const workbook = XLSX.utils.book_new();

  // Sheet 1: 搜索条件模板
  const headers = COLUMNS.map((col) => col.name);
  const exampleRow = COLUMNS.map((col) => col.example);
  const sampleRows = SAMPLE_DATA.map((row) => headers.map((h) => row[h as keyof typeof row] || ''));

  const templateData = [headers, exampleRow, ...sampleRows];
  const templateSheet = XLSX.utils.aoa_to_sheet(templateData);

  // 设置列宽
  templateSheet['!cols'] = COLUMNS.map((col) => ({ wch: col.width }));

  XLSX.utils.book_append_sheet(workbook, templateSheet, '搜索条件');

  // Sheet 2: 说明文档
  const instructions = [
    ['字段说明'],
    [''],
    ['字段名', '类型', '说明', '示例值'],
    ['关键词', '必填', '搜索关键词，多个用逗号分隔', 'Java,后端,架构'],
    ['关键词模式', '可选', 'AND=满足全部，OR=满足任一，默认AND', 'AND'],
    ['城市地区', '可选', '目标城市，多个用逗号分隔', '上海,杭州'],
    ['学历要求', '可选', '最低学历：大专/本科/硕士/博士', '本科'],
    ['工作年限', '可选', '工作经验范围', '3-5年'],
    ['就职公司', '可选', '目标公司，多个用逗号分隔', '阿里,腾讯'],
    ['职位名称', '可选', '目标职位关键词', 'Java开发'],
    ['行业方向', '可选', '目标行业', '互联网'],
    ['毕业学校', '可选', '院校关键词', '985'],
    ['专业', '可选', '专业关键词', '计算机'],
    ['性别', '可选', '男/女/不限', ''],
    ['年龄', '可选', '年龄范围', '25-35'],
    ['期待月薪', '可选', '薪资范围', '25K-40K'],
    ['家乡', '可选', '籍贯筛选', ''],
    ['筛选规则', '可选', '后处理筛选规则，多条用分号分隔', '跳槽<2次;有大厂经历'],
    [''],
    ['注意事项'],
    ['1. 第一行为表头，请勿修改'],
    ['2. 第二行为示例数据，可删除'],
    ['3. 空单元格表示不填写该条件'],
    ['4. 列名必须与上表完全一致'],
  ];

  const instructionsSheet = XLSX.utils.aoa_to_sheet(instructions);
  instructionsSheet['!cols'] = [
    { wch: 15 },
    { wch: 10 },
    { wch: 40 },
    { wch: 25 },
  ];

  XLSX.utils.book_append_sheet(workbook, instructionsSheet, '字段说明');

  // 写入文件
  XLSX.writeFile(workbook, outputPath);

  console.log(`模板已创建: ${outputPath}`);
  console.log('\n包含:');
  console.log('  - Sheet 1 "搜索条件": 搜索条件模板（含示例数据）');
  console.log('  - Sheet 2 "字段说明": 字段说明和注意事项');
}

// 主函数
function main(): void {
  const args = process.argv.slice(2);
  const outputPath = args[0] || 'data/search-template.xlsx';

  // 确保目录存在
  const dir = dirname(outputPath);
  if (dir && !existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }

  createTemplate(outputPath);
}

main();
