const TRIGGER_RE = /@emo([\p{L}\p{N}_]*)$/u

export interface TriggerMatch {
  query: string
  start: number
}

/** Detect an `@emo<query>` trigger immediately before the caret. */
export function matchTrigger(textBeforeCaret: string): TriggerMatch | null {
  const m = TRIGGER_RE.exec(textBeforeCaret)
  if (!m) return null
  return { query: m[1], start: textBeforeCaret.length - m[0].length }
}

/** Replace value[matchStart..caret] with token; return new value + caret after token. */
export function insertToken(
  value: string,
  caret: number,
  matchStart: number,
  token: string,
): { value: string; caret: number } {
  const next = value.slice(0, matchStart) + token + value.slice(caret)
  return { value: next, caret: matchStart + token.length }
}
