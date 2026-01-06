/**
 * Tests for DashboardLayout component with Lucide Icons.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { DashboardLayout } from '../../layouts/DashboardLayout'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { AuthProvider } from '../../contexts/AuthContext'
// Icons are imported in the component, not needed in tests

// Mock the auth context
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: '1', username: 'testuser', full_name: 'Test User', role: 'admin' },
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('DashboardLayout with Lucide Icons', () => {
  it('should render navigation links with icons', () => {
    render(
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <DashboardLayout />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    )

    expect(screen.getByText('Statistics')).toBeInTheDocument()
    expect(screen.getByText('Products')).toBeInTheDocument()
    expect(screen.getByText('Orders')).toBeInTheDocument()
  })

  it('should render theme toggle with Lucide Moon/Sun icons', () => {
    render(
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <DashboardLayout />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    )

    // Find theme toggle button by finding button that contains Moon or Sun icon
    const buttons = screen.getAllByRole('button')
    const themeButton = buttons.find(btn => {
      const icon = btn.querySelector('.lucide-moon, .lucide-sun')
      return icon !== null
    })
    
    expect(themeButton).toBeDefined()
    expect(themeButton).toBeInTheDocument()
    
    // Check that it contains an SVG icon (Moon or Sun)
    const icon = themeButton?.querySelector('svg')
    expect(icon).toBeInTheDocument()
    expect(icon?.classList.contains('lucide-moon') || icon?.classList.contains('lucide-sun')).toBe(true)
  })

  it('should show Sun icon when theme is dark (default)', () => {
    const { container } = render(
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <DashboardLayout />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    )

    // Check for Sun icon (dark theme shows Sun to switch to light)
    const sunIcon = container.querySelector('.lucide-sun')
    expect(sunIcon).toBeInTheDocument()
  })

  it('should render logout button', () => {
    render(
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <DashboardLayout />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    )

    expect(screen.getByText('Logout')).toBeInTheDocument()
  })

  it('should display user information', () => {
    render(
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <DashboardLayout />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    )

    expect(screen.getByText('Test User')).toBeInTheDocument()
  })
})

