export * from './parse-resume';
export * from './analyze-jd';
export * from './match-candidate';

import { parseResumeCommand } from './parse-resume';
import { analyzeJdCommand } from './analyze-jd';
import { matchCandidateCommand } from './match-candidate';

export const allCommands = [
  parseResumeCommand,
  analyzeJdCommand,
  matchCandidateCommand,
];
