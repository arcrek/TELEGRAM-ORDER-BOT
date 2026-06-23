import { describe, it, expect } from 'vitest'
import { getCaretCoordinates } from './caretCoordinates'

describe('getCaretCoordinates', () => {
  it('returns numeric coords without throwing and cleans up the mirror node', () => {
    const ta = document.createElement('textarea')
    ta.value = 'hello world'
    document.body.appendChild(ta)
    const before = document.body.childElementCount
    const coords = getCaretCoordinates(ta, 5)
    expect(typeof coords.top).toBe('number')
    expect(typeof coords.left).toBe('number')
    expect(typeof coords.height).toBe('number')
    expect(document.body.childElementCount).toBe(before) // mirror div removed
    document.body.removeChild(ta)
  })
})
