import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import { Spinner } from '../Spinner'
import './Button.css'

export type ButtonVariant = 'primary' | 'secondary' | 'destructive'
export type ButtonTone = 'solid' | 'subtle' | 'ghost' | 'link'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonBaseProps {
  variant?: ButtonVariant
  tone?: ButtonTone
  size?: ButtonSize
  loading?: boolean
  iconLeft?: ReactNode
  iconRight?: ReactNode
  iconOnly?: boolean
  className?: string
  children?: ReactNode
}

export type ButtonProps =
  | (ButtonBaseProps & ButtonHTMLAttributes<HTMLButtonElement> & { as?: 'button' })
  | (ButtonBaseProps & AnchorHTMLAttributes<HTMLAnchorElement> & { as: 'a' })

export function Button(props: ButtonProps) {
  const {
    variant = 'secondary',
    tone = 'solid',
    size = 'md',
    loading = false,
    iconLeft,
    iconRight,
    iconOnly = false,
    className = '',
    children,
    as,
    ...rest
  } = props

  const classes = [
    'btn',
    `btn--${variant}`,
    `btn--${tone}`,
    `btn--${size}`,
    iconOnly && 'btn--icon-only',
    loading && 'btn--loading',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const content = (
    <>
      {loading && <Spinner size="xs" className="btn__spinner" />}
      {!loading && iconLeft && <span className="btn__icon btn__icon--left" aria-hidden="true">{iconLeft}</span>}
      {children && <span className="btn__text">{children}</span>}
      {iconRight && <span className="btn__icon btn__icon--right" aria-hidden="true">{iconRight}</span>}
    </>
  )

  if (as === 'a') {
    const { ...anchorRest } = rest as AnchorHTMLAttributes<HTMLAnchorElement>
    return (
      <a className={classes} {...anchorRest}>
        {content}
      </a>
    )
  }

  const { disabled, ...buttonRest } = rest as ButtonHTMLAttributes<HTMLButtonElement>
  const isDisabled = disabled || loading

  return (
    <button
      className={classes}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      aria-disabled={isDisabled || undefined}
      {...buttonRest}
    >
      {content}
    </button>
  )
}
