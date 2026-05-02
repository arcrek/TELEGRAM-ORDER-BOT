/**
 * Theme mode + applyTheme stub.
 * All token values live in styles/tokens.css; this only flips data-theme.
 * Kept for backwards compatibility; ThemeContext rewrite (Step 2) replaces it.
 */

export enum ThemeMode {
  LIGHT = 'light',
  DARK = 'dark',
}

export function applyTheme(mode: ThemeMode, document: Document = window.document): void {
  document.documentElement.setAttribute('data-theme', mode)
}
