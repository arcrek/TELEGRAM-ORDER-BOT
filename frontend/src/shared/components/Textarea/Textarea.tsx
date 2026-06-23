import { forwardRef, useEffect, useRef, type TextareaHTMLAttributes } from 'react'
import './Textarea.css'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  helperText?: string
  error?: string
  autoResize?: boolean
  maxHeight?: number
  id?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({
  label,
  helperText,
  error,
  autoResize = false,
  maxHeight,
  id,
  value,
  disabled,
  className = '',
  ...rest
}, forwardedRef) {
  const textareaId = id ?? rest.name ?? `textarea-${Math.random().toString(36).slice(2, 9)}`
  const helperId = helperText ? `${textareaId}-helper` : undefined
  const errorId = error ? `${textareaId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined
  const innerRef = useRef<HTMLTextAreaElement | null>(null)

  const setRefs = (el: HTMLTextAreaElement | null) => {
    innerRef.current = el
    if (typeof forwardedRef === 'function') forwardedRef(el)
    else if (forwardedRef) forwardedRef.current = el
  }

  useEffect(() => {
    if (!autoResize || !innerRef.current) return
    const el = innerRef.current
    el.style.height = 'auto'
    const next = maxHeight ? Math.min(el.scrollHeight, maxHeight) : el.scrollHeight
    el.style.height = `${next}px`
  }, [value, autoResize, maxHeight])

  return (
    <div className={`textarea-field ${error ? 'textarea-field--error' : ''} ${disabled ? 'textarea-field--disabled' : ''} ${className}`}>
      {label && (
        <label htmlFor={textareaId} className="textarea-field__label">
          {label}
        </label>
      )}
      <textarea
        ref={setRefs}
        id={textareaId}
        value={value}
        disabled={disabled}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={describedBy}
        className="textarea-field__textarea"
        {...rest}
      />
      {helperText && !error && (
        <p id={helperId} className="textarea-field__helper">{helperText}</p>
      )}
      {error && (
        <p id={errorId} className="textarea-field__error" role="alert">{error}</p>
      )}
    </div>
  )
})
