/**
 * 职位要求
 */
export interface JobRequirement {
  /** 要求类型：必须/优先 */
  type: "required" | "preferred";
  /** 要求内容 */
  content: string;
  /** 分类 */
  category?: "skill" | "experience" | "education" | "certification" | "other";
}

/**
 * 职位信息
 */
export interface JobDescription {
  title: string;
  company?: string;
  location?: string;
  salaryRange?: {
    min?: number;
    max?: number;
    currency?: string;
  };
  summary?: string;
  responsibilities?: string[];
  requirements?: JobRequirement[];
  benefits?: string[];
  rawText?: string;
}

/**
 * JD 解析结果
 */
export interface JDParseResult {
  success: boolean;
  jd?: JobDescription;
  error?: string;
}

/**
 * 匹配结果
 */
export interface MatchResult {
  score: number; // 0-100
  summary: string;
  strengths: string[];
  gaps: string[];
  recommendations?: string[];
}
