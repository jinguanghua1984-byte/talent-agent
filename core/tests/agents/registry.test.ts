import { describe, it, expect, beforeEach } from "vitest";
import { agentRegistry } from "../../src/agents/registry.ts";
import { defineAgent } from "../../src/agents/base.ts";

describe("AgentRegistry", () => {
  beforeEach(() => {
    agentRegistry.clear();
  });

  it("should register and retrieve an agent", () => {
    const agent = defineAgent()
      .id("test-agent")
      .name("Test Agent")
      .description("Test description with examples")
      .version("1.0.0")
      .model("inherit")
      .color("blue")
      .platforms("claude-code")
      .systemPrompt("You are a test agent.")
      .build();

    agentRegistry.register(agent);

    expect(agentRegistry.has("test-agent")).toBe(true);
    expect(agentRegistry.get("test-agent")).toEqual(agent);
  });

  it("should throw on duplicate registration", () => {
    const agent = defineAgent()
      .id("duplicate")
      .name("Duplicate")
      .description("Test")
      .version("1.0.0")
      .model("inherit")
      .color("blue")
      .platforms("claude-code")
      .systemPrompt("Test")
      .build();

    agentRegistry.register(agent);

    expect(() => agentRegistry.register(agent)).toThrow("already registered");
  });

  it("should filter by platform", () => {
    const agent1 = defineAgent()
      .id("agent-1")
      .name("Agent 1")
      .description("Test")
      .version("1.0.0")
      .model("inherit")
      .color("blue")
      .platforms("claude-code", "cursor")
      .systemPrompt("Test")
      .build();

    const agent2 = defineAgent()
      .id("agent-2")
      .name("Agent 2")
      .description("Test")
      .version("1.0.0")
      .model("haiku")
      .color("green")
      .platforms("continue")
      .systemPrompt("Test")
      .build();

    agentRegistry.register(agent1);
    agentRegistry.register(agent2);

    expect(agentRegistry.getByPlatform("claude-code")).toHaveLength(1);
    expect(agentRegistry.getByPlatform("cursor")).toHaveLength(1);
    expect(agentRegistry.getByPlatform("continue")).toHaveLength(1);
  });

  it("should filter by model", () => {
    const agent1 = defineAgent()
      .id("sonnet-agent")
      .name("Sonnet Agent")
      .description("Test")
      .version("1.0.0")
      .model("sonnet")
      .color("blue")
      .platforms("claude-code")
      .systemPrompt("Test")
      .build();

    const agent2 = defineAgent()
      .id("haiku-agent")
      .name("Haiku Agent")
      .description("Test")
      .version("1.0.0")
      .model("haiku")
      .color("green")
      .platforms("claude-code")
      .systemPrompt("Test")
      .build();

    agentRegistry.register(agent1);
    agentRegistry.register(agent2);

    expect(agentRegistry.getByModel("sonnet")).toHaveLength(1);
    expect(agentRegistry.getByModel("haiku")).toHaveLength(1);
    expect(agentRegistry.getByModel("opus")).toHaveLength(0);
  });
});

describe("AgentBuilder validation", () => {
  it("should reject id shorter than 3 characters", () => {
    expect(() => {
      defineAgent()
        .id("ab")
        .name("Test")
        .description("Test")
        .version("1.0.0")
        .model("inherit")
        .color("blue")
        .platforms("claude-code")
        .systemPrompt("Test")
        .build();
    }).toThrow("3-50 characters");
  });

  it("should reject id longer than 50 characters", () => {
    const longId = "a".repeat(51);
    expect(() => {
      defineAgent()
        .id(longId)
        .name("Test")
        .description("Test")
        .version("1.0.0")
        .model("inherit")
        .color("blue")
        .platforms("claude-code")
        .systemPrompt("Test")
        .build();
    }).toThrow("3-50 characters");
  });

  it("should reject id starting with hyphen", () => {
    expect(() => {
      defineAgent()
        .id("-test-agent")
        .name("Test")
        .description("Test")
        .version("1.0.0")
        .model("inherit")
        .color("blue")
        .platforms("claude-code")
        .systemPrompt("Test")
        .build();
    }).toThrow("must start and end with alphanumeric");
  });

  it("should accept valid id formats", () => {
    const validIds = ["test", "test-agent", "test-123", "a1b2c3", "abc"];
    for (const id of validIds) {
      const agent = defineAgent()
        .id(id)
        .name("Test")
        .description("Test")
        .version("1.0.0")
        .model("inherit")
        .color("blue")
        .platforms("claude-code")
        .systemPrompt("Test")
        .build();
      expect(agent.id).toBe(id);
    }
  });
});
