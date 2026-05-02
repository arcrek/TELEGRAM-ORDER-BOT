import { useState, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import './Tooltip.css'

export type TooltipPlacement = 'top' | 'bottom' | 'left' | 'right'

export interface TooltipProps {
  content: ReactNode
  placement?: TooltipPlacement
  delay?: number
  disabled?: boolean
  children: ReactNode
}

export function Tooltip({
  content,
  placement = 'top',
  delay = 400,
  disabled = false,
  children,
}: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapRef = useRef<HTMLSpanElement | null>(null)

  if (disabled || !content) return <>{children}</>

  const show = () => {
    timerRef.current = setTimeout(() => {
      if (!wrapRef.current) return
      const rect = wrapRef.current.getBoundingClientRect()
      const gap = 6
      let top = 0, left = 0

      if (placement === 'top') {
        top = rect.top + window.scrollY - gap
        left = rect.left + window.scrollX + rect.width / 2
      } else if (placement === 'bottom') {
        top = rect.bottom + window.scrollY + gap
        left = rect.left + window.scrollX + rect.width / 2
      } else if (placement === 'left') {
        top = rect.top + window.scrollY + rect.height / 2
        left = rect.left + window.scrollX - gap
      } else {
        top = rect.top + window.scrollY + rect.height / 2
        left = rect.right + window.scrollX + gap
      }

      setPos({ top, left })
      setVisible(true)
    }, delay)
  }

  const hide = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
  }

  return (
    <>
      <span
        ref={wrapRef}
        style={{ display: 'contents' }}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        {children}
      </span>
      {visible && createPortal(
        <div
          className={`tooltip tooltip--${placement}`}
          style={{ top: pos.top, left: pos.left }}
          role="tooltip"
          aria-hidden="true"
        >
          {content}
        </div>,
        document.body,
      )}
    </>
  )
}
