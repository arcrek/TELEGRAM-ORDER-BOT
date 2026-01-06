/**
 * Premium Dark SaaS Input component.
 * Minimalist design with borders instead of shadows.
 * NO glassmorphism.
 */
import React from 'react'
import './Input.css'

export interface InputProps {
  label?: string
  placeholder?: string
  value?: string
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
  onKeyPress?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  type?: string
  disabled?: boolean
  error?: string
  className?: string
  name?: string
  id?: string
  required?: boolean
}

export function Input({
  label,
  placeholder,
  value,
  onChange,
  onKeyPress,
  type = 'text',
  disabled = false,
  error,
  className = '',
  name,
  id,
  required,
}: InputProps) {
  const inputId = id || name || `input-${Math.random().toString(36).substr(2, 9)}`

  const inputClasses = [
    'input',
    error && 'input--error',
    disabled && 'input--disabled',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="input-wrapper">
      {label && (
        <label htmlFor={inputId} className="input-label">
          {label}
        </label>
      )}
      <input
        id={inputId}
        name={name}
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onKeyPress={onKeyPress}
        disabled={disabled}
        required={required}
        className={inputClasses}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? `${inputId}-error` : undefined}
      />
      {error && (
        <span id={`${inputId}-error`} className="input-error" role="alert">
          {error}
        </span>
      )}
    </div>
  )
}

