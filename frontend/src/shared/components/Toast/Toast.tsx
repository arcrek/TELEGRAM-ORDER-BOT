/**
 * Toast system: ToastProvider + useToast hook.
 * Top-right stack with success/error/warning/info variants.
 * 5s default; pause on hover; action slot; aria-live regions split by severity.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react'
import { setToastErrorHandler } from '../../lib/api'
import './Toast.css'

export type ToastVariant = 'success' | 'error' | 'warning' | 'info'

export interface ToastOptions {
  title?: string
  message: string
  variant?: ToastVariant
  durationMs?: number
  action?: { label: string; onClick: () => void }
}

interface ToastEntry extends Required<Omit<ToastOptions, 'action' | 'title'>> {
  id: string
  title?: string
  action?: ToastOptions['action']
  leaving: boolean
}

interface ToastContextType {
  toast: {
    success: (msg: string, opts?: Omit<ToastOptions, 'message' | 'variant'>) => void
    error: (msg: string, opts?: Omit<ToastOptions, 'message' | 'variant'>) => void
    warning: (msg: string, opts?: Omit<ToastOptions, 'message' | 'variant'>) => void
    info: (msg: string, opts?: Omit<ToastOptions, 'message' | 'variant'>) => void
    show: (opts: ToastOptions) => void
  }
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

const VARIANT_ICONS: Record<ToastVariant, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const POLITE: ToastVariant[] = ['success', 'info']
const ASSERTIVE: ToastVariant[] = ['error', 'warning']

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([])
  const timersRef = useRef(new Map<string, number>())

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 180)
    const handle = timersRef.current.get(id)
    if (handle) {
      window.clearTimeout(handle)
      timersRef.current.delete(id)
    }
  }, [])

  const scheduleDismiss = useCallback(
    (id: string, durationMs: number) => {
      if (durationMs <= 0) return
      const handle = window.setTimeout(() => dismiss(id), durationMs)
      timersRef.current.set(id, handle)
    },
    [dismiss],
  )

  const show = useCallback(
    (opts: ToastOptions) => {
      const id = `toast-${++nextId}`
      const entry: ToastEntry = {
        id,
        title: opts.title,
        message: opts.message,
        variant: opts.variant ?? 'info',
        durationMs: opts.durationMs ?? 5000,
        action: opts.action,
        leaving: false,
      }
      setToasts((prev) => [...prev, entry])
      scheduleDismiss(id, entry.durationMs)
    },
    [scheduleDismiss],
  )

  const toast = useMemo(
    () => ({
      success: (message: string, opts: Omit<ToastOptions, 'message' | 'variant'> = {}) =>
        show({ ...opts, message, variant: 'success' }),
      error: (message: string, opts: Omit<ToastOptions, 'message' | 'variant'> = {}) =>
        show({ ...opts, message, variant: 'error' }),
      warning: (message: string, opts: Omit<ToastOptions, 'message' | 'variant'> = {}) =>
        show({ ...opts, message, variant: 'warning' }),
      info: (message: string, opts: Omit<ToastOptions, 'message' | 'variant'> = {}) =>
        show({ ...opts, message, variant: 'info' }),
      show,
    }),
    [show],
  )

  // Bridge: api client's 401 interceptor pushes a toast through this provider.
  useEffect(() => {
    setToastErrorHandler((message: string) => toast.error(message))
    return () => setToastErrorHandler(() => {})
  }, [toast])

  const polite = toasts.filter((t) => POLITE.includes(t.variant))
  const assertive = toasts.filter((t) => ASSERTIVE.includes(t.variant))

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      <div className="toast-stack" role="region" aria-label="Notifications">
        <div aria-live="polite" aria-atomic="false">
          {polite.map((t) => (
            <ToastItem
              key={t.id}
              entry={t}
              onDismiss={() => dismiss(t.id)}
              onPause={() => {
                const h = timersRef.current.get(t.id)
                if (h) window.clearTimeout(h)
              }}
              onResume={() => scheduleDismiss(t.id, 2500)}
            />
          ))}
        </div>
        <div aria-live="assertive" aria-atomic="false">
          {assertive.map((t) => (
            <ToastItem
              key={t.id}
              entry={t}
              onDismiss={() => dismiss(t.id)}
              onPause={() => {
                const h = timersRef.current.get(t.id)
                if (h) window.clearTimeout(h)
              }}
              onResume={() => scheduleDismiss(t.id, 2500)}
            />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({
  entry,
  onDismiss,
  onPause,
  onResume,
}: {
  entry: ToastEntry
  onDismiss: () => void
  onPause: () => void
  onResume: () => void
}) {
  const Icon = VARIANT_ICONS[entry.variant]
  return (
    <div
      className="toast"
      data-variant={entry.variant}
      data-leaving={entry.leaving ? 'true' : undefined}
      role={entry.variant === 'error' || entry.variant === 'warning' ? 'alert' : 'status'}
      onMouseEnter={onPause}
      onMouseLeave={onResume}
      onFocus={onPause}
      onBlur={onResume}
    >
      <Icon size={20} className="toast-icon" aria-hidden />
      <div className="toast-body">
        {entry.title && <div className="toast-title">{entry.title}</div>}
        <div className="toast-message">{entry.message}</div>
      </div>
      <div className="toast-actions">
        {entry.action && (
          <button type="button" className="toast-action-button" onClick={entry.action.onClick}>
            {entry.action.label}
          </button>
        )}
        <button type="button" className="toast-dismiss" onClick={onDismiss} aria-label="Dismiss">
          <X size={14} aria-hidden />
        </button>
      </div>
    </div>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
