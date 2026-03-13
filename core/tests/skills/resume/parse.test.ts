import { describe, it, expect, beforeEach } from "vitest";
import { skillRegistry } from "../../../src/skills/registry.ts";
import { resumeParseSkill } from "../../../src/skills/resume/parse.skill.ts";

describe("resume-parse skill", () => {
  beforeEach(() => {
    skillRegistry.clear();
    // 重新注册，因为每个测试前清空了注册表
    skillRegistry.register(resumeParseSkill);
  });

  it("should be defined correctly", () => {
    expect(resumeParseSkill.id).toBe("resume-parse");
    expect(resumeParseSkill.name).toBe("简历解析");
    expect(resumeParseSkill.category).toBe("resume");
  });

  it("should be registered", () => {
    expect(skillRegistry.has("resume-parse")).toBe(true);
  });

  it("should have prompt template", () => {
    expect(resumeParseSkill.prompt).toContain("简历解析");
    expect(resumeParseSkill.prompt).toContain("{{resume}}");
  });

  it("should support multiple platforms", () => {
    expect(resumeParseSkill.platforms).toContain("claude-code");
    expect(resumeParseSkill.platforms).toContain("cursor");
    expect(resumeParseSkill.platforms).toContain("continue");
  });
});
