import { useState, useRef, useMemo, type ReactNode } from 'react'
import { ChevronDown, Check, X, Search } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useDismiss } from '../../hooks/useDismiss'
import './Select.css'

export interface SelectOption<V = string> {
  value: V
  label: string
  icon?: ReactNode
  disabled?: boolean
  group?: string
}

export interface SelectProps<V = string> {
  options: SelectOption<V>[]
  value: V | null
  onChange: (value: V | null) => void
  placeholder?: string
  label?: string
  helperText?: string
  error?: string
  disabled?: boolean
  clearable?: boolean
  searchable?: boolean
  size?: 'sm' | 'md' | 'lg'
  className?: string
  id?: string
  renderOption?: (opt: SelectOption<V>) => ReactNode
}

export function Select<V = string>({
  options,
  value,
  onChange,
  placeholder = 'Chọn...',
  label,
  helperText,
  error,
  disabled = false,
  clearable = false,
  searchable = false,
  size = 'md',
  className = '',
  id,
  renderOption,
}: SelectProps<V>) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const searchRef = useRef<HTMLInputElement | null>(null)
  const inputId = id ?? `select-${Math.random().toString(36).slice(2, 9)}`

  useDismiss({ ref: panelRef, onDismiss: () => { setOpen(false); setQuery('') }, enabled: open })

  const selected = options.find(o => o.value === value) ?? null

  const filtered = useMemo(() => {
    if (!query) return options
    const q = query.toLowerCase()
    return options.filter(o => o.label.toLowerCase().includes(q))
  }, [options, query])

  const openPanel = () => {
    if (disabled) return
    setOpen(true)
    setTimeout(() => searchRef.current?.focus(), 50)
  }

  const handleSelect = (opt: SelectOption<V>) => {
    if (opt.disabled) return
    onChange(opt.value)
    setOpen(false)
    setQuery('')
    triggerRef.current?.focus()
  }

  const rect = open && triggerRef.current ? triggerRef.current.getBoundingClientRect() : null

  return (
    <div className={`select-field select-field--${size} ${error ? 'select-field--error' : ''} ${disabled ? 'select-field--disabled' : ''} ${className}`}>
      {label && <label htmlFor={inputId} className="select-field__label">{label}</label>}

      <div className="select-field__wrap">
        <button
          ref={triggerRef}
          id={inputId}
          type="button"
          disabled={disabled}
          className={`select-field__trigger ${open ? 'select-field__trigger--open' : ''}`}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-invalid={error ? 'true' : undefined}
          onClick={openPanel}
        >
          <span className="select-field__value">
            {selected ? (
              <>
                {selected.icon && <span className="select-field__icon">{selected.icon}</span>}
                {selected.label}
              </>
            ) : (
              <span className="select-field__placeholder">{placeholder}</span>
            )}
          </span>
          <span className="select-field__controls">
            {clearable && value !== null && (
              <span
                className="select-field__clear"
                role="button"
                aria-label="Clear selection"
                onClick={e => { e.stopPropagation(); onChange(null) }}
              >
                <X size={12} />
              </span>
            )}
            <ChevronDown size={14} className={`select-field__chevron ${open ? 'select-field__chevron--open' : ''}`} />
          </span>
        </button>
      </div>

      {helperText && !error && <p className="select-field__helper">{helperText}</p>}
      {error && <p className="select-field__error" role="alert">{error}</p>}

      {open && rect && createPortal(
        <div
          ref={panelRef}
          role="listbox"
          aria-label={label}
          className="select-field__panel"
          style={{
            top: rect.bottom + window.scrollY + 4,
            left: rect.left + window.scrollX,
            width: rect.width,
          }}
        >
          {searchable && (
            <div className="select-field__search">
              <Search size={12} className="select-field__search-icon" />
              <input
                ref={searchRef}
                type="text"
                className="select-field__search-input"
                placeholder="Tìm..."
                value={query}
                onChange={e => setQuery(e.target.value)}
                onClick={e => e.stopPropagation()}
              />
            </div>
          )}
          <div className="select-field__options">
            {filtered.length === 0
              ? <div className="select-field__no-results">Không tìm thấy</div>
              : filtered.map(opt => (
                  <div
                    key={String(opt.value)}
                    role="option"
                    aria-selected={opt.value === value}
                    aria-disabled={opt.disabled}
                    className={[
                      'select-field__option',
                      opt.value === value && 'select-field__option--selected',
                      opt.disabled && 'select-field__option--disabled',
                    ].filter(Boolean).join(' ')}
                    onClick={() => handleSelect(opt)}
                  >
                    {renderOption ? renderOption(opt) : (
                      <>
                        {opt.icon && <span className="select-field__icon">{opt.icon}</span>}
                        <span>{opt.label}</span>
                      </>
                    )}
                    {opt.value === value && <Check size={12} className="select-field__check" />}
                  </div>
                ))}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
