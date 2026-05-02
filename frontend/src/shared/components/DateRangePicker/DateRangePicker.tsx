import { useState, useRef } from 'react'
import { CalendarDays, ChevronDown } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useDismiss } from '../../hooks/useDismiss'
import './DateRangePicker.css'

export interface DateRange {
  from: Date | null
  to: Date | null
}

export type RangePreset = 'today' | '7d' | '30d' | 'this-month' | 'last-month' | 'custom'

export interface DateRangePickerProps {
  value: DateRange
  onChange: (range: DateRange, preset: RangePreset) => void
  presets?: RangePreset[]
  placeholder?: string
  size?: 'sm' | 'md'
  className?: string
}

const PRESET_LABELS: Record<RangePreset, string> = {
  today: 'Hôm nay',
  '7d': '7 ngày qua',
  '30d': '30 ngày qua',
  'this-month': 'Tháng này',
  'last-month': 'Tháng trước',
  custom: 'Tuỳ chỉnh',
}

function resolvePreset(preset: RangePreset): DateRange {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const todayEnd = new Date(today.getTime() + 86400000 - 1)

  switch (preset) {
    case 'today':
      return { from: today, to: todayEnd }
    case '7d':
      return { from: new Date(today.getTime() - 6 * 86400000), to: todayEnd }
    case '30d':
      return { from: new Date(today.getTime() - 29 * 86400000), to: todayEnd }
    case 'this-month': {
      const start = new Date(now.getFullYear(), now.getMonth(), 1)
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59)
      return { from: start, to: end }
    }
    case 'last-month': {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      const end = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59)
      return { from: start, to: end }
    }
    default:
      return { from: null, to: null }
  }
}

function formatRange(range: DateRange): string {
  if (!range.from && !range.to) return ''
  const fmt = (d: Date) => d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: '2-digit' })
  if (range.from && range.to) return `${fmt(range.from)} – ${fmt(range.to)}`
  if (range.from) return `từ ${fmt(range.from)}`
  return `đến ${fmt(range.to!)}`
}

export function DateRangePicker({
  value,
  onChange,
  presets = ['today', '7d', '30d', 'this-month', 'last-month', 'custom'],
  placeholder = 'Chọn khoảng thời gian',
  size = 'md',
  className = '',
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false)
  const [activePreset, setActivePreset] = useState<RangePreset | null>(null)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)

  useDismiss({ ref: panelRef, onDismiss: () => setOpen(false), enabled: open })

  const display = formatRange(value)
  const rect = open && triggerRef.current ? triggerRef.current.getBoundingClientRect() : null

  const handlePreset = (preset: RangePreset) => {
    setActivePreset(preset)
    if (preset !== 'custom') {
      onChange(resolvePreset(preset), preset)
      setOpen(false)
    }
  }

  const handleCustomApply = () => {
    if (!customFrom || !customTo) return
    onChange({ from: new Date(customFrom), to: new Date(customTo + 'T23:59:59') }, 'custom')
    setOpen(false)
  }

  return (
    <div className={`drp drp--${size} ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        className={`drp__trigger ${open ? 'drp__trigger--open' : ''}`}
        onClick={() => setOpen(v => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <CalendarDays size={14} className="drp__cal-icon" />
        <span className="drp__display">
          {display || <span className="drp__placeholder">{placeholder}</span>}
        </span>
        <ChevronDown size={14} className={`drp__chevron ${open ? 'drp__chevron--open' : ''}`} />
      </button>

      {open && rect && createPortal(
        <div
          ref={panelRef}
          className="drp__panel"
          style={{ top: rect.bottom + window.scrollY + 4, left: rect.left + window.scrollX }}
          role="dialog"
          aria-label="Date range picker"
        >
          <div className="drp__presets">
            {presets.map(p => (
              <button
                key={p}
                type="button"
                className={`drp__preset ${activePreset === p ? 'drp__preset--active' : ''}`}
                onClick={() => handlePreset(p)}
              >
                {PRESET_LABELS[p]}
              </button>
            ))}
          </div>

          {activePreset === 'custom' && (
            <div className="drp__custom">
              <label className="drp__custom-label">
                Từ ngày
                <input type="date" className="drp__date-input" value={customFrom} onChange={e => setCustomFrom(e.target.value)} />
              </label>
              <label className="drp__custom-label">
                Đến ngày
                <input type="date" className="drp__date-input" value={customTo} onChange={e => setCustomTo(e.target.value)} />
              </label>
              <button type="button" className="drp__apply" onClick={handleCustomApply} disabled={!customFrom || !customTo}>
                Áp dụng
              </button>
            </div>
          )}
        </div>,
        document.body,
      )}
    </div>
  )
}
