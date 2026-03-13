import { describe, it, expect } from "vitest";
import type { Skill } from "../../src/types/skill";

describe("Skill Types", () => {
  it("should define a valid skill", () => {
    const skill: Skill = {
      id: "test-skill",
      name: "Test Skill",
      description: "A test skill",
      version: "1.0.0",
      category: "resume",
      platforms: ["claude-code"],
      prompt: "Test prompt",
    };

    expect(skill.id).toBe("test-skill");
    expect(skill.category).toBe("resume");
  });

  it("should allow optional fields", () => {
    const skill: Skill = {
      id: "test",
      name: "Test",
      description: "Test",
      version: "1.0.0",
      category: "jd",
      platforms: ["claude-code", "cursor"],
      prompt: "Test",
      tags: ["matching"],
      tools: [{ name: "tool1", description: "desc", parameters: {} }],
      examples: [{ input: "in", output: "out" }],
    };

    expect(skill.tags).toHaveLength(1);
    expect(skill.tools).toHaveLength(1);
    expect(skill.examples).toHaveLength(1);
  });
});
