export const DEFAULT_TOKENS = {
  white: '#F8FAF9',
  pos: '#0C3A2D',
  neg: '#BD210F',
  a1: '#6D9773',
  a2: '#FFB902',
  a3: '#BB8A52',
  border: '#e2e8f0',
  textStrong: '#0C3A2D',
  textMuted: '#475569',
  textSubtle: '#64748b',
};

export function useCssVars(tokens = DEFAULT_TOKENS) {
  return {
    ['--c-white']: tokens.white,
    ['--c-pos']: tokens.pos,
    ['--c-neg']: tokens.neg,
    ['--c-a1']: tokens.a1,
    ['--c-a2']: tokens.a2,
    ['--c-a3']: tokens.a3,
    ['--border']: tokens.border,
    ['--text-strong']: tokens.textStrong,
    ['--text-muted']: tokens.textMuted,
    ['--text-subtle']: tokens.textSubtle,
  };
}
