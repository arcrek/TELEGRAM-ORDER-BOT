/**
 * Select/Dropdown component.
 * Premium Dark SaaS Design System.
 */
import { useState, useRef, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import './Select.css'

export interface SelectOption {
  value: string | number | boolean | null
  label: string
}

export interface SelectProps {
  options: SelectOption[]
  value: string | number | boolean | null
  onChange: (value: string | number | boolean | null) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  label?: string
}

export function Select({
  options,
  value,
  onChange,
  placeholder = 'Select...',
  disabled = false,
  className = '',
  label,
}: SelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const selectRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const selectedOption = options.find(opt => {
    // Handle null/undefined comparison
    if (opt.value === null && value === null) return true
    if (opt.value === null || value === null) return false
    return opt.value === value
  })

  const handleSelect = (optionValue: string | number | boolean | null) => {
    onChange(optionValue)
    setIsOpen(false)
  }

  return (
    <div className={`select-wrapper ${className}`}>
      {label && <label className="select-label">{label}</label>}
      <div
        ref={selectRef}
        className={`select ${isOpen ? 'open' : ''} ${disabled ? 'disabled' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
      >
        <span className="select-value">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <ChevronDown size={16} className={`select-icon ${isOpen ? 'open' : ''}`} />
        {isOpen && (
          <div className="select-dropdown">
            {options.map((option) => {
              const isSelected = option.value === null && value === null
                ? true
                : option.value === null || value === null
                ? false
                : option.value === value
              
              return (
                <div
                  key={String(option.value ?? 'null')}
                  className={`select-option ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleSelect(option.value)}
                >
                  {option.label}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

