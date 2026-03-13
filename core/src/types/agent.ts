import type { Skill } from './skill';

/**
 * Agent 元数据
 */
export interface AgentMeta {
  id: string;
  name: string;
  description: string;
  version: string;
}

/**
 * Agent 完整定义
 */
export interface Agent extends AgentMeta {
  /** 系统提示词 */
  systemPrompt: string;
  /** 可用的 Skills */
  skills: Skill[];
  /** 最大迭代次数 */
  maxIterations?: number;
}
