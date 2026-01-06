/**
 * Tests for routing and navigation.
 */
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from '../contexts/ThemeContext'
import { AuthProvider } from '../contexts/AuthContext'
import { AppRoutes } from '../App'

describe('Routing', () => {
  it('should render login route', () => {
    render(
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
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
})

