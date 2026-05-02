import type { ReactNode } from 'react'
import { Skeleton } from '../Skeleton'
import './ChartCard.css'

export interface ChartCardProps {
  title: string
  caption?: string
  actions?: ReactNode
  loading?: boolean
  minHeight?: number
  children: ReactNode
  className?: string
}

export function ChartCard({
  title,
  caption,
  actions,
  loading = false,
  minHeight = 240,
  children,
  className = '',
}: ChartCardProps) {
  return (
    <div className={`chart-card ${className}`}>
      <div className="chart-card__header">
        <h3 className="chart-card__title">{title}</h3>
        <div className="chart-card__actions">
          {actions}
        </div>
      </div>

      <div className="chart-card__body" style={{ minHeight }}>
        {loading ? (
          <div className="chart-card__skeleton">
            <Skeleton variant="rect" width="100%" height={minHeight - 16} radius="var(--radius-md)" />
          </div>
        ) : children}
      </div>

      {caption && (
        <p className="chart-card__caption">{caption}</p>
      )}
    </div>
  )
}
