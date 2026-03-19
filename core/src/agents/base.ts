import type {
  Agent,
  AgentMeta,
  AgentColor,
  AgentModel,
  AgentTool,
  AgentExample,
} from "../types/agent.ts";

/** Agent 构建器 - 用于流畅地创建 Agent 定义 */
export class AgentBuilder {
  private agent: Partial<Agent> = {};

  id(id: string): this {
    this.agent.id = id;
    return this;
  }

  name(name: string): this {
    this.agent.name = name;
    return this;
  }

  description(description: string): this {
    this.agent.description = description;
    return this;
  }

  version(version: string): this {
    this.agent.version = version;
    return this;
  }

  model(model: AgentModel): this {
    this.agent.model = model;
    return this;
  }

  color(color: AgentColor): this {
    this.agent.color = color;
    return this;
  }

  platforms(...platforms: AgentMeta["platforms"]): this {
    this.agent.platforms = platforms;
    return this;
  }

  systemPrompt(prompt: string): this {
    this.agent.systemPrompt = prompt;
    return this;
  }

  tools(...tools: AgentTool[]): this {
    this.agent.tools = tools;
    return this;
  }

  skillIds(...ids: string[]): this {
    this.agent.skillIds = ids;
    return this;
  }

  examples(...examples: AgentExample[]): this {
    this.agent.examples = examples;
    return this;
  }

  maxIterations(max: number): this {
    this.agent.maxIterations = max;
    return this;
  }

  build(): Agent {
    const required = ["id", "name", "description", "version", "model", "color", "platforms", "systemPrompt"] as const;
    for (const field of required) {
      if (!this.agent[field]) {
        throw new Error(`Agent ${field} is required`);
      }
    }

    this.validateId(this.agent.id!);
    return this.agent as Agent;
  }

  private validateId(id: string): void {
    if (id.length < 3 || id.length > 50) {
      throw new Error(`Agent id must be 3-50 characters, got: ${id.length}`);
    }
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(id)) {
      throw new Error(
        `Agent id must contain only lowercase letters, numbers, and hyphens: ${id}`
      );
    }
  }
}

/** 创建 Agent 构建器 */
export function defineAgent(): AgentBuilder {
  return new AgentBuilder();
}
