/**
 * Tests for Premium Dark SaaS Button component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from '../../components/Button'
import { ThemeProvider } from '../../contexts/ThemeContext'

describe('Button Component', () => {
  it('should render button text', () => {
    render(
      <ThemeProvider>
        <Button>Click Me</Button>
      </ThemeProvider>
    )
    
    expect(screen.getByText('Click Me')).toBeInTheDocument()
  })

  it('should call onClick when clicked', () => {
    const handleClick = vi.fn()
    render(
      <ThemeProvider>
        <Button onClick={handleClick}>Click</Button>
      </ThemeProvider>
    )
    
    screen.getByText('Click').click()
    
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('should be disabled when disabled prop is true', () => {
    render(
      <ThemeProvider>
        <Button disabled>Disabled</Button>
      </ThemeProvider>
    )
    
    const button = screen.getByText('Disabled')
    expect(button).toBeDisabled()
  })

  it('should apply variant styles', () => {
    const { container } = render(
      <ThemeProvider>
        <Button variant="primary">Primary</Button>
      </ThemeProvider>
    )
    const button = container.firstChild as HTMLElement
    
    expect(button).toHaveClass('button--primary')
  })

  it('should apply size styles', () => {
    const { container } = render(
      <ThemeProvider>
        <Button size="large">Large</Button>
      </ThemeProvider>
    )
    const button = container.firstChild as HTMLElement
    
    expect(button).toHaveClass('button--large')
  })

  it('should render as different element when as prop is provided', () => {
    render(
      <ThemeProvider>
        <Button as="a" href="/test">Link</Button>
      </ThemeProvider>
    )
    
    const link = screen.getByText('Link')
    expect(link.tagName).toBe('A')
    expect(link).toHaveAttribute('href', '/test')
  })

  it('should apply outline variant', () => {
    const { container } = render(
      <ThemeProvider>
        <Button variant="outline">Outline</Button>
      </ThemeProvider>
    )
    const button = container.firstChild as HTMLElement
    
    expect(button).toHaveClass('button--outline')
  })
})
