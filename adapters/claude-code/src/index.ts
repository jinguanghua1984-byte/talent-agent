/**
 * Talent Agent - Claude Code Adapter
 * 猎头业务 AI 工具集的 Claude Code 适配器
 */

import { skillRegistry, resumeParseSkill, jdAnalyzeSkill } from '@talent-agent/core';
export * from './commands/index';

// 确保所有 skills 已注册
void resumeParseSkill;
void jdAnalyzeSkill;

// 导出所有可用的 skills
export const availableSkills = skillRegistry.getAll();

// 导出适配器信息
export const adapterInfo = {
  name: 'talent-agent',
  version: '0.1.0',
  platform: 'claude-code' as const,
  skillCount: skillRegistry.getAll().length,
};
