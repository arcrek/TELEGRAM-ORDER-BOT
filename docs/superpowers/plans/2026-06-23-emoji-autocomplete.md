# @emo Autocomplete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an @-mention-style autocomplete to the dashboard's multi-line text fields: typing `@emo` opens a caret-anchored popup of configured emoji placeholders (with thumbnail previews); selecting one inserts the `{emo:<id>}` token.

**Architecture:** A reusable `EmojiAutocompleteTextarea` wraps the shared `<Textarea>` (made ref-forwarding), watches the caret for an `@emo<query>` trigger via pure helpers, positions a portal popup at the caret using a mirror-div `getCaretCoordinates` util, and on select rewrites the trigger span to `{emo:<id>}` through the field's existing controlled `onChange`. Frontend-only; reuses the existing `/api/emoji-placeholders` endpoint and `EmojiPreview` component.

**Tech Stack:** React 18 + TypeScript, Vite, axios (`apiClient`), vitest + @testing-library/react. No new dependencies, no backend changes.

## Global Constraints

- **Branch:** `feat/emoji-autocomplete` (off `main`, which already has the placeholders + thumbnail features). Frontend-only.
- **Scope:** the 6 multi-line `Textarea` fields — Notifications `notif-msg`; Products `-desc` and `-upgrade`; BotUiSettings `bui-upload`, `bui-product`, `bui-variation`. Chat-ID textareas and single-line name inputs are OUT of scope.
- **Trigger:** regex `/@emo([\p{L}\p{N}_]*)$/u` on the text before the caret; the captured group is the live filter query (contiguous word chars, no spaces). Insert replaces the matched `@emo<query>` span with the placeholder's `{emo:<id>}` token (numeric id — `token` field from the API).
- **Popup:** caret-anchored via a mirror-div `getCaretCoordinates`; rendered in a portal to `document.body`; dismissed via the existing `useDismiss` hook (outside-click) + an Escape handler.
- **Controlled-field integration:** every consumer reads only `e.target.value`; insertion fires `onChange` with a synthetic event whose `target` is the textarea, then restores the caret in a `value`-effect. No page handler changes beyond swapping the component.
- **Data:** `GET /api/emoji-placeholders` returns `{ id, name, token, units }`; fetched lazily on first open, cached in the component. Telegram/network mocked in tests.
- Components live in per-component folders with an `index.ts` re-export (mirror `Textarea/`). `EmojiPreview` is a flat file at `shared/components/EmojiPreview.tsx` exporting `EmojiPreview` + `EmojiUnit`.
- Frontend tests run with `CI=true npx vitest run` (`npm test` is watch mode and hangs). Build gate: `npm run build` (tsc). Lint: `npx eslint <file>`. Keep imports at top. Commit after each task.

---

## File Structure

**Create:**
- `frontend/src/shared/lib/caretCoordinates.ts` — mirror-div caret pixel measurement
- `frontend/src/shared/lib/caretCoordinates.test.ts` — smoke test
- `frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.ts` — pure `matchTrigger` + `insertToken`
- `frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.test.ts`
- `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.tsx`
- `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.test.tsx`
- `frontend/src/shared/components/EmojiAutocompleteTextarea/index.ts`

**Modify:**
- `frontend/src/shared/components/Textarea/Textarea.tsx` — forward the textarea ref
- `frontend/src/pages/NotificationsPage.tsx`, `ProductsPage.tsx`, `BotUiSettingsPage.tsx` — swap the 6 fields

---

### Task 1: Make `Textarea` forward its ref

**Files:**
- Modify: `frontend/src/shared/components/Textarea/Textarea.tsx`
- Test: `frontend/src/shared/components/Textarea/Textarea.test.tsx` (create)

**Interfaces:**
- Produces: `Textarea` now accepts a `ref: Ref<HTMLTextAreaElement>` that resolves to the underlying `<textarea>`; all existing props/behavior (autoResize, label, helper, error) unchanged.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/shared/components/Textarea/Textarea.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { useRef, useEffect } from 'react'
import { render, screen } from '@testing-library/react'
import { Textarea } from './Textarea'

function Harness({ onEl }: { onEl: (el: HTMLTextAreaElement | null) => void }) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { onEl(ref.current) }, [onEl])
  return <Textarea ref={ref} value="hi" onChange={() => {}} aria-label="t" />
}

describe('Textarea ref forwarding', () => {
  it('exposes the underlying textarea element via ref', () => {
    let captured: HTMLTextAreaElement | null = null
    render(<Harness onEl={el => { captured = el }} />)
    expect(captured).toBe(screen.getByLabelText('t'))
    expect(captured?.tagName).toBe('TEXTAREA')
  })

  it('still renders value and passes through props', () => {
    render(<Textarea value="hello" onChange={() => {}} rows={3} aria-label="x" />)
    const ta = screen.getByLabelText('x') as HTMLTextAreaElement
    expect(ta.value).toBe('hello')
    expect(ta.rows).toBe(3)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && CI=true npx vitest run src/shared/components/Textarea/Textarea.test.tsx`
Expected: FAIL (the ref resolves to `null` / is not the textarea — current component doesn't forward).

- [ ] **Step 3: Convert `Textarea` to forwardRef with a merged ref**

Replace the top of `frontend/src/shared/components/Textarea/Textarea.tsx` — change the import and the function declaration to `forwardRef`, keep the internal `innerRef` for autoResize, and merge it with the forwarded ref on the `<textarea>`:

```tsx
import { forwardRef, useEffect, useRef, type TextareaHTMLAttributes } from 'react'
import './Textarea.css'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  helperText?: string
  error?: string
  autoResize?: boolean
  maxHeight?: number
  id?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({
  label,
  helperText,
  error,
  autoResize = false,
  maxHeight,
  id,
  value,
  disabled,
  className = '',
  ...rest
}, forwardedRef) {
  const textareaId = id ?? rest.name ?? `textarea-${Math.random().toString(36).slice(2, 9)}`
  const helperId = helperText ? `${textareaId}-helper` : undefined
  const errorId = error ? `${textareaId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined
  const innerRef = useRef<HTMLTextAreaElement>(null)

  const setRefs = (el: HTMLTextAreaElement | null) => {
    innerRef.current = el
    if (typeof forwardedRef === 'function') forwardedRef(el)
    else if (forwardedRef) forwardedRef.current = el
  }

  useEffect(() => {
    if (!autoResize || !innerRef.current) return
    const el = innerRef.current
    el.style.height = 'auto'
    const next = maxHeight ? Math.min(el.scrollHeight, maxHeight) : el.scrollHeight
    el.style.height = `${next}px`
  }, [value, autoResize, maxHeight])

  return (
    <div className={`textarea-field ${error ? 'textarea-field--error' : ''} ${disabled ? 'textarea-field--disabled' : ''} ${className}`}>
      {label && (
        <label htmlFor={textareaId} className="textarea-field__label">
          {label}
        </label>
      )}
      <textarea
        ref={setRefs}
        id={textareaId}
        value={value}
        disabled={disabled}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={describedBy}
        className="textarea-field__textarea"
        {...rest}
      />
      {helperText && !error && (
        <p id={helperId} className="textarea-field__helper">{helperText}</p>
      )}
      {error && (
        <p id={errorId} className="textarea-field__error" role="alert">{error}</p>
      )}
    </div>
  )
})
```

(The `Textarea/index.ts` re-export `export { Textarea } from './Textarea'` continues to work unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && CI=true npx vitest run src/shared/components/Textarea/Textarea.test.tsx`
Expected: PASS (both).

- [ ] **Step 5: Build + lint + full test (no regressions in other Textarea users)**

Run: `cd frontend && npm run build` (succeeds), `npx eslint src/shared/components/Textarea/Textarea.tsx` (clean), `CI=true npx vitest run` (all pass).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/shared/components/Textarea/Textarea.tsx frontend/src/shared/components/Textarea/Textarea.test.tsx
git commit -m "feat(textarea): forward ref to underlying textarea element"
```

---

### Task 2: Pure helpers — `matchTrigger` + `insertToken`

**Files:**
- Create: `frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.ts`
- Test: `frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.test.ts`

**Interfaces:**
- Produces:
  - `matchTrigger(textBeforeCaret: string) -> { query: string; start: number } | null`
  - `insertToken(value: string, caret: number, matchStart: number, token: string) -> { value: string; caret: number }`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { matchTrigger, insertToken } from './autocompleteHelpers'

describe('matchTrigger', () => {
  it('matches @emo with empty query', () => {
    expect(matchTrigger('hello @emo')).toEqual({ query: '', start: 6 })
  })
  it('captures the contiguous query', () => {
    expect(matchTrigger('say @emohead')).toEqual({ query: 'head', start: 4 })
  })
  it('returns null when no trigger before caret', () => {
    expect(matchTrigger('no trigger here')).toBeNull()
  })
  it('returns null when a space breaks the trigger', () => {
    expect(matchTrigger('@emo head')).toBeNull()
  })
  it('matches at the very start', () => {
    expect(matchTrigger('@emo')).toEqual({ query: '', start: 0 })
  })
})

describe('insertToken', () => {
  it('replaces the trigger span with the token and returns caret after it', () => {
    // value: "hi @emohe more", caret at end of "@emohe" (index 9), matchStart 3
    const value = 'hi @emohe more'
    const result = insertToken(value, 9, 3, '{emo:5}')
    expect(result.value).toBe('hi {emo:5} more')
    expect(result.caret).toBe(3 + '{emo:5}'.length)
  })
  it('works at the end of the string', () => {
    const result = insertToken('go @emo', 7, 3, '{emo:12}')
    expect(result.value).toBe('go {emo:12}')
    expect(result.caret).toBe(3 + '{emo:12}'.length)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && CI=true npx vitest run src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.test.ts`
Expected: FAIL (cannot resolve `./autocompleteHelpers`).

- [ ] **Step 3: Write the helpers**

Create `frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.ts`:

```ts
const TRIGGER_RE = /@emo([\p{L}\p{N}_]*)$/u

export interface TriggerMatch {
  query: string
  start: number
}

/** Detect an `@emo<query>` trigger immediately before the caret. */
export function matchTrigger(textBeforeCaret: string): TriggerMatch | null {
  const m = TRIGGER_RE.exec(textBeforeCaret)
  if (!m) return null
  return { query: m[1], start: textBeforeCaret.length - m[0].length }
}

/** Replace value[matchStart..caret] with token; return new value + caret after token. */
export function insertToken(
  value: string,
  caret: number,
  matchStart: number,
  token: string,
): { value: string; caret: number } {
  const next = value.slice(0, matchStart) + token + value.slice(caret)
  return { value: next, caret: matchStart + token.length }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && CI=true npx vitest run src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.test.ts`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.ts frontend/src/shared/components/EmojiAutocompleteTextarea/autocompleteHelpers.test.ts
git commit -m "feat(emoji-autocomplete): trigger-match + token-insert helpers"
```

---

### Task 3: `getCaretCoordinates` mirror-div util

**Files:**
- Create: `frontend/src/shared/lib/caretCoordinates.ts`
- Test: `frontend/src/shared/lib/caretCoordinates.test.ts`

**Interfaces:**
- Produces: `getCaretCoordinates(el: HTMLTextAreaElement, position: number) -> { top: number; left: number; height: number }` (offsets relative to the textarea's padding box).

- [ ] **Step 1: Write the smoke test**

Create `frontend/src/shared/lib/caretCoordinates.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { getCaretCoordinates } from './caretCoordinates'

describe('getCaretCoordinates', () => {
  it('returns numeric coords without throwing and cleans up the mirror node', () => {
    const ta = document.createElement('textarea')
    ta.value = 'hello world'
    document.body.appendChild(ta)
    const before = document.body.childElementCount
    const coords = getCaretCoordinates(ta, 5)
    expect(typeof coords.top).toBe('number')
    expect(typeof coords.left).toBe('number')
    expect(typeof coords.height).toBe('number')
    expect(document.body.childElementCount).toBe(before) // mirror div removed
    document.body.removeChild(ta)
  })
})
```

> Note: jsdom has no layout engine, so the numeric values are 0 here; pixel correctness is verified manually in the browser (Task 5 manual check). This test guards the contract + cleanup.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && CI=true npx vitest run src/shared/lib/caretCoordinates.test.ts`
Expected: FAIL (cannot resolve `./caretCoordinates`).

- [ ] **Step 3: Write the util**

Create `frontend/src/shared/lib/caretCoordinates.ts`:

```ts
// Mirror-div caret coordinate measurement (standard textarea-caret technique).
const MIRROR_PROPS = [
  'boxSizing', 'width', 'height', 'overflowX', 'overflowY',
  'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
  'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'fontStyle', 'fontVariant', 'fontWeight', 'fontStretch', 'fontSize',
  'lineHeight', 'fontFamily', 'textAlign', 'textTransform', 'textIndent',
  'letterSpacing', 'wordSpacing', 'tabSize', 'whiteSpace', 'wordWrap',
] as const

export interface CaretCoords {
  top: number
  left: number
  height: number
}

export function getCaretCoordinates(el: HTMLTextAreaElement, position: number): CaretCoords {
  const doc = el.ownerDocument
  const computed = window.getComputedStyle(el)
  const div = doc.createElement('div')
  doc.body.appendChild(div)

  const style = div.style
  style.position = 'absolute'
  style.visibility = 'hidden'
  style.whiteSpace = 'pre-wrap'
  style.wordWrap = 'break-word'
  style.overflow = 'hidden'
  // camelCase property names require bracket assignment, NOT setProperty/
  // getPropertyValue (those need kebab-case and would no-op on camelCase).
  for (const prop of MIRROR_PROPS) {
    ;(style as unknown as Record<string, string>)[prop] =
      (computed as unknown as Record<string, string>)[prop]
  }

  div.textContent = el.value.slice(0, position)
  const span = doc.createElement('span')
  // A non-empty span gives a measurable box even at end-of-text.
  span.textContent = el.value.slice(position) || '.'
  div.appendChild(span)

  const coords: CaretCoords = {
    top: span.offsetTop,
    left: span.offsetLeft,
    height: parseInt(computed.lineHeight, 10) || el.offsetHeight,
  }

  doc.body.removeChild(div)
  return coords
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && CI=true npx vitest run src/shared/lib/caretCoordinates.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/lib/caretCoordinates.ts frontend/src/shared/lib/caretCoordinates.test.ts
git commit -m "feat(emoji-autocomplete): mirror-div getCaretCoordinates util"
```

---

### Task 4: `EmojiAutocompleteTextarea` component

**Files:**
- Create: `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.tsx`
- Create: `frontend/src/shared/components/EmojiAutocompleteTextarea/index.ts`
- Test: `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.test.tsx`

**Interfaces:**
- Consumes: `Textarea` (ref-forwarding, Task 1), `matchTrigger`/`insertToken` (Task 2), `getCaretCoordinates` (Task 3), `EmojiPreview`/`EmojiUnit`, `useDismiss`, `apiClient`.
- Produces: `EmojiAutocompleteTextarea` — same props as `Textarea` (`value`, `onChange`, `id`, `rows`, `autoResize`, `placeholder`, …); drop-in replacement.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EmojiAutocompleteTextarea } from './EmojiAutocompleteTextarea'
import { apiClient } from '../../lib/api'

const PLACEHOLDERS = [
  { id: 5, name: 'Header', token: '{emo:5}', units: [{ type: 'emoji', emoji_id: '111', fallback: '🔔' }] },
  { id: 6, name: 'Footer', token: '{emo:6}', units: [{ type: 'text', value: 'bye' }] },
]

function Harness() {
  const [value, setValue] = useState('')
  return (
    <EmojiAutocompleteTextarea
      aria-label="composer"
      value={value}
      onChange={e => setValue(e.target.value)}
    />
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(apiClient, 'get').mockResolvedValue({ data: PLACEHOLDERS } as never)
})

describe('EmojiAutocompleteTextarea', () => {
  it('opens a suggestion list when @emo is typed', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emo' } })
    expect(await screen.findByText('Header')).toBeInTheDocument()
    expect(screen.getByText('Footer')).toBeInTheDocument()
  })

  it('filters the list by the query', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emohead' } })
    expect(await screen.findByText('Header')).toBeInTheDocument()
    expect(screen.queryByText('Footer')).not.toBeInTheDocument()
  })

  it('inserts the {emo:id} token on click and fires onChange', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: 'hi @emo' } })
    fireEvent.click(await screen.findByText('Header'))
    await waitFor(() => expect(ta.value).toBe('hi {emo:5}'))
  })

  it('closes on Escape without inserting', async () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: '@emo' } })
    expect(await screen.findByText('Header')).toBeInTheDocument()
    fireEvent.keyDown(ta, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByText('Header')).not.toBeInTheDocument())
    expect(ta.value).toBe('@emo')
  })

  it('passes text through normally when not triggered', () => {
    render(<Harness />)
    const ta = screen.getByLabelText('composer') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: 'plain text' } })
    expect(ta.value).toBe('plain text')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && CI=true npx vitest run src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.test.tsx`
Expected: FAIL (cannot resolve the component).

- [ ] **Step 3: Write the component**

Create `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.tsx`:

```tsx
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
```

> `onMouseDown` (not `onClick`) with `preventDefault` keeps focus in the textarea so the caret-restore effect works and `useDismiss`'s pointerdown doesn't fire first.

- [ ] **Step 4: Add the stylesheet + index**

Create `frontend/src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.css`:

```css
.emoji-ac__panel {
  position: absolute;
  z-index: 1000;
  min-width: 200px;
  max-height: 240px;
  overflow-y: auto;
  background: var(--color-card, #181816);
  border: 1px solid var(--color-border, #2a2a28);
  border-radius: 8px;
  padding: 4px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
.emoji-ac__option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.emoji-ac__option--active { background: var(--color-hover, #232321); }
.emoji-ac__name { flex: 1; }
.emoji-ac__token { opacity: 0.5; font-size: 0.85em; font-family: monospace; }
```

Create `frontend/src/shared/components/EmojiAutocompleteTextarea/index.ts`:

```ts
export { EmojiAutocompleteTextarea } from './EmojiAutocompleteTextarea'
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && CI=true npx vitest run src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.test.tsx`
Expected: PASS (all 5)

- [ ] **Step 6: Build + lint**

Run: `cd frontend && npm run build` (succeeds) and `npx eslint src/shared/components/EmojiAutocompleteTextarea/EmojiAutocompleteTextarea.tsx` (clean).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/shared/components/EmojiAutocompleteTextarea/
git commit -m "feat(emoji-autocomplete): EmojiAutocompleteTextarea component"
```

---

### Task 5: Wire the autocomplete into the six fields

**Files:**
- Modify: `frontend/src/pages/NotificationsPage.tsx`, `frontend/src/pages/ProductsPage.tsx`, `frontend/src/pages/BotUiSettingsPage.tsx`

**Interfaces:**
- Consumes: `EmojiAutocompleteTextarea` (drop-in for `Textarea`).

- [ ] **Step 1: NotificationsPage — message composer**

In `frontend/src/pages/NotificationsPage.tsx`, add the import near the `Textarea` import:

```tsx
import { EmojiAutocompleteTextarea } from '../shared/components/EmojiAutocompleteTextarea'
```

Replace the `notif-msg` field's `<Textarea …/>` with `<EmojiAutocompleteTextarea …/>` (identical props):

```tsx
<EmojiAutocompleteTextarea
  id="notif-msg"
  value={message}
  onChange={e => setMessage(e.target.value)}
  placeholder={t('notifications.messagePlaceholder', 'Nhập nội dung thông báo...')}
  rows={5}
  autoResize
/>
```

(Leave the `Textarea` import in place — the three chat-ID textareas still use it.)

- [ ] **Step 2: ProductsPage — description + upgrade text**

In `frontend/src/pages/ProductsPage.tsx`, add the import alongside the `Textarea` import, then swap the two fields to `EmojiAutocompleteTextarea` (props unchanged):

```tsx
import { EmojiAutocompleteTextarea } from '../shared/components/EmojiAutocompleteTextarea'
```

```tsx
<EmojiAutocompleteTextarea
  id={`${formId}-desc`}
  value={formData.description}
  onChange={e => setFormData(d => ({ ...d, description: e.target.value }))}
  placeholder={t('products.descPlaceholder', 'Mô tả sản phẩm (tuỳ chọn)')}
  rows={3}
/>
```

```tsx
<EmojiAutocompleteTextarea
  id={`${formId}-upgrade`}
  value={formData.upgrade_request_text}
  onChange={e => setFormData(d => ({ ...d, upgrade_request_text: e.target.value }))}
  placeholder={t('products.upgradePlaceholder', 'Nội dung gửi đến nhà cung cấp')}
  rows={3}
/>
```

- [ ] **Step 3: BotUiSettingsPage — three fields**

In `frontend/src/pages/BotUiSettingsPage.tsx`, add the import alongside the `Textarea` import, then swap the three fields (props unchanged):

```tsx
import { EmojiAutocompleteTextarea } from '../shared/components/EmojiAutocompleteTextarea'
```

```tsx
<EmojiAutocompleteTextarea
  id="bui-upload"
  value={fields.upload_notification_header}
  onChange={setField('upload_notification_header')}
  placeholder={t('botUi.uploadHeaderPlaceholder', '📢 Có hàng mới!')}
  rows={2}
  autoResize
/>
```

```tsx
<EmojiAutocompleteTextarea
  id="bui-product"
  value={fields.product_choose_text}
  onChange={setField('product_choose_text')}
  placeholder={t('botUi.productTextPlaceholder', 'Chọn loại dịch vụ bạn muốn')}
  rows={4}
  autoResize
/>
```

```tsx
<EmojiAutocompleteTextarea
  id="bui-variation"
  value={fields.variation_choose_text}
  onChange={setField('variation_choose_text')}
  placeholder={t('botUi.variationTextPlaceholder', 'Chọn gói phù hợp')}
  rows={4}
  autoResize
/>
```

> NOTE: `setField('...')` returns a native `onChange` handler that reads `e.target.value`; the component's synthetic insert event satisfies it. Confirm `setField` reads only `e.target.value` (it does in the current code) before relying on this.

- [ ] **Step 4: Build + lint + test**

Run: `cd frontend && npm run build` (succeeds), `npx eslint src/pages/NotificationsPage.tsx src/pages/ProductsPage.tsx src/pages/BotUiSettingsPage.tsx` (clean), `CI=true npx vitest run` (all pass).

- [ ] **Step 5: Manual verification**

Run the dashboard, configure at least one emoji placeholder, then in each field type `@emo`: confirm the popup appears at the caret with thumbnail previews, filtering works, selecting inserts `{emo:<id>}`, Esc closes, and saving persists the token.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/NotificationsPage.tsx frontend/src/pages/ProductsPage.tsx frontend/src/pages/BotUiSettingsPage.tsx
git commit -m "feat(emoji-autocomplete): wire @emo autocomplete into authoring fields"
```

---

## Self-Review

**Spec coverage:**
- Drop-in `EmojiAutocompleteTextarea` wrapping the shared Textarea → Tasks 1 + 4 ✓
- Trigger `@emo` + contiguous query, insert `{emo:<id>}` → Task 2 (`matchTrigger`/`insertToken`) + Task 4 (`choose`) ✓
- Caret-anchored popup via mirror-div → Task 3 + Task 4 (`syncTrigger` positioning) ✓
- Suggestion list with EmojiPreview thumbnails + name + token, keyboard nav, useDismiss → Task 4 ✓
- Lazy fetch + cache of `/api/emoji-placeholders` → Task 4 (`ensureLoaded`) ✓
- Controlled-field synthetic onChange + caret restore → Task 4 (`choose` + value-effect) ✓
- Wiring into all 6 fields → Task 5 ✓
- Zero behavior change when not triggered → Task 4 (passthrough test) ✓
- Testing: pure helpers, caret-util smoke, component (open/filter/insert/Esc/passthrough) → Tasks 2,3,4 ✓

**Placeholder scan:** No TBD/TODO; every code step is complete.

**Type consistency:** `matchTrigger(textBeforeCaret) -> {query,start}|null`, `insertToken(value,caret,matchStart,token) -> {value,caret}`, `getCaretCoordinates(el,position) -> {top,left,height}`, `Placeholder {id,name,token,units}` matching the API + `EmojiUnit` from EmojiPreview — used consistently across Tasks 2–5. The component forwards `value`/`onChange` and consumers read `e.target.value` only.

**Verification-required assumptions (flagged in tasks):** `Textarea/index.ts` re-export survives the forwardRef change (Task 1 — it does, named re-export); `setField(...)` reads only `e.target.value` (Task 5 Step 3); CSS variables (`--color-card` etc.) exist in the theme or degrade gracefully via the fallbacks given (Task 4 Step 4).
