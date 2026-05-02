import './Checkbox.css'

export interface CheckboxProps {
  checked: boolean
  onChange: (checked: boolean) => void
  indeterminate?: boolean
  disabled?: boolean
  label?: React.ReactNode
  id?: string
  name?: string
  value?: string
  className?: string
}

export function Checkbox({
  checked,
  onChange,
  indeterminate = false,
  disabled = false,
  label,
  id,
  name,
  value,
  className = '',
}: CheckboxProps) {
  const inputId = id ?? `cb-${Math.random().toString(36).slice(2, 9)}`

  return (
    <label
      htmlFor={inputId}
      className={`checkbox ${disabled ? 'checkbox--disabled' : ''} ${className}`}
    >
      <span className="checkbox__box-wrap">
        <input
          id={inputId}
          type="checkbox"
          name={name}
          value={value}
          checked={checked}
          disabled={disabled}
          className="checkbox__input"
          ref={el => { if (el) el.indeterminate = indeterminate }}
          onChange={e => onChange(e.target.checked)}
          aria-checked={indeterminate ? 'mixed' : checked}
        />
        <span className="checkbox__box" aria-hidden="true">
          {indeterminate ? (
            <svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          ) : (
            <svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <polyline points="2,6 5,9 10,3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </span>
      </span>
      {label && <span className="checkbox__label">{label}</span>}
    </label>
  )
}
