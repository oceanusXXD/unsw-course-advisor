import { STATUS_NODE_MAP } from './constants';

export function mapStatusNodeToStep(node = '') {
  const s = String(node).toLowerCase();
  if (s.includes('analy') || s.includes('context')) return STATUS_NODE_MAP.ANALYZE;
  if (s.includes('plan') || s.includes('router') || s.includes('planner'))
    return STATUS_NODE_MAP.PLAN;
  if (s.includes('retriev') || s.includes('rag') || s.includes('search'))
    return STATUS_NODE_MAP.RETRIEVE;
  return STATUS_NODE_MAP.GENERATE;
}

export function normalizeHistory(messages) {
  return (messages || [])
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({ role: m.role, content: m.content || '' }));
}

export function sourceToCourseCard(src) {
  return {
    code: src.code || src.course_code || src.course || src.id || 'COURSE',
    name: src.name || src.course_name || src.title || 'Unknown Course',
    uoc: src.uoc || src.units || src.credit || 6,
    term: src.term || src.session || 'T1',
    prereq: src.prereq || src.prerequisite || src.prereqs || '-',
    brief: src.brief || src.summary || src.desc || 'No summary',
    source: src.source || src.provider || src.origin || 'Handbook',
  };
}
