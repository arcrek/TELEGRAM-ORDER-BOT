import './Skeleton.css'

interface SkeletonBaseProps {
  className?: string
  style?: React.CSSProperties
}

export interface SkeletonLineProps extends SkeletonBaseProps {
  variant: 'line'
  width?: string | number
  height?: number
}

export interface SkeletonCircleProps extends SkeletonBaseProps {
  variant: 'circle'
  size?: number
}

export interface SkeletonRectProps extends SkeletonBaseProps {
  variant: 'rect'
  width?: string | number
  height?: number | string
  radius?: string
}

export type SkeletonProps = SkeletonLineProps | SkeletonCircleProps | SkeletonRectProps

export function Skeleton(props: SkeletonProps) {
  const { className = '', style } = props

  if (props.variant === 'circle') {
    const size = props.size ?? 40
    return (
      <span
        className={`skeleton skeleton--circle ${className}`}
        style={{ width: size, height: size, ...style }}
        aria-hidden="true"
      />
    )
  }

  if (props.variant === 'rect') {
    return (
      <span
        className={`skeleton skeleton--rect ${className}`}
        style={{
          width: props.width ?? '100%',
          height: props.height ?? 80,
          borderRadius: props.radius,
          ...style,
        }}
        aria-hidden="true"
      />
    )
  }

  return (
    <span
      className={`skeleton skeleton--line ${className}`}
      style={{
        width: props.width ?? '100%',
        height: props.height ?? 16,
        ...style,
      }}
      aria-hidden="true"
    />
  )
}
