import { describe, it, expect } from 'vitest'
import { formatVndCompact } from './format'

describe('formatVndCompact', () => {
  it('formats VND with dot separators and đ suffix', () => {
    expect(formatVndCompact(50000)).toBe('50.000đ')
    expect(formatVndCompact(1000000)).toBe('1.000.000đ')
    expect(formatVndCompact(0)).toBe('0đ')
  })
})
