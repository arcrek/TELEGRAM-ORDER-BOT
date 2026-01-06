/**
 * Premium Dark SaaS Dashboard Theme System.
 * Modern minimalist design with soft dark theme (Vercel/Cursor/Linear-inspired).
 * NO gradients, NO glassmorphism, NO neumorphism.
 */

export enum ThemeMode {
  LIGHT = 'light',
  DARK = 'dark',
}

export interface ThemeColors {
  background: string
  backgroundSecondary: string
  cardBg: string
  border: string
  textPrimary: string
  textSecondary: string
  textMuted: string
  accentBlue: string
}

/**
 * Get theme colors for a specific theme mode.
 * Premium dark theme: Soft dark (not pure black) with minimalist design.
 */
export function getThemeColors(mode: ThemeMode): ThemeColors {
  if (mode === ThemeMode.DARK) {
    return {
      // Premium dark theme colors
      background: '#0F0F0D',           // Main application background
      backgroundSecondary: '#141412',   // Sidebar / Secondary BG
      cardBg: '#181816',                // Card BG
      border: '#2A2A26',                // Borders and dividers
      textPrimary: '#EAEAEA',           // Primary text
      textSecondary: '#B5B5B5',         // Secondary text
      textMuted: '#8F8F8F',             // Muted text (placeholders)
      accentBlue: '#6EA8FF',            // Accent blue for interactive elements
    }
  }

  // Light theme (kept for compatibility, but dark-mode first)
  return {
    background: '#f5f7fa',
    backgroundSecondary: '#e8ecf1',
    cardBg: '#ffffff',
    border: 'rgba(0, 0, 0, 0.1)',
    textPrimary: '#1a1b2e',
    textSecondary: 'rgba(26, 27, 46, 0.7)',
    textMuted: 'rgba(26, 27, 46, 0.5)',
    accentBlue: '#6EA8FF',
  }
}

/**
 * Apply theme to document root.
 * Sets CSS custom properties for the new premium dark theme.
 */
export function applyTheme(mode: ThemeMode, document: Document = window.document): void {
  document.documentElement.setAttribute('data-theme', mode)
  
  const colors = getThemeColors(mode)
  const root = document.documentElement.style
  
  // Set CSS custom properties
  root.setProperty('--bg-primary', colors.background)
  root.setProperty('--bg-secondary', colors.backgroundSecondary)
  root.setProperty('--card-bg', colors.cardBg)
  root.setProperty('--border-color', colors.border)
  root.setProperty('--text-primary', colors.textPrimary)
  root.setProperty('--text-secondary', colors.textSecondary)
  root.setProperty('--text-muted', colors.textMuted)
  root.setProperty('--accent-blue', colors.accentBlue)
}
