import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmojiPreview } from './EmojiPreview'

describe('EmojiPreview', () => {
  it('renders text spans and emoji images', () => {
    render(
      <EmojiPreview
        units={[
          { type: 'emoji', emoji_id: '111', fallback: '🔔' },
          { type: 'text', value: 'hello' },
        ]}
      />,
    )
    const img = screen.getByRole('img')
    expect(img.getAttribute('src')).toContain('/api/emoji-thumbnails/111')
    expect(img.getAttribute('alt')).toBe('🔔')
    expect(screen.getByText('hello')).toBeInTheDocument()
  })

  it('falls back to the fallback char when the image fails to load', () => {
    render(<EmojiPreview units={[{ type: 'emoji', emoji_id: '111', fallback: '🔔' }]} />)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.getByText('🔔')).toBeInTheDocument()
  })
})
