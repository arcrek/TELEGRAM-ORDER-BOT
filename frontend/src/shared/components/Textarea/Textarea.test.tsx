import { describe, it, expect } from 'vitest'
import { useRef, useEffect } from 'react'
import { render, screen } from '@testing-library/react'
import { Textarea } from './Textarea'

function Harness({ onEl }: { onEl: (el: HTMLTextAreaElement | null) => void }) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { onEl(ref.current) }, [onEl])
  return <Textarea ref={ref} value="hi" onChange={() => {}} aria-label="t" />
}

describe('Textarea ref forwarding', () => {
  it('exposes the underlying textarea element via ref', () => {
    let captured: HTMLTextAreaElement | null = null
    render(<Harness onEl={el => { captured = el }} />)
    expect(captured).toBe(screen.getByLabelText('t'))
    expect((captured as HTMLTextAreaElement | null)?.tagName).toBe('TEXTAREA')
  })

  it('still renders value and passes through props', () => {
    render(<Textarea value="hello" onChange={() => {}} rows={3} aria-label="x" />)
    const ta = screen.getByLabelText('x') as HTMLTextAreaElement
    expect(ta.value).toBe('hello')
    expect(ta.rows).toBe(3)
  })
})
