/**
 * 工作经历
 */
export interface WorkExperience {
  company: string;
  title: string;
  startDate: string;
  endDate?: string;
  description?: string;
  highlights?: string[];
}

/**
 * 教育背景
 */
export interface Education {
  school: string;
  degree: string;
  major?: string;
  startDate: string;
  endDate?: string;
}

/**
 * 候选人信息
 */
export interface Candidate {
  name: string;
  email?: string;
  phone?: string;
  location?: string;
  title?: string;
  summary?: string;
  skills?: string[];
  workExperience?: WorkExperience[];
  education?: Education[];
  languages?: string[];
  certifications?: string[];
}

/**
 * 简历解析结果
 */
export interface ResumeParseResult {
  success: boolean;
  candidate?: Candidate;
  rawText?: string;
  error?: string;
}
