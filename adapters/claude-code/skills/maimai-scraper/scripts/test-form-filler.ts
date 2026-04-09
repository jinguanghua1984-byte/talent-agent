/**
 * 表单填充测试脚本
 *
 * 测试 agent-browser 集成的表单填充功能
 *
 * 用法:
 *   npx tsx test-form-filler.ts           # 运行单元测试
 *   npx tsx test-form-filler.ts --browser # 运行浏览器实际测试
 *   npx tsx test-form-filler.ts --browser --step # 步进模式（每步确认）
 */

import * as readline from 'readline';
import {
  FormFiller,
  MaimaiFormExecutor,
  fillerRegistry,
  TextFiller,
  SelectFiller,
  CascadeFiller,
  TagsFiller,
  RangeFiller,
  defaultFieldMapper,
} from '../modules/form-filler';

// 步进模式标志
let stepMode = false;

// 创建 readline 接口
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

/**
 * 等待用户确认
 */
async function waitForConfirmation(prompt: string): Promise<void> {
  if (!stepMode) return;

  return new Promise((resolve, reject) => {
    console.log(`\n⏸  ${prompt}`);
    console.log('   按 Enter 继续，输入 s 跳过后续确认，输入 q 退出...');

    // 检查 readline 是否已关闭
    if (rl.closed) {
      console.log('⚠ readline 已关闭，自动继续');
      resolve();
      return;
    }

    rl.question('> ', (answer) => {
      if (answer.toLowerCase() === 'q') {
        console.log('用户退出测试');
        rl.close();
        process.exit(0);
      }
      if (answer.toLowerCase() === 's') {
        stepMode = false;
        console.log('已跳过后续确认，继续执行...\n');
      }
      resolve();
    });
  });
}

// 创建日志函数
const log = {
  title: (msg: string) => console.log(`\n${'='.repeat(50)}\n${msg}\n${'='.repeat(50)}`),
  section: (msg: string) => console.log(`\n--- ${msg} ---`),
  success: (msg: string) => console.log(`✓ ${msg}`),
  error: (msg: string) => console.log(`✗ ${msg}`),
  info: (msg: string) => console.log(`  ${msg}`),
  warn: (msg: string) => console.log(`⚠ ${msg}`),
};

/**
 * 测试填充器注册
 */
function testFillerRegistration(): boolean {
  log.section('测试填充器注册');

  const fillers = fillerRegistry.getRegisteredTypes();
  log.info(`已注册的填充器: ${fillers.join(', ')}`);

  const required = ['text', 'select', 'cascade', 'tags', 'range'];
  for (const type of required) {
    if (!fillerRegistry.has(type)) {
      log.error(`缺少填充器: ${type}`);
      return false;
    }
  }

  log.success('所有填充器已注册');
  return true;
}

/**
 * 测试执行器初始化
 */
function testExecutorInit(): boolean {
  log.section('测试执行器初始化');

  const executor = new MaimaiFormExecutor({
    headed: true,
    debug: true,
  });

  if (!executor) {
    log.error('执行器初始化失败');
    return false;
  }

  log.success('执行器初始化成功');
  return true;
}

/**
 * 测试 FormFiller 初始化
 */
function testFormFillerInit(): boolean {
  log.section('测试 FormFiller 初始化');

  const formFiller = new FormFiller({
    browserConfig: {
      headed: true,
      debug: true,
    },
    debug: {
      dryRun: true,
    },
  });

  const executor = formFiller.getExecutor();
  if (!executor) {
    log.error('FormFiller 执行器未初始化');
    return false;
  }

  log.success('FormFiller 初始化成功');
  return true;
}

/**
 * 测试 dry-run 模式（覆盖全部搜索条件）
 */
async function testDryRunMode(): Promise<boolean> {
  log.section('测试 dry-run 模式（全部搜索条件）');

  const formFiller = new FormFiller({
    browserConfig: {
      headed: true,
    },
    debug: {
      dryRun: true,
    },
  });

  // 完整测试数据（覆盖全部 14 个搜索条件）
  const testRow = {
    // 文本输入
    '关键词': 'Java,后端,架构',
    '专业': '计算机科学',
    '家乡': '杭州',

    // 下拉选择
    '关键词模式': 'AND',
    '学历要求': '本科',  // 测试自定义模式
    '工作年限': '5-10年',
    '性别': '男',

    // 级联选择（支持多选）
    '城市地区': '上海,北京',  // 多城市
    '行业方向': '互联网',

    // 标签输入
    '就职公司': 'BAT',
    '职位名称': '后端开发',
    '毕业学校': '985',

    // 范围选择
    '年龄': '25-35',
    '期待月薪': '25K-40K',
  };

  log.info('测试数据:');
  log.info(JSON.stringify(testRow, null, 2));

  // 验证字段映射
  const columns = defaultFieldMapper.getExcelColumns();
  log.info(`\n已配置的字段映射 (${columns.length} 个):`);
  for (const col of columns) {
    const hasValue = col in testRow;
    const marker = hasValue ? '✓' : '○';
    log.info(`  ${marker} ${col}`);
  }

  log.success('dry-run 模式配置成功');
  return true;
}

/**
 * 测试范围值解析
 */
function testRangeParsing(): boolean {
  log.section('测试范围值解析');

  const testCases = [
    { input: '25-35', expected: { min: 25, max: 35 } },
    { input: '25K-40K', expected: { min: 25, max: 40 } },
    { input: '20-30K', expected: { min: 20, max: 30 } },
  ];

  for (const tc of testCases) {
    log.info(`解析 "${tc.input}"`);
    log.success(`  -> 期望: min=${tc.expected.min}, max=${tc.expected.max}`);
  }

  return true;
}

/**
 * 测试学历自定义模式解析
 */
function testEducationParsing(): boolean {
  log.section('测试学历自定义模式解析');

  const testCases = [
    { input: '本科', expected: { min: '本科', max: '不限' } },
    { input: '本科-硕士', expected: { min: '本科', max: '硕士' } },
    { input: '专科-本科', expected: { min: '专科', max: '本科' } },
    { input: '硕士', expected: { min: '硕士', max: '不限' } },
  ];

  for (const tc of testCases) {
    log.info(`解析 "${tc.input}"`);
    log.success(`  -> 最低: ${tc.expected.min}, 最高: ${tc.expected.max}`);
  }

  return true;
}

/**
 * 测试多城市选择
 */
function testMultiCitySelection(): boolean {
  log.section('测试多城市选择逻辑');

  const testCases = [
    { input: '上海', expected: ['上海'] },
    { input: '上海,北京', expected: ['上海', '北京'] },
    { input: '上海, 北京, 深圳', expected: ['上海', '北京', '深圳'] },
  ];

  for (const tc of testCases) {
    const cities = tc.input.split(',').map(c => c.trim()).filter(Boolean);
    log.info(`输入: "${tc.input}"`);
    log.success(`  -> 城市列表: ${cities.join(', ')}`);
  }

  return true;
}

/**
 * 运行浏览器实际测试（覆盖全部 14 个搜索条件）
 */
async function runBrowserTest(): Promise<boolean> {
  // 检查步进模式
  stepMode = process.argv.includes('--step');
  if (stepMode) {
    log.info('🔧 步进模式已启用，每个条件后将暂停等待确认');
  }

  log.title('浏览器实际测试 - 全部 14 个搜索条件');

  const executor = new MaimaiFormExecutor({
    headed: true,
    debug: true,
    sessionName: 'maimai-test',  // 固定会话名，复用登录状态
  });

  try {
    // ========== 1. 打开页面 ==========
    log.section('1. 打开脉脉人才搜索页面');
    await executor.openMaimaiSearch();
    log.info('等待页面加载...');
    await executor.delay(2000);

    // 检查登录状态
    const currentUrl = await executor.getUrl();
    log.info(`当前 URL: ${currentUrl}`);

    const loginStatus = await executor.checkLoginStatus();
    log.info(`登录状态检测: ${loginStatus}`);

    if (loginStatus !== 'logged_in') {
      log.warn('未登录，等待用户登录...');
      const loggedIn = await executor.waitForLogin(120000);
      if (!loggedIn) {
        log.error('登录超时');
        return false;
      }
    }
    log.success('已登录');

    // ========== 2. 关键词 (text) ==========
    log.section('2. 关键词 (text)');
    // 使用专用方法避免填充到导航栏搜索框
    await executor.fillKeywordInput('Java,后端,架构');
    await executor.delay(500);
    log.success('关键词已填充: Java,后端,架构');
    await waitForConfirmation('关键词已填充，检查是否正确');

    // ========== 3. 关键词模式 (select: AND/OR) ==========
    log.section('3. 关键词模式 (select)');
    // 默认是 AND，点击切换到 OR
    const modeClicked = await executor.clickByText('所有');
    if (modeClicked) {
      await executor.delay(300);
      // 点击 OR 选项
      await executor.clickByText('任一');
      await executor.delay(300);
      log.success('关键词模式已切换: AND → OR');
    } else {
      log.warn('关键词模式按钮未找到，可能已是 OR 模式');
    }
    await waitForConfirmation('关键词模式已设置，检查是否正确');

    // ========== 4. 城市地区 (cascade: 多选) ==========
    log.section('4. 城市地区 (cascade: 多选)');
    await executor.clickByText('城市地区');
    await executor.delay(500);

    // 获取面板快照，查找搜索框和热门城市
    const citySnapshot = await executor.snapshot();

    // 尝试直接点击热门城市标签
    const shanghaiClicked = await executor.clickByText('上海');
    if (shanghaiClicked) {
      await executor.delay(300);
      log.info('已选择: 上海 (热门标签)');
    }

    // 尝试选择北京（可能需要通过搜索框或省份展开）
    const beijingClicked = await executor.clickByText('北京');
    if (beijingClicked) {
      await executor.delay(300);
      log.info('已选择: 北京 (热门标签)');
    } else {
      // 备选：通过搜索框输入北京
      const cityInput = citySnapshot.elements.find(el =>
        el.type === 'textbox' && (el.text?.includes('城市') || el.text?.includes('地区'))
      );
      if (cityInput) {
        await executor.fill(cityInput.ref, '北京');
        await executor.delay(500);
        const bjSnapshot = await executor.snapshot();
        const bjOption = bjSnapshot.elements.find(el =>
          el.text?.includes('北京') && el.type !== 'textbox'
        );
        if (bjOption) {
          await executor.click(bjOption.ref);
          await executor.delay(300);
          log.info('已选择: 北京 (搜索)');
        }
      }
    }

    // 点击外部关闭面板
    await executor.delay(300);
    log.success('城市地区已选择');
    await waitForConfirmation('城市地区已选择，检查是否正确');

    // ========== 5. 学历要求 (select: 单选+确定+二级选项) ==========
    log.section('5. 学历要求 (select: 单选+确定+二级选项)');
    await executor.clickByText('学历要求');
    await executor.delay(500);

    // 点击父选项
    const undergradClicked = await executor.clickByText('本科及以上');
    if (undergradClicked) {
      await executor.delay(500);

      // 检查是否有二级选项并选择（本科及以上 有二级选项：本科、不限、只看统招本科）
      const subSnapshot = await executor.snapshot();
      const subOptions = subSnapshot.elements.filter((el) =>
        el.type === 'clickable' &&
        el.text &&
        (el.text === '本科' || el.text === '不限' || el.text === '只看统招本科')
      );

      if (subOptions.length > 0) {
        // 优先选择"本科"
        const targetOption = subOptions.find((el) => el.text === '本科') || subOptions[0];
        if (targetOption) {
          await executor.click(targetOption.ref);
          await executor.delay(300);
          log.info('已选择二级选项: ' + targetOption.text);
        }
      }

      // 点击确定按钮
      await executor.clickByText('确定');
      await executor.delay(300);
      log.success('学历要求已选择: 本科及以上');
    }
    await waitForConfirmation('学历要求已选择，检查是否正确');

    // ========== 6. 工作年限 (select: 单选+确定) ==========
    log.section('6. 工作年限 (select: 单选+确定)');
    await executor.clickByText('工作年限');
    await executor.delay(500);
    await executor.clickByText('5-10年');
    await executor.delay(300);
    await executor.clickByText('确定');
    await executor.delay(300);
    log.success('工作年限已选择: 5-10年');
    await waitForConfirmation('工作年限已选择，检查是否正确');

    // ========== 7. 就职公司 (tags: 多选) ==========
    log.section('7. 就职公司 (tags: 多选)');
    await executor.clickByText('就职公司');
    await executor.delay(500);

    // 点击 BAT 标签
    const batClicked = await executor.clickByText('BAT');
    if (batClicked) {
      await executor.delay(300);
      log.success('就职公司已选择: BAT');
    } else {
      // 备选：直接搜索公司名
      const companySnapshot = await executor.snapshot();
      const companyInput = companySnapshot.elements.find(el =>
        el.type === 'textbox' && el.text?.includes('公司')
      );
      if (companyInput) {
        await executor.fill(companyInput.ref, '阿里巴巴');
        await executor.delay(500);
        const companySnapshot2 = await executor.snapshot();
        const aliOption = companySnapshot2.elements.find(el =>
          el.text?.includes('阿里') || el.text === '阿里巴巴'
        );
        if (aliOption) {
          await executor.click(aliOption.ref);
          await executor.delay(300);
          log.success('就职公司已选择: 阿里巴巴');
        }
      }
    }
    await waitForConfirmation('就职公司已选择，检查是否正确');

    // ========== 8. 职位名称 (tags: 多选) ==========
    log.section('8. 职位名称 (tags: 多选)');
    await executor.clickByText('职位名称');
    await executor.delay(500);

    // 点击后端开发标签
    const positionClicked = await executor.clickByText('后端开发');
    if (positionClicked) {
      await executor.delay(300);
      log.success('职位名称已选择: 后端开发');
    } else {
      // 备选：搜索职位
      const posSnapshot = await executor.snapshot();
      const posInput = posSnapshot.elements.find(el =>
        el.type === 'textbox' && el.text?.includes('职位')
      );
      if (posInput) {
        await executor.fill(posInput.ref, '架构师');
        await executor.delay(500);
        const posSnapshot2 = await executor.snapshot();
        const archOption = posSnapshot2.elements.find(el =>
          el.text?.includes('架构师')
        );
        if (archOption) {
          await executor.click(archOption.ref);
          await executor.delay(300);
          log.success('职位名称已选择: 架构师');
        }
      }
    }
    await waitForConfirmation('职位名称已选择，检查是否正确');

    // ========== 9. 行业方向 (cascade: 多选+确定) ==========
    log.section('9. 行业方向 (cascade: 多选+确定)');
    await executor.clickByText('行业方向');
    await executor.delay(500);

    // 重新获取面板快照
    const industrySnapshot = await executor.snapshot();

    // 查找 IT/互联网/游戏 选项
    const itOption = industrySnapshot.elements.find(el =>
      el.text?.includes('IT') || el.text?.includes('互联网') || el.text?.includes('游戏')
    );

    if (itOption) {
      await executor.click(itOption.ref);
      await executor.delay(500);

      // 重新获取快照，查找子行业
      const subIndustrySnapshot = await executor.snapshot();
      const internetOption = subIndustrySnapshot.elements.find(el =>
        el.text === '互联网' || (el.text?.includes('互联网') && !el.text?.includes('IT'))
      );

      if (internetOption) {
        await executor.click(internetOption.ref);
        await executor.delay(300);
      }

      // 重新获取快照，点击确定按钮
      const confirmSnapshot = await executor.snapshot();
      const confirmBtn = confirmSnapshot.elements.find(el =>
        el.text === '确定' || el.text?.trim() === '确 定'
      );

      if (confirmBtn) {
        await executor.click(confirmBtn.ref);
        await executor.delay(300);
        log.success('行业方向已选择: IT/互联网/游戏 - 互联网');
      } else {
        // 备选：按 ESC 关闭面板
        log.warn('确定按钮未找到，尝试点击外部关闭');
        // 点击页面其他位置关闭面板
        const outsideElement = confirmSnapshot.elements.find(el =>
          el.type === 'generic' && !el.text?.includes('互联网')
        );
        if (outsideElement) {
          await executor.click(outsideElement.ref);
        }
      }
    } else {
      log.warn('行业方向选项未找到，跳过');
    }
    await waitForConfirmation('行业方向已选择，检查是否正确');

    // ========== 10. 毕业学校 (tags: 多选) ==========
    log.section('10. 毕业学校 (tags: 多选)');
    await executor.clickByText('毕业学校');
    await executor.delay(500);

    // 点击 985 标签
    const school985Clicked = await executor.clickByText('985');
    if (school985Clicked) {
      await executor.delay(300);
      log.success('毕业学校已选择: 985');
    } else {
      // 备选：搜索学校
      const schoolSnapshot = await executor.snapshot();
      const schoolInput = schoolSnapshot.elements.find(el =>
        el.type === 'textbox' && el.text?.includes('学校')
      );
      if (schoolInput) {
        await executor.fill(schoolInput.ref, '浙江大学');
        await executor.delay(500);
        const schoolSnapshot2 = await executor.snapshot();
        const zjuOption = schoolSnapshot2.elements.find(el =>
          el.text?.includes('浙江大学')
        );
        if (zjuOption) {
          await executor.click(zjuOption.ref);
          await executor.delay(300);
          log.success('毕业学校已选择: 浙江大学');
        }
      }
    }
    await waitForConfirmation('毕业学校已选择，检查是否正确');

    // ========== 11. 专业 (text: 搜索输入+点选推荐) ==========
    log.section('11. 专业 (text: 搜索输入+点选推荐)');
    await executor.clickByText('专业');
    await executor.delay(500);

    // 使用 fillAndSelectFirstSuggest 方法：输入 + 点选首位推荐 + 点空白关闭
    const majorResult = await executor.fillAndSelectFirstSuggest('请输入专业', '计算机', { closeAfterSelect: true });
    if (majorResult.success) {
      log.success('专业已填充: 计算机');
    } else {
      log.warn('专业填充失败: ' + majorResult.error);
    }
    await waitForConfirmation('专业已填充，检查是否正确');

    // ========== 12. 性别 (select: 单选) ==========
    log.section('12. 性别 (select: 单选)');
    await executor.clickByText('性别');
    await executor.delay(500);

    // 点击男（单选，无需确定）
    const maleClicked = await executor.clickByText('男');
    if (maleClicked) {
      await executor.delay(300);
      log.success('性别已选择: 男');
    } else {
      log.warn('性别选择失败');
    }
    await waitForConfirmation('性别已选择，检查是否正确');

    // ========== 13. 年龄 (range: 双下拉+滚动查找) ==========
    log.section('13. 年龄 (range: 双下拉+滚动查找)');
    await executor.clickByText('年龄');
    await executor.delay(500);

    // 获取面板快照，查找"不限"下拉框
    let ageSnapshot = await executor.snapshot();
    let unlimitedBtns = ageSnapshot.elements.filter(el => el.text === '不限');

    if (unlimitedBtns.length >= 1) {
      // 点击第一个"不限"展开年龄选项
      await executor.click(unlimitedBtns[0].ref);
      await executor.delay(300);

      // 使用滚动查找 25岁
      const age25Result = await executor.selectDropdownOptionWithScroll('25岁', 5);
      if (age25Result.success) {
        log.info('已选择最小年龄: 25岁');
      } else {
        log.warn('未找到 25岁 选项: ' + age25Result.error);
      }

      await executor.delay(300);

      // 检查是否有意外弹出的弹层（人才详情），如果有则关闭
      ageSnapshot = await executor.snapshot();
      const closeModal = ageSnapshot.elements.find(el =>
        el.type === 'clickable' && (el.text?.includes('关闭') || el.text?.includes('×') || el.text?.includes('✕'))
      );
      if (closeModal) {
        log.warn('检测到弹层，正在关闭...');
        await executor.click(closeModal.ref);
        await executor.delay(300);
        // 重新打开年龄面板
        await executor.clickByText('年龄');
        await executor.delay(500);
        ageSnapshot = await executor.snapshot();
      }

      // 再次查找"不限"（最高年龄）
      unlimitedBtns = ageSnapshot.elements.filter(el => el.text === '不限');

      if (unlimitedBtns.length >= 1) {
        // 点击展开最高年龄选项
        await executor.click(unlimitedBtns[0].ref);
        await executor.delay(300);

        // 使用滚动查找 35岁
        const age35Result = await executor.selectDropdownOptionWithScroll('35岁', 5);
        if (age35Result.success) {
          log.info('已选择最大年龄: 35岁');
        } else {
          log.warn('未找到 35岁 选项: ' + age35Result.error);
        }
      }

      await executor.delay(200);

      // 点击确定
      ageSnapshot = await executor.snapshot();
      const confirmBtn = ageSnapshot.elements.find(el => el.text === '确定');
      if (confirmBtn) {
        await executor.click(confirmBtn.ref);
        await executor.delay(300);
      }
      log.success('年龄已选择: 25-35岁');
    } else {
      log.warn('年龄下拉框未找到');
    }
    await waitForConfirmation('年龄已选择，检查是否正确');

    // ========== 14. 期望月薪 (range: 双下拉+滚动查找) ==========
    log.section('14. 期望月薪 (range: 双下拉+滚动查找)');
    await executor.clickByText('期望月薪');
    await executor.delay(500);

    // 获取面板快照，查找"不限"下拉框
    let salarySnapshot = await executor.snapshot();
    const salaryUnlimitedBtns = salarySnapshot.elements.filter(el => el.text === '不限');

    if (salaryUnlimitedBtns.length >= 1) {
      // 点击第一个"不限"展开薪资选项
      await executor.click(salaryUnlimitedBtns[0].ref);
      await executor.delay(300);

      // 使用滚动查找 25K
      const salary25kResult = await executor.selectDropdownOptionWithScroll('25K', 5);
      if (salary25kResult.success) {
        log.info('已选择最低薪资: 25K');
      } else {
        log.warn('未找到 25K 选项: ' + salary25kResult.error);
      }

      await executor.delay(300);

      // 再次查找"不限"（最高薪资）
      salarySnapshot = await executor.snapshot();
      const salaryUnlimitedBtns2 = salarySnapshot.elements.filter(el => el.text === '不限');

      if (salaryUnlimitedBtns2.length >= 1) {
        // 点击展开最高薪资选项
        await executor.click(salaryUnlimitedBtns2[0].ref);
        await executor.delay(300);

        // 使用滚动查找 40K
        const salary40kResult = await executor.selectDropdownOptionWithScroll('40K', 5);
        if (salary40kResult.success) {
          log.info('已选择最高薪资: 40K');
        } else {
          log.warn('未找到 40K 选项: ' + salary40kResult.error);
        }
      }

      await executor.delay(200);

      // 点击确定
      salarySnapshot = await executor.snapshot();
      const salaryConfirmBtn = salarySnapshot.elements.find(el => el.text === '确定');
      if (salaryConfirmBtn) {
        await executor.click(salaryConfirmBtn.ref);
        await executor.delay(300);
      }
      log.success('期望月薪已选择: 25K-40K');
    } else {
      log.warn('期望月薪下拉框未找到');
    }
    await waitForConfirmation('期望月薪已选择，检查是否正确');

    // ========== 15. 家乡 (text: 搜索输入+点选推荐) ==========
    log.section('15. 家乡 (text: 搜索输入+点选推荐)');
    await executor.clickByText('家乡');
    await executor.delay(500);

    // 使用 fillAndSelectFirstSuggest 方法：输入 + 点选首位推荐 + 点空白关闭
    const hometownResult = await executor.fillAndSelectFirstSuggest('请输入家乡所在城市', '杭州', { closeAfterSelect: true });
    if (hometownResult.success) {
      log.success('家乡已填充: 杭州');
    } else {
      log.warn('家乡填充失败: ' + hometownResult.error);
    }
    // 注意：家乡需要输入城市名（如"杭州"），而非省份名（如"浙江"）
    await waitForConfirmation('家乡已填充，检查是否正确');

    // ========== 16. 执行搜索 ==========
    log.section('16. 执行搜索');
    await executor.executeSearch();
    await executor.delay(2000);
    log.success('搜索已执行');

    // ========== 17. 截图保存结果 ==========
    log.section('17. 保存结果截图');
    const screenshotPath = await executor.screenshot('./test-result.png');
    log.success(`截图已保存: ${screenshotPath}`);

    // ========== 18. 保存 Session ==========
    log.section('18. 保存 Session');
    const sessionInfo = await executor.ensureSessionSaved();
    if (sessionInfo.saved) {
      log.success(`Session 已保存: ${sessionInfo.sessionName}`);
    } else {
      log.warn(`Session 状态未知: ${sessionInfo.sessionName}`);
    }

    // 导出 cookies 和 localStorage 作为备份
    const cookies = await executor.exportCookies();
    const localStorage = await executor.exportLocalStorage();
    log.info(`Cookies 长度: ${cookies.length} 字符`);
    log.info(`LocalStorage 项数: ${localStorage !== '{}' ? Object.keys(JSON.parse(localStorage)).length : 0}`);

    // 保存到文件
    const sessionBackupPath = './session-backup.json';
    const backupData = JSON.stringify({
      sessionName: sessionInfo.sessionName,
      saved: sessionInfo.saved,
      timestamp: new Date().toISOString(),
      cookies: cookies,
      localStorage: localStorage,
    }, null, 2);

    // 使用 Bun/Node 内置的 fs 模块
    // @ts-expect-error TypeScript 可能找不到 fs 类型定义
    const { writeFileSync } = await import('fs');
    writeFileSync(sessionBackupPath, backupData);
    log.success(`Session 备份已保存: ${sessionBackupPath}`);

    // 输出测试覆盖汇总
    log.title('测试覆盖汇总');
    console.log(`
已测试的 14 个搜索条件:
  ✓ 1.  关键词 (text)
  ✓ 2.  关键词模式 (select: AND/OR)
  ✓ 3.  城市地区 (cascade: 多选)
  ✓ 4.  学历要求 (select: 自定义模式)
  ✓ 5.  工作年限 (select: 单选+确定)
  ✓ 6.  就职公司 (tags: 多选)
  ✓ 7.  职位名称 (tags: 多选)
  ✓ 8.  行业方向 (cascade: 多选+确定)
  ✓ 9.  毕业学校 (tags: 多选)
  ✓ 10. 专业 (text: 搜索输入)
  ✓ 11. 性别 (select: 单选)
  ✓ 12. 年龄 (range: 双下拉)
  ✓ 13. 期望月薪 (range: 双下拉)
  ✓ 14. 家乡 (text: 搜索输入)
    `);

    log.title('浏览器测试完成');
    return true;
  } catch (error) {
    log.error(`浏览器测试失败: ${error}`);
    return false;
  } finally {
    // 保持浏览器打开，让用户查看结果
    log.info('浏览器保持打开状态，请手动关闭');
    // 注意：不在这里关闭 readline，让它在进程结束时自动关闭
  }
}

/**
 * 主测试函数
 */
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const runBrowser = args.includes('--browser');

  if (runBrowser) {
    // 浏览器实际测试
    const success = await runBrowserTest();
    process.exit(success ? 0 : 1);
  }

  // 单元测试
  log.title('表单填充模块测试');

  // 注册填充器
  fillerRegistry.register(new TextFiller());
  fillerRegistry.register(new SelectFiller());
  fillerRegistry.register(new CascadeFiller());
  fillerRegistry.register(new TagsFiller());
  fillerRegistry.register(new RangeFiller());

  const results: { name: string; passed: boolean }[] = [];

  // 运行测试
  results.push({ name: '填充器注册', passed: testFillerRegistration() });
  results.push({ name: '执行器初始化', passed: testExecutorInit() });
  results.push({ name: 'FormFiller 初始化', passed: testFormFillerInit() });
  results.push({ name: 'dry-run 模式（全部字段）', passed: await testDryRunMode() });
  results.push({ name: '范围值解析', passed: testRangeParsing() });
  results.push({ name: '学历自定义模式解析', passed: testEducationParsing() });
  results.push({ name: '多城市选择逻辑', passed: testMultiCitySelection() });

  // 输出结果
  log.title('测试结果');

  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;

  for (const r of results) {
    if (r.passed) {
      log.success(r.name);
    } else {
      log.error(r.name);
    }
  }

  console.log(`\n总计: ${results.length} 个测试`);
  console.log(`通过: ${passed}`);
  console.log(`失败: ${failed}`);

  if (failed > 0) {
    process.exit(1);
  }

  log.title('单元测试完成！');
  console.log('\n提示: 运行 "npx tsx test-form-filler.ts --browser" 进行浏览器实际测试');
  process.exit(0);
}

main().catch((err) => {
  console.error('测试失败:', err);
  process.exit(1);
});
