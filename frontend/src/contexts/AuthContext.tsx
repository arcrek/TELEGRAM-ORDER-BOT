/**
 * Authentication context for managing user session.
 */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem('token')
  })
  const [isLoading, setIsLoading] = useState(true)

  const fetchCurrentUser = async (authToken: string | null = null) => {
    const tokenToUse = authToken || token
    if (!tokenToUse) {
      setIsLoading(false)
      return
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${tokenToUse}`,
        },
      })
      setUser(response.data)
    } catch (error) {
      // Token invalid, clear it
      setToken(null)
      setUser(null)
      localStorage.removeItem('token')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    // Check if user is authenticated on mount
    if (token) {
      fetchCurrentUser()
    } else {
      setIsLoading(false)
    }
    // Only run when token changes, not when fetchCurrentUser changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const login = async (username: string, password: string) => {
    setIsLoading(true)
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      const response = await axios.post(`${API_BASE_URL}/api/auth/login`, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })

      const accessToken = response.data.access_token
      setToken(accessToken)
      localStorage.setItem('token', accessToken)

      // Fetch user info with the new token
      await fetchCurrentUser(accessToken)
    } catch (error: any) {
      setIsLoading(false)
      throw error
    }
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('token')
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

