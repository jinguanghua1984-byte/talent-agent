import type { Skill, SkillMeta } from "../types/skill.ts";

/**
 * Skill 构建器
 * 用于流畅地创建 Skill 定义
 */
export class SkillBuilder {
  private skill: Partial<Skill> = {};

  meta(meta: Partial<SkillMeta>): this {
    this.skill = { ...this.skill, ...meta };
    return this;
  }

  id(id: string): this {
    this.skill.id = id;
    return this;
  }

  name(name: string): this {
    this.skill.name = name;
    return this;
  }

  description(description: string): this {
    this.skill.description = description;
    return this;
  }

  version(version: string): this {
    this.skill.version = version;
    return this;
  }

  category(category: Skill["category"]): this {
    this.skill.category = category;
    return this;
  }

  platforms(...platforms: Skill["platforms"]): this {
    this.skill.platforms = platforms;
    return this;
  }

  prompt(prompt: string): this {
    this.skill.prompt = prompt;
    return this;
  }

  tags(...tags: string[]): this {
    this.skill.tags = tags;
    return this;
  }

  build(): Skill {
    if (!this.skill.id) throw new Error("Skill id is required");
    if (!this.skill.name) throw new Error("Skill name is required");
    if (!this.skill.description) throw new Error("Skill description is required");
    if (!this.skill.version) throw new Error("Skill version is required");
    if (!this.skill.category) throw new Error("Skill category is required");
    if (!this.skill.platforms) throw new Error("Skill platforms is required");
    if (!this.skill.prompt) throw new Error("Skill prompt is required");

    return this.skill as Skill;
  }
}

/**
 * 创建 Skill 构建器
 */
export function defineSkill(): SkillBuilder {
  return new SkillBuilder();
}
