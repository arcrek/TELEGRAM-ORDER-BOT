import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EmojiAutocompleteTextarea } from './EmojiAutocompleteTextarea'
import { apiClient } from '../../lib/api'

const PLACEHOLDERS = [
  { id: 5, name: 'Header', token: '{emo:5}', units: [{ type: 'emoji', emoji_id: '111', fallback: '🔔' }] },
  { id: 6, name: 'Footer', token: '{emo:6}', units: [{ type: 'text', value: 'bye' }] },
]

function Harness() {
  const [value, setValue] = useState('')
  return (
    <EmojiAutocompleteTextarea
      aria-label="composer"
      value={value}
      onChange={e => setValue(e.target.value)}
    />
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(apiClient, 'get').mockResolvedValue({ data: PLACEHOLDERS } as never)
})

describe('EmojiAutocompleteTextarea', () => {
  it('opens a suggestion list when @emo is typed', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emo' } })
    expect(await screen.findByText('Header')).toBeInTheDocument()
    expect(screen.getByText('Footer')).toBeInTheDocument()
  })

  it('filters the list by the query', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emohead' } })
    expect(await screen.findByText('Header')).toBeInTheDocument()
    expect(screen.queryByText('Footer')).not.toBeInTheDocument()
  })

  it('inserts the {emo:id} token on click and fires onChange', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: 'hi @emo' } })
    fireEvent.mouseDown(await screen.findByText('Header'))
    await waitFor(() => expect(ta.value).toBe('hi {emo:5}'))
  })

  it('closes on Escape without inserting', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emo' } })
    expect(await screen.findByText('Header')).toBeInTheDocument()
    fireEvent.keyDown(ta, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByText('Header')).not.toBeInTheDocument())
    expect(ta.value).toBe('@emo')
  })

  it('passes text through normally when not triggered', () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: 'plain text' } })
    expect(ta.value).toBe('plain text')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('arrow-nav: ArrowDown moves highlight so Enter inserts the second item', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emo' } })
    // Wait for both items to be rendered before dispatching arrow key
    await screen.findByText('Header')
    expect(screen.getByText('Footer')).toBeInTheDocument()
    // Move highlight from item 0 (Header) to item 1 (Footer)
    fireEvent.keyDown(ta, { key: 'ArrowDown' })
    fireEvent.keyDown(ta, { key: 'Enter' })
    // Footer is id:6 → token {emo:6}
    await waitFor(() => expect(ta.value).toBe('{emo:6}'))
  })

  it('shows empty state when no placeholders are configured', async () => {
    vi.restoreAllMocks()
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] } as never)
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emo' } })
    expect(await screen.findByText('No emoji placeholders — create one on the Emoji page')).toBeInTheDocument()
  })
})
