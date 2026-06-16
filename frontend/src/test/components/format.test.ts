/**
 * Tests for parseUtc in format.ts
 *
 * Spec requirement: naive-UTC strings (no zone designator) must be parsed as
 * UTC, not as browser-local time. This test verifies the fix by asserting that
 * the epoch milliseconds of a parsed naive-UTC string equal the same value
 * computed via Date.UTC — regardless of the machine's local timezone.
 */
import { describe, it, expect } from 'vitest'
import { parseUtc } from '../../shared/lib/format'

describe('parseUtc', () => {
  it('parses a naive ISO string as UTC', () => {
    // "2026-06-16T10:30:00" has no zone designator — must be treated as UTC
    const result = parseUtc('2026-06-16T10:30:00')
    expect(result.getTime()).toBe(Date.UTC(2026, 5, 16, 10, 30, 0))
  })

  it('passes through a Z-suffixed string unchanged', () => {
    const result = parseUtc('2026-06-16T10:30:00Z')
    expect(result.getTime()).toBe(Date.UTC(2026, 5, 16, 10, 30, 0))
  })

  it('passes through a +00:00 suffixed string correctly', () => {
    const result = parseUtc('2026-06-16T10:30:00+00:00')
    expect(result.getTime()).toBe(Date.UTC(2026, 5, 16, 10, 30, 0))
  })

  it('passes through a positive offset string correctly', () => {
    // 2026-06-16T17:30:00+07:00  (Vietnam UTC+7) = 10:30 UTC
    const result = parseUtc('2026-06-16T17:30:00+07:00')
    expect(result.getTime()).toBe(Date.UTC(2026, 5, 16, 10, 30, 0))
  })

  it('passes through a negative offset string correctly', () => {
    // 2026-06-16T06:30:00-04:00 (EDT) = 10:30 UTC
    const result = parseUtc('2026-06-16T06:30:00-04:00')
    expect(result.getTime()).toBe(Date.UTC(2026, 5, 16, 10, 30, 0))
  })

  it('passes through a Date object', () => {
    const d = new Date(Date.UTC(2026, 5, 16, 10, 30, 0))
    const result = parseUtc(d)
    expect(result.getTime()).toBe(d.getTime())
  })

  it('passes through a numeric timestamp', () => {
    const ms = Date.UTC(2026, 5, 16, 10, 30, 0)
    const result = parseUtc(ms)
    expect(result.getTime()).toBe(ms)
  })

  it('naive string: parsed epoch differs from local-time interpretation when local is not UTC', () => {
    // This verifies the bug-fix: without parseUtc, new Date('2026-06-16T10:30:00')
    // would be LOCAL time on most machines, giving a different epoch than Date.UTC.
    // parseUtc must always give the UTC epoch.
    const naiveUtcEpoch = Date.UTC(2026, 5, 16, 10, 30, 0)
    const result = parseUtc('2026-06-16T10:30:00')
    expect(result.getTime()).toBe(naiveUtcEpoch)
  })
})
