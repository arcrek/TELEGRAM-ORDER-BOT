/**
 * Premium Dark SaaS Button component.
 * Minimalist design with borders instead of shadows.
 * NO gradients.
 */
import React from 'react'
import './Button.css'

export interface ButtonProps {
  children: React.ReactNode
  variant?: 'primary' | 'secondary' | 'outline'
  size?: 'small' | 'medium' | 'large'
  disabled?: boolean
  onClick?: () => void
  className?: string
  type?: 'button' | 'submit' | 'reset'
  as?: 'button' | 'a'
  href?: string
  title?: string
  style?: React.CSSProperties
}

export function Button({
  children,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  onClick,
  className = '',
  type = 'button',
  as = 'button',
  href,
  title,
  style: externalStyle,
}: ButtonProps) {
  const classes = [
    'button',
    `button--${variant}`,
    `button--${size}`,
    disabled && 'button--disabled',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const style: React.CSSProperties = {
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    ...externalStyle,
  }

  if (as === 'a') {
    return (
      <a
        href={href}
        className={classes}
        style={style}
        onClick={disabled ? undefined : onClick}
        aria-disabled={disabled}
        title={title}
      >
        {children}
      </a>
    )
  }

  return (
    <button
      type={type}
      className={classes}
      style={style}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </button>
  )
}

