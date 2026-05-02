import type { ButtonHTMLAttributes, ReactNode } from 'react'
import './IconButton.css'

export type IconButtonSize = 'sm' | 'md' | 'lg'
export type IconButtonVariant = 'ghost' | 'subtle' | 'solid' | 'destructive'

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  icon: ReactNode
  'aria-label': string
  size?: IconButtonSize
  variant?: IconButtonVariant
  className?: string
  loading?: boolean
}

export function IconButton({
  icon,
  size = 'md',
  variant = 'ghost',
  className = '',
  loading = false,
  disabled,
  ...rest
}: IconButtonProps) {
  const isDisabled = disabled || loading

  return (
    <button
      type="button"
      className={`icon-btn icon-btn--${size} icon-btn--${variant} ${loading ? 'icon-btn--loading' : ''} ${className}`}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      aria-disabled={isDisabled || undefined}
      {...rest}
    >
      <span className="icon-btn__icon" aria-hidden="true">{icon}</span>
    </button>
  )
}
