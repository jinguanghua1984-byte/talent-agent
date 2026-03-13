import { describe, it, expect, beforeEach } from 'vitest';
import { skillRegistry } from '../../src/skills/registry.ts';
import { defineSkill } from '../../src/skills/base.ts';

describe('SkillRegistry', () => {
  beforeEach(() => {
    skillRegistry.clear();
  });

  it('should register and retrieve a skill', () => {
    const skill = defineSkill()
      .id('test')
      .name('Test')
      .description('Test skill')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code')
      .prompt('Test prompt')
      .build();

    skillRegistry.register(skill);

    expect(skillRegistry.has('test')).toBe(true);
    expect(skillRegistry.get('test')).toEqual(skill);
  });

  it('should throw on duplicate registration', () => {
    const skill = defineSkill()
      .id('duplicate')
      .name('Duplicate')
      .description('Test')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code')
      .prompt('Test')
      .build();

    skillRegistry.register(skill);

    expect(() => skillRegistry.register(skill)).toThrow('already registered');
  });

  it('should filter by category', () => {
    const resumeSkill = defineSkill()
      .id('resume-1')
      .name('Resume')
      .description('Test')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code')
      .prompt('Test')
      .build();

    const jdSkill = defineSkill()
      .id('jd-1')
      .name('JD')
      .description('Test')
      .version('1.0.0')
      .category('jd')
      .platforms('claude-code')
      .prompt('Test')
      .build();

    skillRegistry.register(resumeSkill);
    skillRegistry.register(jdSkill);

    expect(skillRegistry.getByCategory('resume')).toHaveLength(1);
    expect(skillRegistry.getByCategory('jd')).toHaveLength(1);
  });

  it('should filter by platform', () => {
    const skill = defineSkill()
      .id('multi-platform')
      .name('Multi')
      .description('Test')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code', 'cursor')
      .prompt('Test')
      .build();

    skillRegistry.register(skill);

    expect(skillRegistry.getByPlatform('claude-code')).toHaveLength(1);
    expect(skillRegistry.getByPlatform('cursor')).toHaveLength(1);
    expect(skillRegistry.getByPlatform('continue')).toHaveLength(0);
  });
});
