/**
 * 脉脉候选人抓取 - 类型定义
 */

// 工作履历
export interface WorkHistory {
  timeRange: string;
  company: string;
  position: string;
  description?: string;
}

// 教育履历
export interface EducationHistory {
  timeRange: string;
  school: string;
  major: string;
  degree: string;
}

// 候选人信息
export interface Candidate {
  // 基础信息（列表页可获取）
  name: string;
  activeStatus: string; // 活跃度：刚刚活跃、今日活跃、3日内活跃等
  age?: number;
  workYears?: number;
  education?: string;
  workLocation?: string;
  expectedLocation?: string;
  expectedSalary?: string;
  expectedPosition?: string;

  // 详情页完整信息
  careerTags: string[]; // 职业标签
  workHistory: WorkHistory[]; // 工作履历
  educationHistory: EducationHistory[]; // 教育履历

  // 元信息
  sourceUrl?: string; // 候选人详情页链接
  scrapedAt: string; // 抓取时间
}

// 淘汰原因
export interface FilterReason {
  reason: string;
  count: number;
}

// 抓取结果
export interface ScrapeResult {
  // 候选人列表（通过筛选）
  candidates: Candidate[];

  // 统计信息
  totalCount: number; // 总抓取数量
  filteredCount: number; // 淘汰数量
  filterReasons: FilterReason[]; // 淘汰原因分布

  // 搜索和筛选条件
  searchConditions: Record<string, string>; // 搜索条件
  filterRules: string[]; // 筛选规则

  // 元信息
  scrapedAt: string; // 抓取完成时间
  duration: string; // 抓取耗时
}

// 搜索条件（12个字段）
export interface SearchConditions {
  city?: string; // 城市地区
  education?: string; // 学历要求
  workYears?: string; // 工作年限
  company?: string; // 就职公司
  position?: string; // 职位名称
  industry?: string; // 行业方向
  school?: string; // 毕业学校
  major?: string; // 专业
  gender?: 'male' | 'female' | 'any'; // 性别
  ageRange?: string; // 年龄范围，如 "25-35"
  expectedSalary?: string; // 期望月薪
  hometown?: string; // 家乡
}

// 筛选规则（语义描述）
export interface FilterRule {
  description: string; // 自然语言描述
  // 可选：解析后的结构化条件
  parsed?: {
    type: 'job_hops' | 'education' | 'salary' | 'experience' | 'custom';
    params?: Record<string, unknown>;
  };
}

// 抓取配置
export interface ScraperConfig {
  // 搜索条件
  searchConditions: SearchConditions;

  // 筛选规则
  filterRules: FilterRule[];

  // 并发设置
  concurrency: number; // 同时打开的详情页数量，默认 2-3

  // 反爬设置
  requestDelay: [number, number]; // 请求间隔范围 [min, max] 秒

  // 输出设置
  outputPath?: string; // 自定义输出路径
}

// 抓取状态
export interface ScraperState {
  phase: 'login' | 'search' | 'filter_setup' | 'scraping' | 'output' | 'error' | 'complete';
  currentPage: number;
  totalCandidates: number;
  passedCandidates: number;
  filteredCandidates: number;
  error?: string;
}
