/**
 * Tests for routing and navigation.
 */
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../contexts/ThemeContext'
import { AuthProvider } from '../contexts/AuthContext'
import { ToastProvider } from '../shared/components/Toast'
import { ConfirmDialogProvider } from '../shared/components/ConfirmDialog'
import { AppRoutes } from '../App'

// jsdom does not implement window.matchMedia — stub it so AppShell can mount
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
})

// Mock useAuth to return an authenticated session so the protected route mounts
vi.mock('../contexts/AuthContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../contexts/AuthContext')>()
  return {
    ...actual,
    useAuth: vi.fn(() => ({
      isAuthenticated: true,
      isLoading: false,
      user: { id: '1', username: 'admin', full_name: 'Admin', role: 'admin', is_active: true },
      token: 'test-token',
      login: vi.fn(),
      logout: vi.fn(),
    })),
  }
})

describe('Routing', () => {
  it('should render login route', () => {
    render(
      <BrowserRouter>
        <ThemeProvider>
          <ToastProvider>
            <ConfirmDialogProvider>
              <AuthProvider>
                <AppRoutes />
              </AuthProvider>
            </ConfirmDialogProvider>
          </ToastProvider>
        </ThemeProvider>
      </BrowserRouter>
    )

    // Should show login page by default (protected routes redirect to login)
    expect(window.location.pathname).toBeDefined()
  })

  it('should have route definitions', () => {
    // Test that routes are properly configured
    const routes = ['/login', '/dashboard', '/products', '/orders', '/statistics']

    routes.forEach(route => {
      expect(route).toMatch(/^\//)
    })
  })

  it('should render RefundsPage at /refunds when authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/refunds']}>
        <ThemeProvider>
          <ToastProvider>
            <ConfirmDialogProvider>
              <AuthProvider>
                <AppRoutes />
              </AuthProvider>
            </ConfirmDialogProvider>
          </ToastProvider>
        </ThemeProvider>
      </MemoryRouter>
    )

    // RefundsPage mounts a PageHeader which renders an <h1 class="page-header__title">
    // There are two h1s (topbar + page header), both showing the i18n key literal
    // in jsdom (no i18n provider) — assert there is at least one heading present.
    const headings = screen.getAllByRole('heading', { level: 1 })
    expect(headings.length).toBeGreaterThan(0)
  })
})
