/**
 * 简单的模板加载器
 * 在构建时将模板嵌入代码
 */

// 使用 Vite 的 ?raw 导入或直接内联
const templates: Record<string, string> = {};

/**
 * 注册模板
 */
export function registerTemplate(id: string, content: string): void {
  templates[id] = content;
}

/**
 * 获取模板
 */
export function getTemplate(id: string): string | undefined {
  return templates[id];
}

/**
 * 获取所有模板 ID
 */
export function getTemplateIds(): string[] {
  return Object.keys(templates);
}
