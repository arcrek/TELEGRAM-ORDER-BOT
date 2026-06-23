import { describe, it, expect } from 'vitest'
import { matchTrigger, insertToken } from './autocompleteHelpers'

describe('matchTrigger', () => {
  it('matches @emo with empty query', () => {
    expect(matchTrigger('hello @emo')).toEqual({ query: '', start: 6 })
  })
  it('captures the contiguous query', () => {
    expect(matchTrigger('say @emohead')).toEqual({ query: 'head', start: 4 })
  })
  it('returns null when no trigger before caret', () => {
    expect(matchTrigger('no trigger here')).toBeNull()
  })
  it('returns null when a space breaks the trigger', () => {
    expect(matchTrigger('@emo head')).toBeNull()
  })
  it('matches at the very start', () => {
    expect(matchTrigger('@emo')).toEqual({ query: '', start: 0 })
  })
})

describe('insertToken', () => {
  it('replaces the trigger span with the token and returns caret after it', () => {
    // value: "hi @emohe more", caret at end of "@emohe" (index 9), matchStart 3
    const value = 'hi @emohe more'
    const result = insertToken(value, 9, 3, '{emo:5}')
    expect(result.value).toBe('hi {emo:5} more')
    expect(result.caret).toBe(3 + '{emo:5}'.length)
  })
  it('works at the end of the string', () => {
    const result = insertToken('go @emo', 7, 3, '{emo:12}')
    expect(result.value).toBe('go {emo:12}')
    expect(result.caret).toBe(3 + '{emo:12}'.length)
  })
})
