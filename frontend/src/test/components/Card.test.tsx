/**
 * Tests for Premium Dark SaaS Card component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Card } from '../../components/Card'
import { ThemeProvider } from '../../contexts/ThemeContext'

describe('Card Component', () => {
  it('should render children content', () => {
    render(
      <ThemeProvider>
        <Card>Test Content</Card>
      </ThemeProvider>
    )
    
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('should apply premium dark theme styles with borders', () => {
    const { container } = render(
      <ThemeProvider>
        <Card>Content</Card>
      </ThemeProvider>
    )
    const card = container.firstChild as HTMLElement
    
    // Card should have the card class for premium dark theme styling
    expect(card).toHaveClass('card')
    // Card should not have inline styles (styles come from CSS)
    // The card component no longer uses glassmorphic inline styles
    expect(card.style.backgroundColor).toBe('')
    expect(card.style.backgroundImage).toBe('')
    expect(card.style.boxShadow).toBe('')
  })

  it('should accept className prop', () => {
    const { container } = render(
      <ThemeProvider>
        <Card className="custom-class">Content</Card>
      </ThemeProvider>
    )
    const card = container.firstChild as HTMLElement
    
    expect(card).toHaveClass('custom-class')
  })

  it('should accept onClick handler', () => {
    const handleClick = vi.fn()
    render(
      <ThemeProvider>
        <Card onClick={handleClick}>Clickable</Card>
      </ThemeProvider>
    )
    
    const card = screen.getByText('Clickable')
    card.click()
    
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('should render with variant styles', () => {
    const { container } = render(
      <ThemeProvider>
        <Card variant="elevated">Content</Card>
      </ThemeProvider>
    )
    const card = container.firstChild as HTMLElement
    
    expect(card).toHaveClass('card--elevated')
  })

  it('should render with flat variant (no border)', () => {
    const { container } = render(
      <ThemeProvider>
        <Card variant="flat">Content</Card>
      </ThemeProvider>
    )
    const card = container.firstChild as HTMLElement
    
    expect(card).toHaveClass('card--flat')
  })
})
