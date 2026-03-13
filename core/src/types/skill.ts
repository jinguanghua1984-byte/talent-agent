/**
 * Skill 分类
 */
export type SkillCategory = "resume" | "jd" | "communication" | "analysis";

/**
 * 支持的平台
 */
export type Platform = "claude-code" | "cursor" | "continue";

/**
 * Skill 元数据
 */
export interface SkillMeta {
  /** 唯一标识符 */
  id: string;
  /** 显示名称 */
  name: string;
  /** 描述 */
  description: string;
  /** 版本号 */
  version: string;
  /** 分类 */
  category: SkillCategory;
  /** 支持的平台 */
  platforms: Platform[];
  /** 标签 */
  tags?: string[];
}

/**
 * 工具定义
 */
export interface Tool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

/**
 * 示例定义
 */
export interface Example {
  input: string;
  output: string;
  explanation?: string;
}

/**
 * Skill 完整定义
 */
export interface Skill extends SkillMeta {
  /** 提示词模板 */
  prompt: string;
  /** 可用工具 */
  tools?: Tool[];
  /** 使用示例 */
  examples?: Example[];
}
