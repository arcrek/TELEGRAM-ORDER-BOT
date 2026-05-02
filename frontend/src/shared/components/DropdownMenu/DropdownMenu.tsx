import {
  useRef,
  useCallback,
  type ReactNode,
  type KeyboardEvent,
} from 'react'
import { createPortal } from 'react-dom'
import { useDisclosure } from '../../hooks/useDisclosure'
import { useDismiss } from '../../hooks/useDismiss'
import './DropdownMenu.css'

export interface DropdownMenuItem {
  key: string
  label: ReactNode
  icon?: ReactNode
  disabled?: boolean
  danger?: boolean
  onClick?: () => void
  separator?: boolean
}

export interface DropdownMenuProps {
  trigger: ReactNode
  items: DropdownMenuItem[]
  placement?: 'bottom-start' | 'bottom-end'
  className?: string
}

export function DropdownMenu({
  trigger,
  items,
  placement = 'bottom-start',
  className = '',
}: DropdownMenuProps) {
  const { isOpen, open, close } = useDisclosure()
  const triggerRef = useRef<HTMLSpanElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const focusedIdx = useRef(-1)

  useDismiss({ ref: menuRef, onDismiss: close, enabled: isOpen })

  const getMenuItems = () =>
    Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])') ?? [])

  const moveFocus = useCallback((dir: 1 | -1) => {
    const menuItems = getMenuItems()
    if (!menuItems.length) return
    focusedIdx.current = Math.max(0, Math.min(menuItems.length - 1, focusedIdx.current + dir))
    menuItems[focusedIdx.current]?.focus()
  }, [])

  const handleTriggerKeyDown = (e: KeyboardEvent<HTMLSpanElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      open()
      setTimeout(() => {
        const first = menuRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
        focusedIdx.current = 0
        first?.focus()
      }, 50)
    }
  }

  const handleMenuKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); moveFocus(1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveFocus(-1) }
    else if (e.key === 'Tab') { close(); triggerRef.current?.focus() }
  }

  const rect = isOpen && triggerRef.current ? triggerRef.current.getBoundingClientRect() : null
  const pos = rect
    ? {
        top: rect.bottom + window.scrollY + 4,
        left: placement === 'bottom-start'
          ? rect.left + window.scrollX
          : rect.right + window.scrollX,
      }
    : null

  return (
    <span
      className={`dropdown-wrap ${className}`}
      ref={triggerRef}
      onKeyDown={handleTriggerKeyDown}
      role="none"
    >
      <span
        style={{ display: 'contents' }}
        onClick={(e) => { e.stopPropagation(); isOpen ? close() : open() }}
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        {trigger}
      </span>
      {isOpen && pos && createPortal(
        <div
          ref={menuRef}
          role="menu"
          className={`dropdown-menu dropdown-menu--${placement}`}
          style={{
            top: pos.top,
            left: pos.left,
            transform: placement === 'bottom-end' ? 'translateX(-100%)' : undefined,
          }}
          onKeyDown={handleMenuKeyDown}
        >
          {items.map(item => {
            if (item.separator) {
              return <div key={item.key} className="dropdown-menu__separator" role="separator" />
            }
            return (
              <button
                key={item.key}
                role="menuitem"
                disabled={item.disabled}
                className={`dropdown-menu__item ${item.danger ? 'dropdown-menu__item--danger' : ''}`}
                onClick={() => {
                  item.onClick?.()
                  close()
                  triggerRef.current?.focus()
                }}
                tabIndex={-1}
              >
                {item.icon && <span className="dropdown-menu__item-icon" aria-hidden="true">{item.icon}</span>}
                <span>{item.label}</span>
              </button>
            )
          })}
        </div>,
        document.body,
      )}
    </span>
  )
}
