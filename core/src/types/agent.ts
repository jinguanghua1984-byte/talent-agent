import type { Platform } from "./skill.ts";

/** Agent 颜色标识 */
export type AgentColor = "blue" | "cyan" | "green" | "yellow" | "magenta" | "red";

/** Agent 模型选择 */
export type AgentModel = "inherit" | "sonnet" | "opus" | "haiku";

/** Agent 元数据 */
export interface AgentMeta {
  /** 唯一标识符 (3-50字符，小写字母、数字、连字符) */
  id: string;
  /** 显示名称 */
  name: string;
  /** 描述，包含触发条件和示例 */
  description: string;
  /** 版本号 */
  version: string;
  /** 使用的模型 */
  model: AgentModel;
  /** UI 颜色标识 */
  color: AgentColor;
  /** 支持的平台 */
  platforms: Platform[];
}

/**
 * Agent 工具配置
 * 轻量级引用（仅名称+可选描述），运行时按名称解析实际工具定义
 */
export interface AgentTool {
  name: string;
  description?: string;
}

/**
 * Agent 触发示例
 * 使用对话格式（context/user/assistant），适合多轮交互场景
 */
export interface AgentExample {
  context: string;
  user: string;
  assistant: string;
  commentary: string;
}

/** Agent 完整定义 */
export interface Agent extends AgentMeta {
  systemPrompt: string;
  tools?: AgentTool[];
  skillIds?: string[];
  examples?: AgentExample[];
  maxIterations?: number;
}
