/**
 * Premium Dark SaaS Card component.
 * Minimalist design with borders instead of shadows.
 */
import React from 'react'
import './Card.css'

export interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'elevated' | 'flat'
  onClick?: (e?: React.MouseEvent) => void
  style?: React.CSSProperties
}

export function Card({
  children,
  className = '',
  variant = 'default',
  onClick,
  style = {},
}: CardProps) {
  const classes = ['card', `card--${variant}`, className].filter(Boolean).join(' ')

  return (
    <div
      className={classes}
      style={style}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  )
}

