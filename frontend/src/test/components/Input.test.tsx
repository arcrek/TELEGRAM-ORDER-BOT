/**
 * Tests for Premium Dark SaaS Input component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Input } from '../../components/Input'
import { ThemeProvider } from '../../contexts/ThemeContext'

describe('Input Component', () => {
  it('should render input element', () => {
    render(
      <ThemeProvider>
        <Input placeholder="Enter text" />
      </ThemeProvider>
    )
    
    const input = screen.getByPlaceholderText('Enter text')
    expect(input).toBeInTheDocument()
    expect(input.tagName).toBe('INPUT')
  })

  it('should accept value and onChange', async () => {
    const handleChange = vi.fn()
    const user = userEvent.setup()
    
    render(
      <ThemeProvider>
        <Input value="test" onChange={handleChange} />
      </ThemeProvider>
    )
    
    const input = screen.getByDisplayValue('test')
    await user.type(input, 'x')
    
    expect(handleChange).toHaveBeenCalled()
  })

  it('should apply premium dark theme styles with borders', () => {
    const { container } = render(
      <ThemeProvider>
        <Input />
      </ThemeProvider>
    )
    const input = container.querySelector('input') as HTMLElement
    
    // Input should have border (no shadows, no gradients)
    expect(input).toHaveClass('input')
    const computedStyle = window.getComputedStyle(input)
    expect(computedStyle.border).toBeTruthy()
  })

  it('should show error state', () => {
    render(
      <ThemeProvider>
        <Input error="Error message" />
      </ThemeProvider>
    )
    
    expect(screen.getByText('Error message')).toBeInTheDocument()
    const input = screen.getByRole('textbox')
    expect(input).toHaveClass('input--error')
  })

  it('should accept label', () => {
    render(
      <ThemeProvider>
        <Input label="Username" />
      </ThemeProvider>
    )
    
    expect(screen.getByText('Username')).toBeInTheDocument()
  })

  it('should be disabled when disabled prop is true', () => {
    render(
      <ThemeProvider>
        <Input disabled />
      </ThemeProvider>
    )
    
    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
    expect(input).toHaveClass('input--disabled')
  })
})
