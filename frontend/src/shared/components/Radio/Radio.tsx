import './Radio.css'

export interface RadioProps {
  checked: boolean
  onChange: (value: string) => void
  value: string
  label?: React.ReactNode
  id?: string
  name?: string
  disabled?: boolean
  className?: string
}

export function Radio({
  checked,
  onChange,
  value,
  label,
  id,
  name,
  disabled = false,
  className = '',
}: RadioProps) {
  const inputId = id ?? `radio-${Math.random().toString(36).slice(2, 9)}`

  return (
    <label
      htmlFor={inputId}
      className={`radio ${disabled ? 'radio--disabled' : ''} ${className}`}
    >
      <span className="radio__dot-wrap">
        <input
          id={inputId}
          type="radio"
          name={name}
          value={value}
          checked={checked}
          disabled={disabled}
          className="radio__input"
          onChange={() => onChange(value)}
        />
        <span className="radio__dot" aria-hidden="true" />
      </span>
      {label && <span className="radio__label">{label}</span>}
    </label>
  )
}
