import type { InputHTMLAttributes, ReactNode } from 'react'
import { X } from 'lucide-react'
import './Input.css'

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'prefix' | 'size'> {
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  clearable?: boolean
  onClear?: () => void
  helperText?: string
  error?: string
  prefix?: string
  suffix?: string
  size?: 'sm' | 'md' | 'lg'
  label?: string
  id?: string
}

export function Input({
  leftIcon,
  rightIcon,
  clearable,
  onClear,
  helperText,
  error,
  prefix,
  suffix,
  size = 'md',
  label,
  id,
  value,
  disabled,
  className = '',
  ...rest
}: InputProps) {
  const inputId = id ?? rest.name ?? `input-${Math.random().toString(36).slice(2, 9)}`
  const helperId = helperText ? `${inputId}-helper` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined

  const hasLeft = leftIcon || prefix
  const hasRight = rightIcon || suffix || (clearable && value)

  return (
    <div className={`input-field input-field--${size} ${error ? 'input-field--error' : ''} ${disabled ? 'input-field--disabled' : ''} ${className}`}>
      {label && (
        <label htmlFor={inputId} className="input-field__label">
          {label}
        </label>
      )}

      <div className="input-field__wrap">
        {prefix && <span className="input-field__affix input-field__affix--prefix">{prefix}</span>}
        {leftIcon && <span className="input-field__icon input-field__icon--left" aria-hidden="true">{leftIcon}</span>}

        <input
          id={inputId}
          value={value}
          disabled={disabled}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={describedBy}
          className={[
            'input-field__input',
            hasLeft && 'input-field__input--left',
            hasRight && 'input-field__input--right',
          ].filter(Boolean).join(' ')}
          {...rest}
        />

        {rightIcon && !clearable && <span className="input-field__icon input-field__icon--right" aria-hidden="true">{rightIcon}</span>}
        {clearable && value && (
          <button
            type="button"
            className="input-field__clear"
            onClick={onClear}
            aria-label="Clear"
            tabIndex={-1}
          >
            <X size={14} />
          </button>
        )}
        {suffix && <span className="input-field__affix input-field__affix--suffix">{suffix}</span>}
      </div>

      {helperText && !error && (
        <p id={helperId} className="input-field__helper">{helperText}</p>
      )}
      {error && (
        <p id={errorId} className="input-field__error" role="alert">{error}</p>
      )}
    </div>
  )
}
