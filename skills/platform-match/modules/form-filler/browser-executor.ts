/**
 * agent-browser 执行器
 *
 * 封装 agent-browser CLI 命令，提供类型安全的浏览器操作接口
 */

import { exec } from 'node:child_process';
import { promisify } from 'node:util';

const execAsync = promisify(exec);

/**
 * 执行器配置
 */
export interface BrowserExecutorConfig {
  /** agent-browser 命令路径，默认 'agent-browser' */
  command?: string;
  /** 默认超时时间（毫秒） */
  timeout?: number;
  /** 是否启用 headed 模式 */
  headed?: boolean;
  /** 会话名称 */
  sessionName?: string;
  /** 调试模式 */
  debug?: boolean;
}

/**
 * 元素引用（从 snapshot -i 获取）
 */
export interface ElementRef {
  ref: string;
  type: string;
  text?: string;
}

/**
 * Snapshot 结果
 */
export interface SnapshotResult {
  elements: ElementRef[];
  raw: string;
}

/**
 * 填充结果
 */
export interface FillResult {
  success: boolean;
  error?: string;
  duration: number;
}

/**
 * agent-browser 执行器
 */
export class BrowserExecutor {
  private config: Required<Omit<BrowserExecutorConfig, 'sessionName'>> & Pick<BrowserExecutorConfig, 'sessionName'>;

  constructor(config?: BrowserExecutorConfig) {
    this.config = {
      command: config?.command ?? 'agent-browser',
      timeout: config?.timeout ?? 30000,
      headed: config?.headed ?? true,
      sessionName: config?.sessionName,
      debug: config?.debug ?? false,
    };
  }

  /**
   * 构建基础命令
   */
  private buildBaseCommand(): string {
    let cmd = this.config.command;
    if (this.config.headed) {
      cmd = `${cmd} --headed`;
    }
    if (this.config.sessionName) {
      cmd = `${cmd} --session-name ${this.config.sessionName}`;
    }
    return cmd;
  }

  /**
   * 执行 agent-browser 命令
   */
  protected async exec(args: string, timeout?: number): Promise<{ stdout: string; stderr: string }> {
    const cmd = `${this.buildBaseCommand()} ${args}`;
    const actualTimeout = timeout ?? this.config.timeout;

    if (this.config.debug) {
      console.log(`[BrowserExecutor] Executing: ${cmd}`);
    }

    try {
      const result = await execAsync(cmd, {
        timeout: actualTimeout,
        maxBuffer: 1024 * 1024 * 10, // 10MB buffer
      });
      return result;
    } catch (error: unknown) {
      const err = error as { stdout?: string; stderr?: string; message?: string };
      // 即使命令失败，也可能有有用的输出
      if (err.stdout || err.stderr) {
        return {
          stdout: err.stdout ?? '',
          stderr: err.stderr ?? '',
        };
      }
      throw error;
    }
  }

  /**
   * 执行 JavaScript 代码
   */
  async eval(js: string): Promise<string> {
    const { stdout } = await this.exec(`eval "${js.replace(/"/g, '\\"')}"`);
    // 解析输出（可能是 JSON 字符串或纯文本）
    const trimmed = stdout.trim();
    // 如果是带引号的字符串，去掉引号
    if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
        (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
      return trimmed.slice(1, -1);
    }
    return trimmed;
  }

  /**
   * 打开 URL
   */
  async open(url: string): Promise<void> {
    await this.exec(`open "${url}"`);
    // 等待页面加载
    await this.wait('networkidle');
  }

  /**
   * 获取交互式快照
   */
  async snapshot(): Promise<SnapshotResult> {
    const { stdout } = await this.exec('snapshot -i -C');
    const elements = this.parseSnapshot(stdout);
    return { elements, raw: stdout };
  }

  /**
   * 解析 snapshot 输出
   */
  private parseSnapshot(output: string): ElementRef[] {
    const elements: ElementRef[] = [];
    const lines = output.split('\n');

    for (const line of lines) {
      // 解析格式: - textbox "placeholder" [ref=e1]
      // 或: - clickable "text" [ref=e2] [cursor:pointer, onclick]
      const match = line.match(/- (\w+)\s+"([^"]*)"\s*\[ref=(e\d+)\]/);
      if (match) {
        elements.push({
          type: match[1],
          text: match[2],
          ref: match[3],
        });
      }
    }

    return elements;
  }

  /**
   * 通过文本查找元素
   */
  async findByText(text: string): Promise<ElementRef | undefined> {
    const { elements } = await this.snapshot();
    return elements.find((el) =>
      el.text?.toLowerCase().includes(text.toLowerCase())
    );
  }

  /**
   * 点击元素
   */
  async click(ref: string): Promise<void> {
    await this.exec(`click ${ref}`);
  }

  /**
   * 通过文本点击
   */
  async clickByText(text: string, options?: { exact?: boolean }): Promise<boolean> {
    const { elements } = await this.snapshot();
    const element = elements.find((el) => {
      if (el.type !== 'clickable') return false;
      if (options?.exact) {
        return el.text === text;
      }
      // 优先匹配以 text 开头的元素（如 "家乡：" 开头的按钮）
      if (el.text?.startsWith(text)) return true;
      return el.text?.includes(text);
    });
    if (!element) {
      return false;
    }
    await this.click(element.ref);
    return true;
  }

  /**
   * 填充文本输入框
   */
  async fill(ref: string, value: string): Promise<void> {
    await this.exec(`fill ${ref} "${this.escapeValue(value)}"`);
  }

  /**
   * 通过占位符查找并填充
   */
  async fillByPlaceholder(placeholder: string, value: string): Promise<FillResult> {
    const startTime = Date.now();
    const { elements } = await this.snapshot();

    const input = elements.find((el) =>
      el.type === 'textbox' &&
      el.text?.toLowerCase().includes(placeholder.toLowerCase())
    );

    if (!input) {
      return {
        success: false,
        error: `找不到输入框: ${placeholder}`,
        duration: Date.now() - startTime,
      };
    }

    await this.fill(input.ref, value);
    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 选择下拉选项
   */
  async selectOption(ref: string, value: string): Promise<void> {
    await this.exec(`select ${ref} "${this.escapeValue(value)}"`);
  }

  /**
   * 通过文本选择下拉选项
   */
  async selectOptionByText(optionText: string): Promise<FillResult> {
    const startTime = Date.now();
    const element = await this.findByText(optionText);

    if (!element) {
      return {
        success: false,
        error: `找不到选项: ${optionText}`,
        duration: Date.now() - startTime,
      };
    }

    await this.click(element.ref);
    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 勾选复选框
   */
  async check(ref: string): Promise<void> {
    await this.exec(`check ${ref}`);
  }

  /**
   * 取消勾选复选框
   */
  async uncheck(ref: string): Promise<void> {
    await this.exec(`uncheck ${ref}`);
  }

  /**
   * 通过标签勾选复选框
   */
  async checkByLabel(label: string, checked: boolean = true): Promise<FillResult> {
    const startTime = Date.now();
    const { elements } = await this.snapshot();

    const checkbox = elements.find((el) =>
      el.type === 'checkbox' &&
      el.text?.toLowerCase().includes(label.toLowerCase())
    );

    if (!checkbox) {
      return {
        success: false,
        error: `找不到复选框: ${label}`,
        duration: Date.now() - startTime,
      };
    }

    if (checked) {
      await this.check(checkbox.ref);
    } else {
      await this.uncheck(checkbox.ref);
    }

    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 等待
   */
  async wait(target: string | number): Promise<void> {
    if (typeof target === 'number') {
      await this.exec(`wait ${target}`);
    } else {
      await this.exec(`wait --load ${target}`);
    }
  }

  /**
   * 等待元素出现
   */
  async waitForElement(selector: string): Promise<void> {
    await this.exec(`wait "${selector}"`);
  }

  /**
   * 等待文本出现
   */
  async waitForText(text: string): Promise<void> {
    await this.exec(`wait --text "${text}"`);
  }

  /**
   * 截图
   */
  async screenshot(path?: string): Promise<string> {
    const args = path ? `screenshot ${path}` : 'screenshot';
    const { stdout } = await this.exec(args);
    // 从输出中提取文件路径
    const match = stdout.match(/saved to\s+(.+)/);
    return match ? match[1].trim() : '';
  }

  /**
   * 获取元素文本
   */
  async getText(ref: string): Promise<string> {
    const { stdout } = await this.exec(`get text ${ref}`);
    return stdout.trim();
  }

  /**
   * 获取当前 URL
   */
  async getUrl(): Promise<string> {
    const { stdout, stderr } = await this.exec('get url');
    if (this.config.debug) {
      console.log(`[BrowserExecutor] getUrl stdout: "${stdout}"`);
      console.log(`[BrowserExecutor] getUrl stderr: "${stderr}"`);
    }
    return stdout.trim();
  }

  /**
   * 关闭浏览器
   */
  async close(): Promise<void> {
    await this.exec('close');
  }

  /**
   * 获取当前 session 名称
   */
  async getSessionName(): Promise<string> {
    const { stdout } = await this.exec('session');
    return stdout.trim();
  }

  /**
   * 列出所有活跃的 sessions
   */
  async listSessions(): Promise<string[]> {
    const { stdout } = await this.exec('session list');
    // 解析输出，提取 session 名称
    const lines = stdout.trim().split('\n');
    return lines.filter(line => line.trim() && !line.includes('No sessions'));
  }

  /**
   * 保存当前页面状态到 session
   *
   * agent-browser 使用 --session-name 时会自动保存，
   * 此方法通过获取 session 信息来确认 session 状态
   */
  async ensureSessionSaved(): Promise<{ sessionName: string; saved: boolean }> {
    const sessionName = this.config.sessionName || 'default';
    // agent-browser 在每次操作后会自动保存 session
    // 这里通过获取 session 信息来确认
    const currentSession = await this.getSessionName();
    return {
      sessionName,
      saved: currentSession === sessionName || currentSession.includes(sessionName),
    };
  }

  /**
   * 导出当前页面的 cookies（用于调试或备份）
   */
  async exportCookies(): Promise<string> {
    const js = `JSON.stringify(document.cookie)`;
    return this.eval(js);
  }

  /**
   * 导出 localStorage（用于调试或备份）
   */
  async exportLocalStorage(): Promise<string> {
    const js = `JSON.stringify(Object.keys(localStorage).reduce((acc, key) => { acc[key] = localStorage.getItem(key); return acc; }, {}))`;
    return this.eval(js);
  }

  /**
   * 转义值中的特殊字符
   */
  private escapeValue(value: string): string {
    return value
      .replace(/"/g, '\\"')
      .replace(/\$/g, '\\$')
      .replace(/`/g, '\\`');
  }

  /**
   * 延迟
   */
  async delay(ms: number): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, ms));
  }
}

/**
 * 脉脉表单填充执行器
 *
 * 专门用于脉脉人才搜索页面的表单填充
 *
 * 特殊处理：
 * 1. 关键词输入框 - 需要定位到搜索条件区域的输入框，而非导航栏
 * 2. 学历要求 - 有二级选项，需要点击到末级
 * 3. 下拉选择 - 需要滚动才能看到所有选项（工作年限、年龄、期望月薪）
 */
export class MaimaiFormExecutor extends BrowserExecutor {
  /**
   * 打开脉脉人才搜索页面
   */
  async openMaimaiSearch(): Promise<void> {
    await this.open('https://maimai.cn/ent/v41/recruit/talents?pid=&tab=1');
  }

  /**
   * 检查登录状态
   */
  async checkLoginStatus(): Promise<'logged_in' | 'not_logged_in' | 'unknown'> {
    const url = await this.getUrl();
    if (url.includes('/login')) {
      return 'not_logged_in';
    }
    if (url.includes('/recruit/talents')) {
      return 'logged_in';
    }
    return 'unknown';
  }

  /**
   * 等待登录完成
   */
  async waitForLogin(timeout: number = 120000): Promise<boolean> {
    const startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      const status = await this.checkLoginStatus();
      if (status === 'logged_in') {
        return true;
      }
      await this.delay(2000);
    }
    return false;
  }

  /**
   * 展开筛选面板
   */
  async expandFilterPanel(filterName: string): Promise<boolean> {
    // 点击筛选条件按钮
    const clicked = await this.clickByText(filterName);
    if (!clicked) {
      return false;
    }
    // 等待面板展开
    await this.delay(300);
    return true;
  }

  /**
   * 填充关键词输入框
   *
   * 重要：页面有两个搜索框
   * 1. 导航栏搜索框 - 不要用这个
   * 2. 搜索条件区域的输入框 - 使用这个
   *
   * 通过查找包含"搜人才"的 placeholder 来定位正确的输入框
   */
  async fillKeywordInput(value: string): Promise<FillResult> {
    const startTime = Date.now();
    const { elements } = await this.snapshot();

    // 查找包含"搜人才"的输入框（搜索条件区域的输入框）
    const keywordInput = elements.find((el) =>
      el.type === 'textbox' &&
      el.text?.includes('搜人才')
    );

    if (!keywordInput) {
      return {
        success: false,
        error: '找不到关键词输入框（搜索条件区域）',
        duration: Date.now() - startTime,
      };
    }

    await this.fill(keywordInput.ref, value);
    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 填充文本搜索框
   */
  async fillSearchInput(placeholder: string, value: string): Promise<FillResult> {
    return this.fillByPlaceholder(placeholder, value);
  }

  /**
   * 滚动下拉列表并查找选项
   *
   * 用于处理下拉选项较多，需要滚动才能看到的情况
   * 适用于：工作年限、年龄、期望月薪等
   *
   * @param targetText 目标选项文本（如 "25K", "5-10年"）
   * @param maxScrolls 最大滚动次数
   */
  async scrollAndFindOption(targetText: string, maxScrolls: number = 10): Promise<FillResult> {
    const startTime = Date.now();

    // 先尝试直接查找
    let directFind = await this.findByText(targetText);
    if (directFind) {
      await this.click(directFind.ref);
      return { success: true, duration: Date.now() - startTime };
    }

    // 需要滚动查找 - 使用 agent-browser scroll 命令
    for (let i = 0; i < maxScrolls; i++) {
      // 在下拉面板内滚动
      await this.exec(`scroll down 100 --selector "[class*='dropdown'], [class*='select-dropdown'], .ant-select-dropdown"`);
      await this.delay(200);

      // 检查是否找到目标
      directFind = await this.findByText(targetText);
      if (directFind) {
        await this.click(directFind.ref);
        return { success: true, duration: Date.now() - startTime };
      }
    }

    return {
      success: false,
      error: `滚动 ${maxScrolls} 次后仍未找到选项: ${targetText}`,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 选择选项并检查是否有子选项
   *
   * 用于处理有二级选项的控件（如学历要求）
   * 点击选项后，检查是否展开了子选项列表，如果有则继续选择
   *
   * @param parentText 父选项文本（如 "本科及以上"）
   * @param childText 子选项文本（如 "本科"），如果不提供则自动选择第一个子选项
   */
  async selectWithSubOptions(parentText: string, childText?: string): Promise<FillResult> {
    const startTime = Date.now();

    // 1. 点击父选项
    const parent = await this.findByText(parentText);
    if (!parent) {
      return {
        success: false,
        error: `找不到选项: ${parentText}`,
        duration: Date.now() - startTime,
      };
    }

    await this.click(parent.ref);
    await this.delay(300);

    // 2. 检查是否展开了子选项
    const snapshot = await this.snapshot();
    const subOptions = snapshot.elements.filter((el) =>
      el.type === 'clickable' &&
      el.text &&
      el.text !== parentText &&
      !el.text.includes('确定') &&
      !el.text.includes('取消')
    );

    // 如果有子选项，选择对应的子选项
    if (subOptions.length > 0) {
      let targetSubOption: ElementRef | undefined;

      if (childText) {
        // 查找指定的子选项
        targetSubOption = subOptions.find((el) =>
          el.text?.includes(childText) || el.text === childText
        );
      } else {
        // 选择第一个子选项
        targetSubOption = subOptions[0];
      }

      if (targetSubOption) {
        await this.click(targetSubOption.ref);
        await this.delay(200);
      }
    }

    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 选择下拉选项并确认
   */
  async selectAndConfirm(optionText: string): Promise<FillResult> {
    const result = await this.selectOptionByText(optionText);
    if (!result.success) {
      return result;
    }

    // 等待选项选中
    await this.delay(200);

    // 点击确定按钮
    const confirmed = await this.clickByText('确定');
    if (!confirmed) {
      return {
        success: false,
        error: '找不到确定按钮',
        duration: result.duration,
      };
    }

    return result;
  }

  /**
   * 选择范围下拉选项（两个下拉框）
   *
   * 用于处理双下拉范围选择控件（如年龄、期望月薪）
   *
   * @param minValue 最小值
   * @param maxValue 最大值
   */
  async selectRangeOptions(minValue: string, maxValue: string): Promise<FillResult> {
    const startTime = Date.now();

    // 获取当前快照，找到 combobox
    const snapshot1 = await this.snapshot();
    const comboboxes = snapshot1.elements.filter((el) => el.type === 'combobox');

    if (comboboxes.length < 2) {
      return {
        success: false,
        error: `找不到范围选择下拉框，需要2个，找到${comboboxes.length}个`,
        duration: Date.now() - startTime,
      };
    }

    // 1. 选择最小值
    await this.click(comboboxes[0].ref);
    await this.delay(300);

    // 滚动查找最小值选项
    const minResult = await this.scrollAndFindOption(minValue);
    if (!minResult.success) {
      return { ...minResult, duration: Date.now() - startTime };
    }
    await this.delay(200);

    // 2. 选择最大值
    const snapshot2 = await this.snapshot();
    const updatedComboboxes = snapshot2.elements.filter((el) => el.type === 'combobox');
    const maxBox = updatedComboboxes[1] || comboboxes[1];

    await this.click(maxBox.ref);
    await this.delay(300);

    // 滚动查找最大值选项
    const maxResult = await this.scrollAndFindOption(maxValue);
    if (!maxResult.success) {
      return { ...maxResult, duration: Date.now() - startTime };
    }
    await this.delay(200);

    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 点击标签（用于 tags 类型控件）
   */
  async clickTag(tagText: string): Promise<FillResult> {
    const startTime = Date.now();
    const clicked = await this.clickByText(tagText);

    if (!clicked) {
      return {
        success: false,
        error: `找不到标签: ${tagText}`,
        duration: Date.now() - startTime,
      };
    }

    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 执行搜索
   */
  async executeSearch(): Promise<void> {
    await this.clickByText('搜索');
    await this.wait('networkidle');
  }

  /**
   * 清空所有筛选条件
   */
  async clearAllFilters(): Promise<void> {
    await this.clickByText('清空');
    await this.delay(300);
  }

  /**
   * 输入搜索词并点选首位推荐项
   *
   * 用于处理"搜索建议型"控件（毕业学校、专业、家乡等）
   * 流程：输入 → 等待推荐列表 → 点击首位匹配项
   *
   * @param placeholder 输入框占位符
   * @param value 搜索值
   * @param options 配置选项
   */
  async fillAndSelectFirstSuggest(
    placeholder: string,
    value: string,
    options?: { closeAfterSelect?: boolean }
  ): Promise<FillResult> {
    const startTime = Date.now();

    // 1. 查找输入框并输入
    const { elements, raw } = await this.snapshot();

    // 调试：打印所有 textbox
    if (this.config.debug) {
      const textboxes = elements.filter(el => el.type === 'textbox');
      console.log(`[fillAndSelectFirstSuggest] 找到 ${textboxes.length} 个 textbox:`);
      textboxes.forEach(el => console.log(`  - "${el.text}"`));
    }

    const input = elements.find((el) =>
      el.type === 'textbox' &&
      el.text?.toLowerCase().includes(placeholder.toLowerCase())
    );

    if (!input) {
      return {
        success: false,
        error: `找不到输入框: ${placeholder}`,
        duration: Date.now() - startTime,
      };
    }

    await this.fill(input.ref, value);

    // 2. 等待推荐列表出现
    await this.delay(500);

    // 3. 点选首位推荐项
    const suggestSnapshot = await this.snapshot();
    const firstSuggest = suggestSnapshot.elements.find((el) =>
      el.type === 'clickable' &&
      (el.text === value || el.text?.includes(value)) &&
      el.text !== placeholder &&
      el.text !== value + '...' // 排除加载状态
    );

    if (!firstSuggest) {
      return {
        success: false,
        error: `未找到推荐项: ${value}`,
        duration: Date.now() - startTime,
      };
    }

    await this.click(firstSuggest.ref);
    await this.delay(200);

    // 4. 可选：点空白关闭面板
    if (options?.closeAfterSelect) {
      await this.clickBlankArea();
    }

    return {
      success: true,
      duration: Date.now() - startTime,
    };
  }

  /**
   * 点击搜索条件模块内的空白区域关闭下拉面板
   *
   * 用于关闭不需要点击"确定"的面板（专业、家乡等）
   */
  async clickBlankArea(): Promise<void> {
    const snapshot = await this.snapshot();

    // 查找通用容器或空白区域（排除按钮和输入框）
    const blankArea = snapshot.elements.find((el) =>
      el.type === 'generic' &&
      !el.text?.includes('确定') &&
      !el.text?.includes('取消') &&
      !el.text?.includes('搜索') &&
      el.text?.length === 0 // 空白区域通常没有文本
    );

    if (blankArea) {
      await this.click(blankArea.ref);
      await this.delay(200);
    }
  }

  /**
   * 等待并选择下拉选项（带滚动）
   *
   * 专门用于范围选择控件（年龄、期望月薪）
   * 先尝试直接查找，找不到则用 JS 滚动下拉列表
   *
   * @param targetText 目标选项文本（如 "25岁", "40K"）
   * @param maxScrolls 最大滚动次数
   */
  async selectDropdownOptionWithScroll(targetText: string, maxScrolls: number = 5): Promise<FillResult> {
    const startTime = Date.now();
    const shortTarget = targetText.replace('岁', '').replace('K', '');

    // 1. 先尝试直接查找并点击
    let snapshot = await this.snapshot();
    let option = snapshot.elements.find((el) =>
      el.text === targetText || el.text === shortTarget
    );

    if (option) {
      await this.click(option.ref);
      return { success: true, duration: Date.now() - startTime };
    }

    // 2. 需要滚动查找 - 使用 JS 在下拉框容器内滚动
    const scrollJs = `(function() {
      // 找到包含年龄/薪资选项的滚动容器
      const containers = document.querySelectorAll('[style*="overflow"]');
      for (const container of containers) {
        const text = container.textContent || '';
        const hasOption = text.includes('16岁') || text.includes('1K') ||
                          text.includes('17岁') || text.includes('2K');
        if (hasOption && container.scrollHeight > container.clientHeight) {
          container.scrollTop += 150;
          return 'scrolled';
        }
      }
      return 'no-scrollable-container';
    })()`;

    for (let i = 0; i < maxScrolls; i++) {
      // 用 JS 滚动
      const scrollResult = await this.eval(scrollJs);
      if (this.config.debug) {
        console.log(`[selectDropdownOptionWithScroll] JS scroll result: ${scrollResult}`);
      }
      await this.delay(300);

      // 重新获取快照
      snapshot = await this.snapshot();
      option = snapshot.elements.find((el) =>
        el.text === targetText || el.text === shortTarget
      );

      if (option) {
        await this.click(option.ref);
        return { success: true, duration: Date.now() - startTime };
      }
    }

    return {
      success: false,
      error: `滚动 ${maxScrolls} 次后仍未找到选项: ${targetText}`,
      duration: Date.now() - startTime,
    };
  }
}

// 默认执行器实例
export const defaultBrowserExecutor = new BrowserExecutor();
export const defaultMaimaiExecutor = new MaimaiFormExecutor();
