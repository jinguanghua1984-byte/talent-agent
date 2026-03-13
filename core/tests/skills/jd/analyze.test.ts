import { describe, it, expect, beforeEach } from 'vitest';
import { skillRegistry } from '../../../src/skills/registry.ts';
import { jdAnalyzeSkill } from '../../../src/skills/jd/analyze.skill.ts';

describe('jd-analyze skill', () => {
  beforeEach(() => {
    skillRegistry.clear();
    // 重新注册，因为每个测试前清空了注册表
    skillRegistry.register(jdAnalyzeSkill);
  });

  it('should be defined correctly', () => {
    expect(jdAnalyzeSkill.id).toBe('jd-analyze');
    expect(jdAnalyzeSkill.name).toBe('JD 分析');
    expect(jdAnalyzeSkill.category).toBe('jd');
  });

  it('should be registered', () => {
    expect(skillRegistry.has('jd-analyze')).toBe(true);
  });

  it('should have prompt template', () => {
    expect(jdAnalyzeSkill.prompt).toContain('JD 分析');
    expect(jdAnalyzeSkill.prompt).toContain('{{jd}}');
  });

  it('should support multiple platforms', () => {
    expect(jdAnalyzeSkill.platforms).toContain('claude-code');
    expect(jdAnalyzeSkill.platforms).toContain('cursor');
    expect(jdAnalyzeSkill.platforms).toContain('continue');
  });
});
