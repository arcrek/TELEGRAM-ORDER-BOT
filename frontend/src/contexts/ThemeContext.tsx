/**
 * Theme context for managing light/dark theme.
 */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { applyTheme, ThemeMode } from '../styles/theme'

interface ThemeContextType {
  theme: ThemeMode
  toggleTheme: () => void
  setTheme: (theme: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    // Get theme from localStorage or default to dark
    const saved = localStorage.getItem('theme') as ThemeMode
    return saved || ThemeMode.DARK
  })

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setThemeState(prev => prev === ThemeMode.LIGHT ? ThemeMode.DARK : ThemeMode.LIGHT)
  }

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme)
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

