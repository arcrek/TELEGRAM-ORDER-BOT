import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { Textarea, type TextareaProps } from '../Textarea'
import { EmojiPreview, type EmojiUnit } from '../EmojiPreview'
import { useDismiss } from '../../hooks/useDismiss'
import { apiClient } from '../../lib/api'
import { getCaretCoordinates } from '../../lib/caretCoordinates'
import { matchTrigger, insertToken } from './autocompleteHelpers'
import './EmojiAutocompleteTextarea.css'

interface Placeholder {
  id: number
  name: string
  token: string
  units: EmojiUnit[]
}

export function EmojiAutocompleteTextarea(props: TextareaProps) {
  const { onChange, value, ...rest } = props
  const taRef = useRef<HTMLTextAreaElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  const [all, setAll] = useState<Placeholder[]>([])
  const [loaded, setLoaded] = useState(false)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [triggerStart, setTriggerStart] = useState(0)
  const [highlight, setHighlight] = useState(0)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const [pendingCaret, setPendingCaret] = useState<number | null>(null)

  useDismiss({ ref: panelRef, onDismiss: () => setOpen(false), escKey: false, enabled: open })

  const items = open
    ? all.filter(p => p.name.toLowerCase().includes(query.toLowerCase()))
    : []

  // Restore caret after a controlled-value update from an insertion.
  useEffect(() => {
    if (pendingCaret == null || !taRef.current) return
    const el = taRef.current
    el.focus()
    el.setSelectionRange(pendingCaret, pendingCaret)
    setPendingCaret(null)
  }, [value, pendingCaret])

  const ensureLoaded = async () => {
    if (loaded) return
    try {
      const res = await apiClient.get<Placeholder[]>('/api/emoji-placeholders')
      setAll(res.data)
    } catch {
      setAll([])
    } finally {
      setLoaded(true)
    }
  }

  const syncTrigger = (text: string, caret: number) => {
    const el = taRef.current
    if (!el) return
    const m = matchTrigger(text.slice(0, caret))
    if (!m) {
      setOpen(false)
      return
    }
    void ensureLoaded()
    setTriggerStart(m.start)
    setQuery(m.query)
    setHighlight(0)
    const rect = el.getBoundingClientRect()
    const c = getCaretCoordinates(el, caret)
    setPos({
      top: rect.top + window.scrollY + c.top - el.scrollTop + c.height,
      left: rect.left + window.scrollX + c.left - el.scrollLeft,
    })
    setOpen(true)
  }

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    onChange?.(e)
    syncTrigger(e.target.value, e.target.selectionStart ?? e.target.value.length)
  }

  const reSync = () => {
    const el = taRef.current
    if (el) syncTrigger(el.value, el.selectionStart ?? el.value.length)
  }

  const choose = (p: Placeholder) => {
    const el = taRef.current
    if (!el) return
    const caret = el.selectionStart ?? el.value.length
    const next = insertToken(String(value ?? ''), caret, triggerStart, p.token)
    el.value = next.value
    setPendingCaret(next.caret)
    setOpen(false)
    onChange?.({ target: el, currentTarget: el } as unknown as ChangeEvent<HTMLTextAreaElement>)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!open || items.length === 0) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(h => (h + 1) % items.length) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(h => (h - 1 + items.length) % items.length) }
    else if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); choose(items[highlight]) }
    else if (e.key === 'Escape') { e.preventDefault(); setOpen(false) }
  }

  return (
    <>
      <Textarea
        {...rest}
        ref={taRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onKeyUp={reSync}
        onClick={reSync}
      />
      {open && items.length > 0 && pos && createPortal(
        <div
          ref={panelRef}
          role="listbox"
          className="emoji-ac__panel"
          style={{ top: pos.top, left: pos.left }}
        >
          {items.map((p, i) => (
            <div
              key={p.id}
              role="option"
              aria-selected={i === highlight}
              className={`emoji-ac__option ${i === highlight ? 'emoji-ac__option--active' : ''}`}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={e => { e.preventDefault(); choose(p) }}
            >
              <EmojiPreview units={p.units} />
              <span className="emoji-ac__name">{p.name}</span>
              <span className="emoji-ac__token">{p.token}</span>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </>
  )
}
