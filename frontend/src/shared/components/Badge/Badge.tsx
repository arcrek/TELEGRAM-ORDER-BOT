import './Badge.css'

export type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
export type OrderStatus = 'pending' | 'paid' | 'processing' | 'delivered' | 'cancelled' | 'shipped' | 'refunded'

const STATUS_VARIANT: Record<OrderStatus, BadgeVariant> = {
  pending: 'warning',
  paid: 'info',
  processing: 'info',
  delivered: 'success',
  cancelled: 'danger',
  shipped: 'info',
  refunded: 'neutral',
}

export interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  status?: OrderStatus
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}

export function Badge({
  children,
  variant,
  status,
  size = 'md',
  dot = false,
  className = '',
}: BadgeProps) {
  const resolvedVariant = status ? STATUS_VARIANT[status] : (variant ?? 'default')

  return (
    <span
      className={`badge badge--${resolvedVariant} badge--${size} ${className}`}
      data-status={status}
    >
      {dot && <span className="badge__dot" aria-hidden="true" />}
      {children}
    </span>
  )
}
