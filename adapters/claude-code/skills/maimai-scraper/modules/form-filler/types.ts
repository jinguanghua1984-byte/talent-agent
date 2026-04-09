/**
 * 表单填充模块 - 类型定义
 *
 * 定义 Excel 列、表单控件、填充结果等核心类型
 */

// ============ 控件类型 ============

/** 支持的控件类型 */
export type ControlType =
  | 'text' // 文本输入框
  | 'select' // 下拉单选
  | 'cascade' // 级联选择
  | 'tags' // 标签输入（带智能提示）
  | 'range'; // 范围滑块

/** 控件配置 */
export interface ControlConfig {
  /** 控件类型 */
  type: ControlType;

  /** 控件名称（显示名） */
  name: string;

  /** 控件选择器 */
  selector: string;

  /** 额外配置（不同控件类型有不同的配置） */
  options?: TextOptions | SelectOptions | CascadeOptions | TagsOptions | RangeOptions;
}

/** 文本输入配置 */
export interface TextOptions {
  /** 定位策略：'selector' | 'text' */
  locateStrategy?: 'selector' | 'text';
  /** 通过文本定位时的关键词 */
  locateText?: string;
  /** 输入框选择器（placeholder） */
  inputSelector?: string;
  /** 是否需要点选首位推荐项（专业、家乡等） */
  needsSuggestSelect?: boolean;
  /** 选择推荐项后是否点击空白区域关闭面板 */
  closeByBlankClick?: boolean;
}

/** 下拉单选配置 */
export interface SelectOptions {
  /** 选项值映射：显示文本 -> 实际值 */
  valueMap?: Record<string, string>;
  /** 选项选择器 */
  optionSelector?: string;
  /** 定位策略：'selector' | 'text' */
  locateStrategy?: 'selector' | 'text';
  /** 通过文本定位时的关键词 */
  locateText?: string;
  /** 是否需要点击确定按钮 */
  needsConfirm?: boolean;
}

/** 级联选择配置 */
export interface CascadeOptions {
  /** 级联层级 */
  levels: number;
  /** 各层级选择器 */
  levelSelectors?: string[];
  /** 定位策略：'selector' | 'text' */
  locateStrategy?: 'selector' | 'text';
  /** 通过文本定位时的关键词 */
  locateText?: string;
  /** 搜索输入框选择器 */
  inputSelector?: string;
  /** 复选框选项（如：期望/现居） */
  checkboxOptions?: string[];
  /** 是否需要点击确定按钮 */
  needsConfirm?: boolean;
}

/** 标签输入配置 */
export interface TagsOptions {
  /** 智能提示项选择器 */
  suggestionSelector?: string;
  /** 是否支持多值 */
  multiple?: boolean;
  /** 分隔符（默认逗号） */
  separator?: string;
  /** 定位策略：'selector' | 'text' */
  locateStrategy?: 'selector' | 'text';
  /** 通过文本定位时的关键词 */
  locateText?: string;
  /** 搜索输入框选择器 */
  inputSelector?: string;
  /** 复选框选项（如：正任职/曾任职） */
  checkboxOptions?: string[];
  /** 热门标签 */
  hotTags?: string[];
}

/** 范围滑块配置 */
export interface RangeOptions {
  /** 最小值选择器 */
  minSelector?: string;
  /** 最大值选择器 */
  maxSelector?: string;
  /** 值格式：'25-35' 或 '25K-40K' */
  format?: 'number' | 'salary';
  /** 定位策略：'selector' | 'text' */
  locateStrategy?: 'selector' | 'text';
  /** 通过文本定位时的关键词 */
  locateText?: string;
}

// ============ Excel 相关 ============

/** Excel 行数据（列名 -> 值） */
export type ExcelRow = Record<string, string | number | undefined>;

/** Excel 读取结果 */
export interface ExcelReadResult {
  /** 文件路径 */
  filePath: string;

  /** 总行数（不含表头） */
  totalRows: number;

  /** 表头列名 */
  headers: string[];

  /** 行数据 */
  rows: ExcelRow[];

  /** 读取错误 */
  errors?: string[];
}

/** 解析后的搜索条件行 */
export interface ParsedSearchRow {
  /** 行号（1-indexed，不含表头） */
  rowNumber: number;

  /** 关键词 */
  keywords?: string[];

  /** 关键词模式：AND 或 OR */
  keywordMode: 'AND' | 'OR';

  /** 搜索条件（字段名 -> 值） */
  conditions: Record<string, string | string[]>;

  /** 筛选规则（原始描述） */
  filterRules: string[];

  /** 原始行数据 */
  raw: ExcelRow;
}

// ============ 填充操作 ============

/** 填充操作 */
export interface FillOperation {
  /** 字段名 */
  field: string;

  /** 控件配置 */
  control: ControlConfig;

  /** 要填充的值 */
  value: string | string[];

  /** 操作类型 */
  action: 'fill' | 'select' | 'click';
}

/** 单个字段填充结果 */
export interface FieldFillResult {
  /** 字段名 */
  field: string;

  /** 是否成功 */
  success: boolean;

  /** 填充的值 */
  value?: string | string[];

  /** 错误信息 */
  error?: string;

  /** 耗时（毫秒） */
  duration?: number;
}

/** 单行填充结果 */
export interface RowFillResult {
  /** 行号 */
  rowNumber: number;

  /** 各字段结果 */
  fields: FieldFillResult[];

  /** 成功字段数 */
  successCount: number;

  /** 失败字段数 */
  failCount: number;

  /** 总耗时（毫秒） */
  duration: number;
}

/** 整体填充报告 */
export interface FillReport {
  /** Excel 文件路径 */
  filePath: string;

  /** 总行数 */
  totalRows: number;

  /** 处理行数 */
  processedRows: number;

  /** 成功行数（所有字段都成功） */
  successRows: number;

  /** 部分成功行数 */
  partialRows: number;

  /** 失败行数 */
  failedRows: number;

  /** 各行结果 */
  rowResults: RowFillResult[];

  /** 统计：各字段成功率 */
  fieldStats: Record<string, { success: number; fail: number }>;

  /** 总耗时（毫秒） */
  duration: number;

  /** 生成时间 */
  generatedAt: string;
}

// ============ 填充器接口 ============

/** 填充器接口 */
export interface IFiller {
  /** 控件类型 */
  readonly type: ControlType;

  /**
   * 填充控件
   * @param config 控件配置
   * @param value 要填充的值
   * @returns 填充结果
   */
  fill(config: ControlConfig, value: string | string[]): Promise<FieldFillResult>;
}

// ============ 调试配置 ============

/** 调试选项 */
export interface DebugOptions {
  /** 只解析 Excel，不操作页面 */
  dryRun?: boolean;

  /** 只调试指定行 */
  row?: number;

  /** 只调试指定字段 */
  onlyFields?: string[];

  /** 每步暂停确认 */
  stepByStep?: boolean;

  /** 放慢操作速度 */
  slow?: boolean;

  /** 操作间隔（毫秒） */
  delay?: number;
}

// ============ 字段映射 ============

/** Excel 列名到表单字段的映射 */
export interface FieldMapping {
  /** Excel 列名 */
  excelColumn: string;

  /** 表单字段名 */
  formField: string;

  /** 控件类型 */
  controlType: ControlType;

  /** 值转换函数 */
  transform?: (value: string) => string | string[];

  /** 是否必需 */
  required?: boolean;
}

/** 字段映射配置 */
export const FIELD_MAPPINGS: FieldMapping[] = [
  { excelColumn: '关键词', formField: 'keyword', controlType: 'text' },
  { excelColumn: '关键词模式', formField: 'keywordMode', controlType: 'select' },
  { excelColumn: '城市地区', formField: 'city', controlType: 'cascade' },
  { excelColumn: '学历要求', formField: 'education', controlType: 'select' },
  { excelColumn: '工作年限', formField: 'workYears', controlType: 'select' },
  { excelColumn: '就职公司', formField: 'company', controlType: 'tags' },
  { excelColumn: '职位名称', formField: 'position', controlType: 'text' },
  { excelColumn: '行业方向', formField: 'industry', controlType: 'cascade' },
  { excelColumn: '毕业学校', formField: 'school', controlType: 'tags' },
  { excelColumn: '专业', formField: 'major', controlType: 'text' },
  { excelColumn: '性别', formField: 'gender', controlType: 'select' },
  { excelColumn: '年龄', formField: 'age', controlType: 'range' },
  { excelColumn: '期待月薪', formField: 'expectedSalary', controlType: 'range' },
  { excelColumn: '家乡', formField: 'hometown', controlType: 'cascade' },
];
