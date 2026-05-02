/**
 * Locale-aware formatters.
 * Use the useFormat() hook in components — it reads the active i18next locale.
 * Direct calls accept an explicit locale.
 */
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

export function formatCurrency(value: number, locale: string, currency = 'VND'): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(locale).format(value)
}

export function formatPercent(value: number, locale: string, fractionDigits = 1): string {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

export function formatDate(
  value: Date | string | number,
  locale: string,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' },
): string {
  return new Intl.DateTimeFormat(locale, options).format(new Date(value))
}

export function formatDateTime(value: Date | string | number, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

const RELATIVE_UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 365 * 24 * 60 * 60],
  ['month', 30 * 24 * 60 * 60],
  ['week', 7 * 24 * 60 * 60],
  ['day', 24 * 60 * 60],
  ['hour', 60 * 60],
  ['minute', 60],
  ['second', 1],
]

export function formatRelative(value: Date | string | number, locale: string): string {
  const target = new Date(value).getTime()
  const diffSeconds = Math.round((target - Date.now()) / 1000)
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  for (const [unit, secondsInUnit] of RELATIVE_UNITS) {
    if (Math.abs(diffSeconds) >= secondsInUnit || unit === 'second') {
      return rtf.format(Math.round(diffSeconds / secondsInUnit), unit)
    }
  }
  return rtf.format(0, 'second')
}

export interface FormatHelpers {
  currency: (n: number, currency?: string) => string
  number: (n: number) => string
  percent: (n: number, fractionDigits?: number) => string
  date: (d: Date | string | number, options?: Intl.DateTimeFormatOptions) => string
  dateTime: (d: Date | string | number) => string
  relative: (d: Date | string | number) => string
  locale: string
}

/** Read active i18next locale and return formatters bound to it. */
export function useFormat(): FormatHelpers {
  const { i18n } = useTranslation()
  const locale = i18n.language || 'vi'
  return useMemo<FormatHelpers>(
    () => ({
      currency: (n, currency) => formatCurrency(n, locale, currency),
      number: (n) => formatNumber(n, locale),
      percent: (n, fractionDigits) => formatPercent(n, locale, fractionDigits),
      date: (d, options) => formatDate(d, locale, options),
      dateTime: (d) => formatDateTime(d, locale),
      relative: (d) => formatRelative(d, locale),
      locale,
    }),
    [locale],
  )
}
