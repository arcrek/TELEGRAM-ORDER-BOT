import { Outlet } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import { Sidebar, type NavBadgeCounts } from './Sidebar'
import { Topbar } from './Topbar'
import { MobileDrawer } from './MobileDrawer'
import { CommandPalette } from './CommandPalette'
import { useDisclosure } from '../../shared/hooks/useDisclosure'
import { useMediaQuery } from '../../shared/hooks/useMediaQuery'
import { apiClient } from '../../shared/lib/api'
import { useTranslation } from 'react-i18next'
import { useToast } from '../../shared/components/Toast'
import { buildToastParams, pickNewOrders, type PaidOrder } from './newOrderToast'
import './AppShell.css'

function readCollapsed(): boolean {
  try { return localStorage.getItem('sidebar-collapsed') === 'true' } catch { return false }
}

interface TodoCounts {
  upgrade_orders_count: number
  aging_inventory_count: number
  low_stock_inventory_count: number
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const isMobile = useMediaQuery('(max-width: 900px)')
  const drawer = useDisclosure()
  const cmdPalette = useDisclosure()
  const [badgeCounts, setBadgeCounts] = useState<NavBadgeCounts>({})

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', String(collapsed)) } catch { /* noop */ }
  }, [collapsed])

  useEffect(() => { drawer.close() }, [])

  const { toast } = useToast()
  const { t } = useTranslation()  // single 'translation' namespace; key path is 'orders.newOrderToast'
  const sinceRef = useRef<string | null>(null)
  const seenRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    const LOOKBACK_MS = 30_000

    const poll = async () => {
      try {
        const since = sinceRef.current
        const qs = since
          ? `?since=${encodeURIComponent(new Date(new Date(since).getTime() - LOOKBACK_MS).toISOString())}`
          : ''
        const res = await apiClient.get<{ server_now: string; orders: PaidOrder[] }>(
          `/api/orders/recent-paid${qs}`,
        )
        if (cancelled) return
        const { server_now, orders } = res.data
        if (since === null) {
          // baseline: seed nothing, do not toast history
          sinceRef.current = server_now
          return
        }
        for (const o of pickNewOrders(orders, seenRef.current)) {
          toast.success(t('orders.newOrderToast', buildToastParams(o)), { durationMs: 8000 })
        }
        // cap memory of the seen-set
        if (seenRef.current.size > 200) {
          seenRef.current = new Set(Array.from(seenRef.current).slice(-200))
        }
        sinceRef.current = server_now
      } catch { /* fail silently */ }
    }

    poll()
    const interval = setInterval(poll, 10_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [toast, t])

  // Fetch todo counts for sidebar badges
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await apiClient.get<TodoCounts>('/api/statistics/todo')
        if (cancelled) return
        const d = res.data
        setBadgeCounts({
          orders: d.upgrade_orders_count,
          preUploaded: (d.aging_inventory_count > 0 || d.low_stock_inventory_count > 0) ? 'warn' : undefined,
        })
      } catch { /* fail silently */ }
    }
    load()
    const interval = setInterval(load, 60_000)  // refresh every minute
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  // ⌘K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        cmdPalette.toggle()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [cmdPalette])

  return (
    <div
      className="app-shell"
      data-collapsed={isMobile ? 'false' : String(collapsed)}
      data-mobile={String(isMobile)}
    >
      <a href="#main-content" className="skip-link">Bỏ qua điều hướng</a>

      {!isMobile && (
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed(v => !v)}
          badgeCounts={badgeCounts}
          className="app-shell__sidebar"
        />
      )}

      <Topbar
        onMenuClick={drawer.open}
        isMobile={isMobile}
        onSearchClick={cmdPalette.open}
        className="app-shell__topbar"
      />

      <main id="main-content" className="app-shell__main" tabIndex={-1}>
        <Outlet />
      </main>

      {isMobile && (
        <MobileDrawer
          open={drawer.isOpen}
          onClose={drawer.close}
        />
      )}

      <CommandPalette
        open={cmdPalette.isOpen}
        onClose={cmdPalette.close}
      />
    </div>
  )
}
