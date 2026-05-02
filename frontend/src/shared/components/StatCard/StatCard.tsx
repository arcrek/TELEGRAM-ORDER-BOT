import type { ReactNode } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Skeleton } from '../Skeleton'
import './StatCard.css'

export interface StatCardProps {
  label: string
  value: string | number
  delta?: number | null
  deltaLabel?: string
  icon?: ReactNode
  sparkline?: number[]
  loading?: boolean
  className?: string
  size?: 'sm' | 'md'
}

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data.length) return null
  const max = Math.max(...data, 1)
  const min = Math.min(...data)
  const range = max - min || 1
  const W = 80
  const H = 32
  const step = W / (data.length - 1)

  const points = data
    .map((v, i) => `${i * step},${H - ((v - min) / range) * H}`)
    .join(' ')

  const fillPoints = `0,${H} ${points} ${W},${H}`
  const color = positive ? 'var(--success-500)' : 'var(--danger-500)'

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      className="stat-card__sparkline"
      aria-hidden="true"
    >
      <polygon points={fillPoints} fill={color} opacity="0.15" />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function StatCard({
  label,
  value,
  delta,
  deltaLabel,
  icon,
  sparkline,
  loading = false,
  className = '',
  size = 'md',
}: StatCardProps) {
  const isPositive = delta !== null && delta !== undefined && delta >= 0
  const deltaAbs = delta !== null && delta !== undefined ? Math.abs(delta) : null

  return (
    <div className={`stat-card stat-card--${size} ${className}`}>
      <div className="stat-card__header">
        <span className="stat-card__label">{label}</span>
        {icon && <span className="stat-card__icon" aria-hidden="true">{icon}</span>}
      </div>

      {loading ? (
        <div className="stat-card__loading">
          <Skeleton variant="line" width="60%" height={28} />
          <Skeleton variant="line" width="40%" height={14} />
        </div>
      ) : (
        <>
          <div className="stat-card__value-row">
            <span className="stat-card__value num">{value}</span>
            {deltaAbs !== null && (
              <span className={`stat-card__delta stat-card__delta--${isPositive ? 'up' : 'down'}`}>
                {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                <span>{deltaAbs}%</span>
              </span>
            )}
            {delta === null && (
              <span className="stat-card__delta stat-card__delta--neutral">
                <Minus size={12} />
              </span>
            )}
          </div>
          {deltaLabel && <p className="stat-card__sub">{deltaLabel}</p>}
          {sparkline && sparkline.length > 1 && (
            <Sparkline data={sparkline} positive={isPositive} />
          )}
        </>
      )}
    </div>
  )
}
