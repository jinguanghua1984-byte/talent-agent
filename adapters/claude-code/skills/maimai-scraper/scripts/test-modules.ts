/**
 * 模块功能测试脚本
 *
 * 测试 form-filler、result-merger、loop-orchestrator 模块
 */

import {
  FormFiller,
  FieldMapper,
  TextFiller,
  SelectFiller,
  CascadeFiller,
  TagsFiller,
  RangeFiller,
  fillerRegistry,
  FIELD_MAPPINGS,
} from '../modules/form-filler';
import { ResultMerger, mergeResults } from '../modules/result-merger';
import { LoopOrchestrator } from '../modules/loop-orchestrator';
import { Logger, createLogger } from '../modules/logger';
import type { Candidate, ScrapeResult } from './types';

// 创建测试 logger
const log = createLogger('test');

/**
 * 测试结果
 */
interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

const results: TestResult[] = [];

/**
 * 运行测试
 */
function test(name: string, fn: () => void | Promise<void>): void {
  try {
    const result = fn();
    if (result instanceof Promise) {
      result
        .then(() => {
          results.push({ name, passed: true });
          log.success(name);
        })
        .catch((err) => {
          results.push({ name, passed: false, error: String(err) });
          log.error(`${name}: ${err}`);
        });
    } else {
      results.push({ name, passed: true });
      log.success(name);
    }
  } catch (err) {
    results.push({ name, passed: false, error: String(err) });
    log.error(`${name}: ${err}`);
  }
}

/**
 * 主测试函数
 */
async function main(): Promise<void> {
  log.title('模块功能测试');
  log.newline();

  // ========== 测试 form-filler 模块 ==========
  log.phase('fill', '测试 form-filler 模块');
  log.newline();

  // 测试填充器注册
  test('填充器注册', () => {
    const textFiller = fillerRegistry.get('text');
    const selectFiller = fillerRegistry.get('select');
    const cascadeFiller = fillerRegistry.get('cascade');
    const tagsFiller = fillerRegistry.get('tags');
    const rangeFiller = fillerRegistry.get('range');

    if (!textFiller) throw new Error('text filler not registered');
    if (!selectFiller) throw new Error('select filler not registered');
    if (!cascadeFiller) throw new Error('cascade filler not registered');
    if (!tagsFiller) throw new Error('tags filler not registered');
    if (!rangeFiller) throw new Error('range filler not registered');
  });

  // 测试文本填充器
  test('TextFiller.fill', async () => {
    const filler = new TextFiller();
    const result = await filler.fill(
      { type: 'text', name: '关键词', selector: 'input' },
      'Java,后端'
    );
    if (!result.success) throw new Error('fill failed');
    if (result.value !== 'Java,后端') throw new Error('value mismatch');
  });

  // 测试下拉填充器
  test('SelectFiller.fill', async () => {
    const filler = new SelectFiller();
    const result = await filler.fill(
      {
        type: 'select',
        name: '学历要求',
        selector: 'select',
        options: { valueMap: { 本科: '2' } },
      },
      '本科'
    );
    if (!result.success) throw new Error('fill failed');
  });

  // 测试范围填充器
  test('RangeFiller.fill (age)', async () => {
    const filler = new RangeFiller();
    const result = await filler.fill(
      { type: 'range', name: '年龄', selector: '.range', options: { format: 'number' } },
      '25-35'
    );
    if (!result.success) throw new Error('fill failed');
  });

  // 测试范围填充器 (薪资)
  test('RangeFiller.fill (salary)', async () => {
    const filler = new RangeFiller();
    const result = await filler.fill(
      { type: 'range', name: '期待月薪', selector: '.range', options: { format: 'salary' } },
      '25K-40K'
    );
    if (!result.success) throw new Error('fill failed');
  });

  // 测试字段映射
  test('FieldMapper', () => {
    const mapper = new FieldMapper();
    const mapping = mapper.getMapping('关键词');
    if (!mapping) throw new Error('mapping not found');
    if (mapping.formField !== 'keyword') throw new Error('wrong formField');
  });

  // 测试行解析
  test('FieldMapper.parseRow', () => {
    const mapper = new FieldMapper();
    const row = {
      关键词: 'Java,后端',
      关键词模式: 'AND',
      城市地区: '上海',
      学历要求: '本科',
      筛选规则: '跳槽<2次',
    };
    const parsed = mapper.parseRow(row, 1);

    if (parsed.keywords?.length !== 2) throw new Error('keywords parse failed');
    if (parsed.keywordMode !== 'AND') throw new Error('keywordMode parse failed');
    if (parsed.filterRules.length !== 1) throw new Error('filterRules parse failed');
  });

  log.newline();

  // ========== 测试 result-merger 模块 ==========
  log.phase('merge', '测试 result-merger 模块');
  log.newline();

  // 创建模拟候选人
  const createMockCandidate = (name: string, company: string): Candidate => ({
    name,
    activeStatus: '今日活跃',
    careerTags: [],
    workHistory: [{ timeRange: '2020-至今', company, position: '工程师', description: '' }],
    educationHistory: [],
    scrapedAt: new Date().toISOString(),
  });

  // 创建模拟抓取结果
  const createMockScrapeResult = (candidates: Candidate[]): ScrapeResult => ({
    candidates,
    totalCount: candidates.length,
    filteredCount: 0,
    filterReasons: [],
    searchConditions: {},
    filterRules: [],
    scrapedAt: new Date().toISOString(),
    duration: '10s',
  });

  // 测试合并器
  test('ResultMerger.merge', () => {
    const merger = new ResultMerger();

    // 添加两组结果，有重复
    merger.addScrapeResult(
      createMockScrapeResult([
        createMockCandidate('张三', '阿里'),
        createMockCandidate('李四', '腾讯'),
      ]),
      1,
      1
    );

    merger.addScrapeResult(
      createMockScrapeResult([
        createMockCandidate('张三', '阿里'), // 重复
        createMockCandidate('王五', '字节'),
      ]),
      2,
      2
    );

    const result = merger.merge();

    if (result.statistics.totalGroups !== 2) throw new Error('totalGroups mismatch');
    if (result.candidates.length !== 3) throw new Error(`candidates length mismatch: expected 3, got ${result.candidates.length}`);
    if (result.statistics.duplicateCount !== 1) throw new Error('duplicateCount mismatch');

    // 检查张三的来源组
    const zhangSan = result.candidates.find((c) => c.name === '张三');
    if (!zhangSan) throw new Error('张三 not found');
    if (zhangSan.sourceGroups.length !== 2) throw new Error('张三应该有2个来源组');
  });

  // 测试快捷合并函数
  test('mergeResults helper', () => {
    const results = [
      createMockScrapeResult([createMockCandidate('测试', '公司')]),
    ];

    const merged = mergeResults(results);
    if (merged.candidates.length !== 1) throw new Error('merge failed');
  });

  log.newline();

  // ========== 测试 logger 模块 ==========
  log.phase('init', '测试 logger 模块');
  log.newline();

  test('Logger basic', () => {
    const testLogger = createLogger('test-module');
    testLogger.debug('debug message');
    testLogger.info('info message');
    testLogger.success('success message');
    testLogger.warn('warn message');
    // 不测试 error，会退出码非0
  });

  test('Logger phase formatting', () => {
    const formatted = log.formatPhase('scrape');
    if (!formatted.includes('scrape')) throw new Error('phase format failed');
  });

  log.newline();

  // ========== 测试 loop-orchestrator 模块 ==========
  log.phase('loop', '测试 loop-orchestrator 模块');
  log.newline();

  test('LoopOrchestrator instantiation', () => {
    const orchestrator = new LoopOrchestrator({
      excelPath: 'test.xlsx',
      mode: 'debug',
      debug: { dryRun: true },
    });

    const state = orchestrator.getState();
    if (state.phase !== 'init') throw new Error('initial phase should be init');
    if (state.mode !== 'debug') throw new Error('mode mismatch');
  });

  log.newline();

  // ========== 输出测试摘要 ==========
  log.separator();
  log.title('测试摘要');

  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;

  console.log(`总计: ${results.length} 个测试`);
  console.log(`通过: ${passed}`);
  console.log(`失败: ${failed}`);

  if (failed > 0) {
    console.log('\n失败的测试:');
    for (const r of results.filter((r) => !r.passed)) {
      console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
  }

  log.newline();
  log.success('所有测试通过！');
  process.exit(0);
}

main().catch((err) => {
  console.error('测试失败:', err);
  process.exit(1);
});
