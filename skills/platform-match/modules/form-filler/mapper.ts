/**
 * 字段映射器
 *
 * 将 Excel 列名映射到表单控件配置
 */

import type {
  ControlConfig,
  ControlType,
  ExcelRow,
  FieldMapping,
  FillOperation,
  ParsedSearchRow,
} from './types';
import { FIELD_MAPPINGS } from './types';

/**
 * 控件选择器配置
 *
 * 基于 2026-03-21 实际页面分析
 * 使用语义化定位策略：优先通过文本内容定位
 *
 * agent-browser 定位方式：
 * - find text "城市地区" click  - 通过文本点击
 * - snapshot -i 后使用 @e1, @e2 等 ref
 */
export const CONTROL_SELECTORS: Record<string, ControlConfig> = {
  keyword: {
    type: 'text',
    name: '关键词',
    // 主搜索框: textbox "按职位/公司等搜人才"
    selector: 'input[placeholder*="搜人才"], input[placeholder*="职位"]',
    options: {
      locateStrategy: 'text',
      locateText: '按职位/公司等搜人才',
    },
  },
  keywordMode: {
    type: 'select',
    name: '关键词模式',
    // 点击切换: clickable "满足所有关键词搜索"
    selector: '[class*="keyword-mode"], [class*="search-mode"]',
    options: {
      valueMap: {
        AND: 'and',
        OR: 'or',
      },
      locateStrategy: 'text',
      locateText: '满足所有关键词搜索',
    },
  },
  city: {
    type: 'cascade',
    name: '城市地区',
    // 点击展开: clickable "城市地区"
    // 搜索框: textbox "请输入城市地区"
    // 复选框: checkbox "期望", checkbox "现居"
    selector: '[class*="city-select"], [class*="location"]',
    options: {
      levels: 2,
      locateStrategy: 'text',
      locateText: '城市地区',
      inputSelector: 'input[placeholder*="城市地区"]',
      checkboxOptions: ['期望', '现居'],
    },
  },
  education: {
    type: 'select',
    name: '学历要求',
    // 点击展开: clickable "学历要求"
    // 选项: clickable "专科及以上", "本科及以上", "硕士及以上", "博士", "不限"
    // 确定按钮: clickable "确定"
    selector: '[class*="education-select"], [class*="degree"]',
    options: {
      valueMap: {
        '专科及以上': '1',
        '本科及以上': '2',
        '硕士及以上': '3',
        '博士': '4',
        '不限': '0',
      },
      locateStrategy: 'text',
      locateText: '学历要求',
      needsConfirm: true,
    },
  },
  workYears: {
    type: 'select',
    name: '工作年限',
    // 点击展开: clickable "工作年限"
    // 选项: clickable "在校/应届", "1年以内", "1-3年", "3-5年", "5-10年", "10年以上", "不限"
    // 确定按钮: clickable "确定"
    selector: '[class*="work-years"], [class*="experience"]',
    options: {
      valueMap: {
        '在校/应届': '0',
        '1年以内': '1',
        '1-3年': '2',
        '3-5年': '3',
        '5-10年': '4',
        '10年以上': '5',
        '不限': '6',
      },
      locateStrategy: 'text',
      locateText: '工作年限',
      needsConfirm: true,
    },
  },
  company: {
    type: 'tags',
    name: '就职公司',
    // 点击展开: clickable "就职公司"
    // 搜索框: textbox "请输入就职公司"
    // 复选框: checkbox "正任职", checkbox "曾任职"
    // 热门标签: clickable "BAT", "TMDJ", "一线互联网公司", "百度", "阿里"...
    selector: '[class*="company-input"], [class*="employer"]',
    options: {
      multiple: true,
      locateStrategy: 'text',
      locateText: '就职公司',
      inputSelector: 'input[placeholder*="就职公司"]',
      checkboxOptions: ['正任职', '曾任职'],
      hotTags: ['BAT', 'TMDJ', '一线互联网公司', '二线互联网公司'],
    },
  },
  position: {
    type: 'tags',
    name: '职位名称',
    // 点击展开: clickable "职位名称"
    // 搜索框: textbox "请输入职位名称"
    // 热门标签: clickable "运营", "销售", "算法", "产品经理", "前端开发", "后端开发"...
    selector: '[class*="position-input"], [class*="job-title"]',
    options: {
      multiple: true,
      locateStrategy: 'text',
      locateText: '职位名称',
      inputSelector: 'input[placeholder*="职位名称"]',
      hotTags: ['运营', '销售', '算法', '产品经理', '前端开发', '后端开发', '数据分析'],
    },
  },
  industry: {
    type: 'cascade',
    name: '行业方向',
    // 点击展开: clickable "行业方向"
    // 搜索框: textbox "搜索行业方向"
    // 一级行业: clickable "IT/互联网/游戏", "金融业", "制造业"...
    // 二级行业: clickable "新零售", "计算机软件", "互联网"...
    // 确定按钮: clickable "确定"
    selector: '[class*="industry-select"], [class*="sector"]',
    options: {
      levels: 2,
      locateStrategy: 'text',
      locateText: '行业方向',
      inputSelector: 'input[placeholder*="行业方向"]',
      needsConfirm: true,
    },
  },
  school: {
    type: 'tags',
    name: '毕业学校',
    // 点击展开: clickable "毕业学校"
    // 搜索框: textbox "请输入毕业学校"
    // 类型标签: clickable "985", "211", "QS排名Top500", "海外Top500"
    // 热门学校: clickable "北京大学", "清华大学", "复旦大学"...
    selector: '[class*="school-input"], [class*="university"]',
    options: {
      multiple: true,
      locateStrategy: 'text',
      locateText: '毕业学校',
      inputSelector: 'input[placeholder*="毕业学校"]',
      hotTags: ['985', '211', 'QS排名Top500', '海外Top500'],
    },
  },
  major: {
    type: 'text',
    name: '专业',
    // 点击展开: clickable "专业"
    // 搜索框: textbox "请输入专业"
    selector: '[class*="major-input"], [class*="specialty"]',
    options: {
      locateStrategy: 'text',
      locateText: '专业',
      inputSelector: 'input[placeholder*="专业"]',
    },
  },
  gender: {
    type: 'select',
    name: '性别',
    // 点击展开: clickable "性别"
    // 选项: clickable "不限", "男", "女"
    selector: '[class*="gender-select"], [class*="sex"]',
    options: {
      valueMap: {
        '不限': '0',
        '男': '1',
        '女': '2',
      },
      locateStrategy: 'text',
      locateText: '性别',
    },
  },
  age: {
    type: 'range',
    name: '年龄',
    // 点击展开: clickable "年龄"
    // 两个下拉框: combobox (最小年龄), combobox (最大年龄)
    selector: '[class*="age-range"], [class*="age-select"]',
    options: {
      format: 'number',
      locateStrategy: 'text',
      locateText: '年龄',
    },
  },
  expectedSalary: {
    type: 'range',
    name: '期待月薪',
    // 点击展开: clickable "期望月薪"
    // 两个下拉框: combobox (最小薪资), combobox (最大薪资)
    selector: '[class*="salary-range"], [class*="expected-salary"]',
    options: {
      format: 'salary',
      locateStrategy: 'text',
      locateText: '期望月薪',
    },
  },
  hometown: {
    type: 'text',
    name: '家乡',
    // 点击展开: clickable "家乡"
    // 搜索框: textbox "请输入家乡所在城市"
    selector: '[class*="hometown-input"], [class*="native-place"]',
    options: {
      locateStrategy: 'text',
      locateText: '家乡',
      inputSelector: 'input[placeholder*="家乡"]',
    },
  },
};

/**
 * 字段映射器类
 */
export class FieldMapper {
  private mappings: Map<string, FieldMapping> = new Map();
  private selectors: Map<string, ControlConfig> = new Map();

  constructor(
    customMappings?: FieldMapping[],
    customSelectors?: Record<string, ControlConfig>
  ) {
    // 加载默认映射
    for (const mapping of FIELD_MAPPINGS) {
      this.mappings.set(mapping.excelColumn, mapping);
    }

    // 加载自定义映射
    if (customMappings) {
      for (const mapping of customMappings) {
        this.mappings.set(mapping.excelColumn, mapping);
      }
    }

    // 加载选择器配置
    const selectors = { ...CONTROL_SELECTORS, ...customSelectors };
    for (const [field, config] of Object.entries(selectors)) {
      this.selectors.set(field, config);
    }
  }

  /**
   * 获取字段映射
   */
  getMapping(excelColumn: string): FieldMapping | undefined {
    return this.mappings.get(excelColumn);
  }

  /**
   * 获取控件配置
   */
  getControlConfig(formField: string): ControlConfig | undefined {
    return this.selectors.get(formField);
  }

  /**
   * 获取所有 Excel 列名
   */
  getExcelColumns(): string[] {
    return Array.from(this.mappings.keys());
  }

  /**
   * 解析单行 Excel 数据
   */
  parseRow(row: ExcelRow, rowNumber: number): ParsedSearchRow {
    const conditions: Record<string, string | string[]> = {};
    let keywords: string[] = [];
    let keywordMode: 'AND' | 'OR' = 'AND';
    const filterRules: string[] = [];

    for (const [excelColumn, value] of Object.entries(row)) {
      if (value === undefined || value === '') continue;

      const mapping = this.mappings.get(excelColumn);
      if (!mapping) {
        // 未知列，可能是筛选规则
        if (excelColumn === '筛选规则') {
          const rules = String(value).split(';').filter(Boolean);
          filterRules.push(...rules);
        }
        continue;
      }

      // 特殊处理关键词
      if (excelColumn === '关键词') {
        keywords = String(value)
          .split(',')
          .map((k) => k.trim())
          .filter(Boolean);
        continue;
      }

      // 特殊处理关键词模式
      if (excelColumn === '关键词模式') {
        const mode = String(value).toUpperCase();
        keywordMode = mode === 'OR' ? 'OR' : 'AND';
        continue;
      }

      // 特殊处理筛选规则
      if (excelColumn === '筛选规则') {
        const rules = String(value)
          .split(';')
          .map((r) => r.trim())
          .filter(Boolean);
        filterRules.push(...rules);
        continue;
      }

      // 常规字段
      let processedValue: string | string[] = String(value);

      // 应用值转换
      if (mapping.transform) {
        processedValue = mapping.transform(String(value));
      }

      // 多值字段处理
      if (mapping.controlType === 'tags' || mapping.controlType === 'cascade') {
        if (typeof processedValue === 'string' && processedValue.includes(',')) {
          processedValue = processedValue.split(',').map((v) => v.trim());
        }
      }

      conditions[mapping.formField] = processedValue;
    }

    return {
      rowNumber,
      keywords,
      keywordMode,
      conditions,
      filterRules,
      raw: row,
    };
  }

  /**
   * 生成填充操作列表
   */
  generateFillOperations(parsedRow: ParsedSearchRow): FillOperation[] {
    const operations: FillOperation[] = [];

    // 添加关键词操作
    if (parsedRow.keywords.length > 0) {
      const config = this.selectors.get('keyword');
      if (config) {
        operations.push({
          field: 'keyword',
          control: config,
          value: parsedRow.keywords.join(','),
          action: 'fill',
        });
      }
    }

    // 添加其他条件操作
    for (const [field, value] of Object.entries(parsedRow.conditions)) {
      const config = this.selectors.get(field);
      if (!config) continue;

      operations.push({
        field,
        control: config,
        value,
        action: this.getActionForControlType(config.type),
      });
    }

    return operations;
  }

  /**
   * 根据控件类型获取操作类型
   */
  private getActionForControlType(type: ControlType): 'fill' | 'select' | 'click' {
    switch (type) {
      case 'text':
      case 'tags':
        return 'fill';
      case 'select':
      case 'cascade':
      case 'range':
        return 'select';
      default:
        return 'fill';
    }
  }
}

// 默认映射器实例
export const defaultFieldMapper = new FieldMapper();
