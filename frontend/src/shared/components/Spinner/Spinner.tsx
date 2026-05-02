import './Spinner.css'

export interface SpinnerProps {
  size?: 'xs' | 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}

export function Spinner({ size = 'md', label = 'Loading…', className = '' }: SpinnerProps) {
  return (
    <span
      className={`spinner spinner--${size} ${className}`}
      role="status"
      aria-label={label}
    >
      <span className="spinner__ring" aria-hidden="true" />
    </span>
  )
}
