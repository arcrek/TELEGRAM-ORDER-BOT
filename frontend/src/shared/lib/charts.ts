import type { ChartOptions } from 'chart.js'

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export interface ChartTheme {
  textPrimary: string
  textMuted: string
  borderSubtle: string
  brand500: string
  viz: string[]
  bgSurface: string
}

export function getChartTheme(): ChartTheme {
  return {
    textPrimary: cssVar('--text-primary') || '#EAEAEA',
    textMuted: cssVar('--text-muted') || '#6B7280',
    borderSubtle: cssVar('--border-subtle') || '#2A2A26',
    brand500: cssVar('--brand-500') || '#6EA8FF',
    bgSurface: cssVar('--bg-surface') || '#181816',
    viz: [
      cssVar('--viz-1') || '#6EA8FF',
      cssVar('--viz-2') || '#34D399',
      cssVar('--viz-3') || '#FBBF24',
      cssVar('--viz-4') || '#F87171',
      cssVar('--viz-5') || '#A78BFA',
      cssVar('--viz-6') || '#38BDF8',
      cssVar('--viz-7') || '#FB923C',
      cssVar('--viz-8') || '#E879F9',
    ],
  }
}

export function getBaseChartOptions(theme: ChartTheme): Partial<ChartOptions<'line'>> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 300,
    },
    plugins: {
      legend: {
        labels: {
          color: theme.textMuted,
          font: { size: 11 },
          boxWidth: 12,
        },
      },
      tooltip: {
        backgroundColor: theme.bgSurface,
        borderColor: theme.borderSubtle,
        borderWidth: 1,
        titleColor: theme.textPrimary,
        bodyColor: theme.textMuted,
        padding: 8,
        displayColors: true,
        callbacks: {},
      },
    },
    scales: {
      x: {
        ticks: { color: theme.textMuted, font: { size: 10 } },
        grid: { color: theme.borderSubtle, drawBorder: false } as Record<string, unknown>,
        border: { display: false },
      },
      y: {
        ticks: { color: theme.textMuted, font: { size: 10 } },
        grid: { color: theme.borderSubtle, drawBorder: false } as Record<string, unknown>,
        border: { display: false },
      },
    },
  } as Partial<ChartOptions<'line'>>
}

export function useChartTheme(): ChartTheme {
  return getChartTheme()
}
