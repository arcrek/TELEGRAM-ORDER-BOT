import './Switch.css'

export interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  label?: string
  id?: string
  size?: 'sm' | 'md'
  className?: string
}

export function Switch({
  checked,
  onChange,
  disabled = false,
  label,
  id,
  size = 'md',
  className = '',
}: SwitchProps) {
  const switchId = id ?? `switch-${Math.random().toString(36).slice(2, 9)}`

  return (
    <label
      htmlFor={switchId}
      className={`switch switch--${size} ${disabled ? 'switch--disabled' : ''} ${className}`}
    >
      <input
        id={switchId}
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        disabled={disabled}
        className="switch__input"
      />
      <span className="switch__track" aria-hidden="true">
        <span className="switch__thumb" />
      </span>
      {label && <span className="switch__label">{label}</span>}
    </label>
  )
}
