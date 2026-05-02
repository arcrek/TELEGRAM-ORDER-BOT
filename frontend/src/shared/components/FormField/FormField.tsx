import type { ReactNode } from 'react'
import './FormField.css'

export interface FormFieldProps {
  label: string
  htmlFor?: string
  helperText?: string
  error?: string
  required?: boolean
  children: ReactNode
  className?: string
}

export function FormField({
  label,
  htmlFor,
  helperText,
  error,
  required,
  children,
  className = '',
}: FormFieldProps) {
  const helperId = helperText ? `${htmlFor}-helper` : undefined
  const errorId = error ? `${htmlFor}-error` : undefined

  return (
    <div
      className={`form-field ${error ? 'form-field--error' : ''} ${className}`}
      data-error-id={errorId}
      data-helper-id={helperId}
    >
      <label htmlFor={htmlFor} className="form-field__label">
        {label}
        {required && <span className="form-field__required" aria-hidden="true"> *</span>}
      </label>

      {children}

      {helperText && !error && (
        <p id={helperId} className="form-field__helper">{helperText}</p>
      )}
      {error && (
        <p id={errorId} className="form-field__error" role="alert">{error}</p>
      )}
    </div>
  )
}
