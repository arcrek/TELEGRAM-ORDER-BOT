import { useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useDisclosure } from '../../hooks/useDisclosure'
import { useDismiss } from '../../hooks/useDismiss'
import './Popover.css'

export type PopoverPlacement = 'bottom-start' | 'bottom-end' | 'bottom' | 'top-start' | 'top-end' | 'top'

export interface PopoverProps {
  trigger: ReactNode
  content: ReactNode
  placement?: PopoverPlacement
  className?: string
  contentClassName?: string
  closeOnContentClick?: boolean
}

function getTransform(placement: PopoverPlacement): string | undefined {
  if (placement.startsWith('top') && placement.endsWith('end')) return 'translate(-100%, -100%)'
  if (placement.startsWith('top')) return 'translateY(-100%)'
  if (placement.endsWith('end')) return 'translateX(-100%)'
  if (placement === 'bottom') return 'translateX(-50%)'
  if (placement === 'top') return 'translate(-50%, -100%)'
  return undefined
}

export function Popover({
  trigger,
  content,
  placement = 'bottom-start',
  className = '',
  contentClassName = '',
  closeOnContentClick = false,
}: PopoverProps) {
  const { isOpen, toggle, close } = useDisclosure()
  const triggerRef = useRef<HTMLSpanElement | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)

  useDismiss({ ref: panelRef, onDismiss: close, enabled: isOpen, clickOutside: true, escKey: true })

  const rect = isOpen && triggerRef.current ? triggerRef.current.getBoundingClientRect() : null
  const pos = rect
    ? {
        top: placement.startsWith('top')
          ? rect.top + window.scrollY
          : rect.bottom + window.scrollY + 4,
        left: placement.endsWith('end')
          ? rect.right + window.scrollX
          : placement === 'bottom' || placement === 'top'
          ? rect.left + window.scrollX + rect.width / 2
          : rect.left + window.scrollX,
      }
    : null

  return (
    <span className={`popover-wrap ${className}`} ref={triggerRef}>
      <span
        style={{ display: 'contents' }}
        onClick={(e) => { e.stopPropagation(); toggle() }}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
      >
        {trigger}
      </span>
      {isOpen && pos && createPortal(
        <div
          ref={panelRef}
          className={`popover popover--${placement} ${contentClassName}`}
          style={{ top: pos.top, left: pos.left, transform: getTransform(placement) }}
          onClick={closeOnContentClick ? close : undefined}
          role="dialog"
          aria-modal="false"
        >
          {content}
        </div>,
        document.body,
      )}
    </span>
  )
}
