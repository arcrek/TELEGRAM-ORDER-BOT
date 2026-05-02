import { useEffect, type RefObject } from 'react'

interface UseDismissOptions {
  ref: RefObject<HTMLElement | null>
  onDismiss: () => void
  escKey?: boolean
  clickOutside?: boolean
  enabled?: boolean
}

export function useDismiss({
  ref,
  onDismiss,
  escKey = true,
  clickOutside = true,
  enabled = true,
}: UseDismissOptions) {
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (escKey && e.key === 'Escape') {
        e.stopPropagation()
        onDismiss()
      }
    }

    const handlePointerDown = (e: PointerEvent) => {
      if (!clickOutside) return
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onDismiss()
      }
    }

    if (escKey) document.addEventListener('keydown', handleKeyDown)
    if (clickOutside) document.addEventListener('pointerdown', handlePointerDown)

    return () => {
      if (escKey) document.removeEventListener('keydown', handleKeyDown)
      if (clickOutside) document.removeEventListener('pointerdown', handlePointerDown)
    }
  }, [ref, onDismiss, escKey, clickOutside, enabled])
}
