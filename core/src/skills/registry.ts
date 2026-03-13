import type { Skill } from '../types/skill.ts';

/**
 * Skill 注册表
 * 管理所有已注册的 Skills
 */
class SkillRegistry {
  private skills: Map<string, Skill> = new Map();

  /**
   * 注册一个 Skill
   */
  register(skill: Skill): void {
    if (this.skills.has(skill.id)) {
      throw new Error(`Skill with id "${skill.id}" already registered`);
    }
    this.skills.set(skill.id, skill);
  }

  /**
   * 获取一个 Skill
   */
  get(id: string): Skill | undefined {
    return this.skills.get(id);
  }

  /**
   * 获取所有 Skills
   */
  getAll(): Skill[] {
    return Array.from(this.skills.values());
  }

  /**
   * 按分类获取 Skills
   */
  getByCategory(category: Skill['category']): Skill[] {
    return this.getAll().filter((s) => s.category === category);
  }

  /**
   * 按平台获取 Skills
   */
  getByPlatform(platform: Skill['platforms'][number]): Skill[] {
    return this.getAll().filter((s) => s.platforms.includes(platform));
  }

  /**
   * 检查 Skill 是否存在
   */
  has(id: string): boolean {
    return this.skills.has(id);
  }

  /**
   * 清空注册表
   */
  clear(): void {
    this.skills.clear();
  }
}

// 单例导出
export const skillRegistry = new SkillRegistry();
