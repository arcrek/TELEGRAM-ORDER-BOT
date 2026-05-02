import { useEffect, useRef } from 'react'

const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export function useFocusTrap<T extends HTMLElement>(active: boolean) {
  const ref = useRef<T>(null)

  useEffect(() => {
    if (!active || !ref.current) return
    const el = ref.current
    const focusables = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS))
    if (!focusables.length) return

    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    const prev = document.activeElement as HTMLElement | null

    // Defer focus so the element is fully rendered
    const raf = requestAnimationFrame(() => first.focus())

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    el.addEventListener('keydown', handleKeyDown)
    return () => {
      cancelAnimationFrame(raf)
      el.removeEventListener('keydown', handleKeyDown)
      prev?.focus()
    }
  }, [active])

  return ref
}
