import { useEffect, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useFocusTrap } from '../../hooks/useFocusTrap'
import { IconButton } from '../IconButton'
import './Modal.css'

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'full'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children?: ReactNode
  footer?: ReactNode
  size?: ModalSize
  closeOnBackdrop?: boolean
  closeOnEsc?: boolean
  hideCloseButton?: boolean
  stickyHeader?: boolean
  stickyFooter?: boolean
  initialFocusRef?: RefObject<HTMLElement | null>
  'aria-label'?: string
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
  closeOnEsc = true,
  hideCloseButton = false,
  stickyHeader = false,
  stickyFooter = false,
  initialFocusRef,
  'aria-label': ariaLabel,
}: ModalProps) {
  const dialogRef = useFocusTrap<HTMLDivElement>(open)

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  // Esc key
  useEffect(() => {
    if (!open || !closeOnEsc) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, closeOnEsc, onClose])

  // Focus initialFocusRef if provided
  useEffect(() => {
    if (open && initialFocusRef?.current) {
      const raf = requestAnimationFrame(() => initialFocusRef.current?.focus())
      return () => cancelAnimationFrame(raf)
    }
  }, [open, initialFocusRef])

  if (!open) return null

  const titleId = title ? 'modal-title' : undefined
  const descId = description ? 'modal-desc' : undefined

  return createPortal(
    <div
      className="modal-backdrop"
      onClick={closeOnBackdrop ? onClose : undefined}
      aria-hidden="true"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        aria-label={ariaLabel}
        className={`modal modal--${size} ${stickyHeader ? 'modal--sticky-header' : ''} ${stickyFooter ? 'modal--sticky-footer' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        {(title || !hideCloseButton) && (
          <div className="modal__header">
            <div className="modal__header-text">
              {title && <h2 id={titleId} className="modal__title">{title}</h2>}
              {description && <p id={descId} className="modal__description">{description}</p>}
            </div>
            {!hideCloseButton && (
              <IconButton
                icon={<X />}
                aria-label="Close dialog"
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="modal__close"
              />
            )}
          </div>
        )}

        {children && <div className="modal__body">{children}</div>}

        {footer && <div className="modal__footer">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
