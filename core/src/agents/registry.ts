import type { Agent } from "../types/agent.ts";

/** Agent 注册表 - 管理所有已注册的 Agents */
class AgentRegistry {
  private agents: Map<string, Agent> = new Map();

  register(agent: Agent): void {
    if (this.agents.has(agent.id)) {
      throw new Error(`Agent with id "${agent.id}" already registered`);
    }
    this.agents.set(agent.id, agent);
  }

  get(id: string): Agent | undefined {
    return this.agents.get(id);
  }

  getAll(): Agent[] {
    return Array.from(this.agents.values());
  }

  getByPlatform(platform: Agent["platforms"][number]): Agent[] {
    return this.getAll().filter((agent) => agent.platforms.includes(platform));
  }

  getByModel(model: Agent["model"]): Agent[] {
    return this.getAll().filter((agent) => agent.model === model);
  }

  has(id: string): boolean {
    return this.agents.has(id);
  }

  clear(): void {
    this.agents.clear();
  }
}

export const agentRegistry = new AgentRegistry();
