/**
 * Authentication context for managing user session.
 * All HTTP goes through shared/lib/api.ts (which injects bearer + handles 401).
 */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { apiClient, getAuthToken, clearAuthToken } from '../shared/lib/api'

interface User {
  id: string
  username: string
  email?: string
  full_name: string
  role: 'admin' | 'viewer'
  is_active: boolean
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => getAuthToken())
  const [isLoading, setIsLoading] = useState(true)

  const fetchCurrentUser = async (authToken: string | null = null) => {
    const tokenToUse = authToken || token
    if (!tokenToUse) {
      setIsLoading(false)
      return
    }

    try {
      const response = await apiClient.get('/api/auth/me')
      setUser(response.data)
    } catch {
      setToken(null)
      setUser(null)
      clearAuthToken()
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      fetchCurrentUser()
    } else {
      setIsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const login = async (username: string, password: string) => {
    setIsLoading(true)
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      const response = await apiClient.post('/api/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })

      const accessToken = response.data.access_token
      setToken(accessToken)
      localStorage.setItem('token', accessToken)
      await fetchCurrentUser(accessToken)
    } catch (error) {
      setIsLoading(false)
      throw error
    }
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    clearAuthToken()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAuthenticated: !!token && !!user,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
