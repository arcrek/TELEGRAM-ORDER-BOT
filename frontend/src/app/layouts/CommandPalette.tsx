import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { LucideIcon } from 'lucide-react'
import {
  Search, BarChart2, Package, Layers, Star, ShoppingCart, Bell, Upload,
  Database, Gift, Settings, RotateCcw,
} from 'lucide-react'
import { useFocusTrap } from '../../shared/hooks/useFocusTrap'
import { ROUTES } from '../routes'
import './CommandPalette.css'

const ICON_MAP: Record<string, LucideIcon> = {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell,
  Upload, Database, Gift, Settings, RotateCcw,
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [focusIdx, setFocusIdx] = useState(0)
  const dialogRef = useFocusTrap<HTMLDivElement>(open)
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setFocusIdx(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const filtered = ROUTES.filter(r =>
    !query || t(r.labelKey, r.key).toLowerCase().includes(query.toLowerCase()),
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusIdx(i => (i + 1) % Math.max(1, filtered.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusIdx(i => (i - 1 + filtered.length) % Math.max(1, filtered.length))
    } else if (e.key === 'Enter' && filtered[focusIdx]) {
      navigate(filtered[focusIdx].path)
      onClose()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  useEffect(() => {
    setFocusIdx(0)
  }, [query])

  if (!open) return null

  return createPortal(
    <div className="cmd-backdrop" onClick={onClose} aria-hidden="false">
      <div
        ref={dialogRef}
        className="cmd-palette"
        role="dialog"
        aria-modal="true"
        aria-label={t('common.search', 'Tìm kiếm')}
        onClick={e => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="cmd-palette__input-wrap">
          <Search size={16} className="cmd-palette__search-icon" />
          <input
            ref={inputRef}
            type="text"
            className="cmd-palette__input"
            placeholder={t('common.searchPlaceholder', 'Tìm trang...')}
            value={query}
            onChange={e => setQuery(e.target.value)}
            aria-label={t('common.search', 'Tìm kiếm')}
          />
          <kbd className="cmd-palette__esc">Esc</kbd>
        </div>

        <div className="cmd-palette__results" role="listbox">
          {filtered.length === 0 ? (
            <div className="cmd-palette__empty">{t('common.noResults', 'Không tìm thấy')}</div>
          ) : (
            filtered.map((route, idx) => {
              const Icon = ICON_MAP[route.iconName]
              const label = t(route.labelKey, route.key)
              return (
                <button
                  key={route.key}
                  role="option"
                  aria-selected={idx === focusIdx}
                  className={`cmd-palette__item ${idx === focusIdx ? 'cmd-palette__item--focused' : ''}`}
                  onClick={() => { navigate(route.path); onClose() }}
                  onMouseEnter={() => setFocusIdx(idx)}
                >
                  {Icon && <Icon size={14} />}
                  <span>{label}</span>
                  <span className="cmd-palette__item-path">{route.path}</span>
                </button>
              )
            })
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
