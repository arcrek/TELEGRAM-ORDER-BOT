/**
 * Tests for Premium Dark SaaS theme utilities.
 */
import { describe, it, expect, vi } from 'vitest'
import {
  getThemeColors,
  applyTheme,
  ThemeMode,
} from '../styles/theme'

describe('Theme Utilities', () => {
  describe('getThemeColors', () => {
    it('should return light theme colors', () => {
      const colors = getThemeColors(ThemeMode.LIGHT)
      
      expect(colors).toHaveProperty('background')
      expect(colors).toHaveProperty('backgroundSecondary')
      expect(colors).toHaveProperty('cardBg')
      expect(colors).toHaveProperty('border')
      expect(colors).toHaveProperty('textPrimary')
      expect(colors).toHaveProperty('textSecondary')
      expect(colors).toHaveProperty('textMuted')
      expect(colors).toHaveProperty('accentBlue')
      expect(colors.background).toBe('#f5f7fa')
    })

    it('should return dark theme colors with premium dark palette', () => {
      const colors = getThemeColors(ThemeMode.DARK)
      
      expect(colors).toHaveProperty('background')
      expect(colors).toHaveProperty('backgroundSecondary')
      expect(colors).toHaveProperty('cardBg')
      expect(colors).toHaveProperty('border')
      expect(colors).toHaveProperty('textPrimary')
      expect(colors).toHaveProperty('textSecondary')
      expect(colors).toHaveProperty('textMuted')
      expect(colors).toHaveProperty('accentBlue')
      // Premium dark theme colors
      expect(colors.background).toBe('#0F0F0D')
      expect(colors.backgroundSecondary).toBe('#141412')
      expect(colors.cardBg).toBe('#181816')
      expect(colors.border).toBe('#2A2A26')
      expect(colors.textPrimary).toBe('#EAEAEA')
      expect(colors.textSecondary).toBe('#B5B5B5')
      expect(colors.textMuted).toBe('#8F8F8F')
      expect(colors.accentBlue).toBe('#6EA8FF')
    })

    it('should have different colors for light and dark themes', () => {
      const lightColors = getThemeColors(ThemeMode.LIGHT)
      const darkColors = getThemeColors(ThemeMode.DARK)
      
      expect(lightColors.background).not.toBe(darkColors.background)
      expect(lightColors.cardBg).not.toBe(darkColors.cardBg)
      expect(lightColors.textPrimary).not.toBe(darkColors.textPrimary)
    })
  })

  describe('applyTheme', () => {
    it('should apply theme to document root', () => {
      const setAttributeSpy = vi.fn()
      const setPropertySpy = vi.fn()
      const mockDocument = {
        documentElement: {
          style: {
            setProperty: setPropertySpy,
          } as unknown as CSSStyleDeclaration,
          setAttribute: setAttributeSpy,
        },
      } as unknown as Document
      
      applyTheme(ThemeMode.DARK, mockDocument)
      
      expect(setAttributeSpy).toHaveBeenCalledWith('data-theme', 'dark')
      expect(setPropertySpy).toHaveBeenCalled()
    })

    it('should set data-theme attribute', () => {
      let themeAttribute = ''
      const setPropertySpy = vi.fn()
      const mockDocument = {
        documentElement: {
          style: {
            setProperty: setPropertySpy,
          } as unknown as CSSStyleDeclaration,
          setAttribute: (name: string, value: string) => {
            if (name === 'data-theme') {
              themeAttribute = value
            }
          },
        },
      } as unknown as Document
      
      applyTheme(ThemeMode.DARK, mockDocument)
      
      expect(themeAttribute).toBe('dark')
    })

    it('should set all CSS custom properties for dark theme', () => {
      const setPropertyCalls: Array<[string, string]> = []
      const setPropertySpy = vi.fn((name: string, value: string) => {
        setPropertyCalls.push([name, value])
      })
      const mockDocument = {
        documentElement: {
          style: {
            setProperty: setPropertySpy,
          } as unknown as CSSStyleDeclaration,
          setAttribute: vi.fn(),
        },
      } as unknown as Document
      
      applyTheme(ThemeMode.DARK, mockDocument)
      
      // Check that all required CSS variables are set
      const propertyNames = setPropertyCalls.map(([name]) => name)
      expect(propertyNames).toContain('--bg-primary')
      expect(propertyNames).toContain('--bg-secondary')
      expect(propertyNames).toContain('--card-bg')
      expect(propertyNames).toContain('--border-color')
      expect(propertyNames).toContain('--text-primary')
      expect(propertyNames).toContain('--text-secondary')
      expect(propertyNames).toContain('--text-muted')
      expect(propertyNames).toContain('--accent-blue')
    })
  })
})
