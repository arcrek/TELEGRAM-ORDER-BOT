import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, RotateCcw } from 'lucide-react'
import axios from 'axios'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Button } from '../shared/components/Button'
import { Input } from '../shared/components/Input'
import { Badge, type OrderStatus } from '../shared/components/Badge/Badge'
import { Checkbox } from '../shared/components/Checkbox'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { useFormat } from '../shared/lib/format'
import {
  fetchUserOrders,
  previewRefunds,
  confirmRefunds,
  type RefundOrdersResponse,
  type RefundOrderRow,
  type PreviewRow,
  type RefundMode,
} from './refunds/refundsApi'

type Phase = 'search' | 'select' | 'calculate'

interface DurationState {
  days: number
  months: number
  years: number
}

const fmtVnd = (n: number) => `${n.toLocaleString('vi-VN')} VND`

export function RefundsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()

  const fmtBuyDate = (s: string | null) => (s ? fmt.dateTime(s) : '—')

  const [phase, setPhase] = useState<Phase>('search')
  const [search, setSearch] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [loading, setLoading] = useState(false)

  const [data, setData] = useState<RefundOrdersResponse | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [durations, setDurations] = useState<Record<string, DurationState>>({})
  const [preview, setPreview] = useState<Record<string, PreviewRow>>({})
  const [outcome, setOutcome] = useState<Record<string, boolean>>({})

  function reset() {
    setPhase('search')
    setSearch('')
    setFrom('')
    setTo('')
    setData(null)
    setSelected(new Set())
    setDurations({})
    setPreview({})
    setOutcome({})
  }

  async function doSearch() {
    if (!search.trim()) return
    setLoading(true)
    try {
      const res = await fetchUserOrders(search.trim(), from || undefined, to || undefined)
      setData(res)
      setSelected(new Set())
      setPhase('select')
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 404) {
        toast.error(t('refunds.userNotFound'))
      } else {
        toast.error(e instanceof Error ? e.message : String(e))
      }
    } finally {
      setLoading(false)
    }
  }

  function toggle(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function confirmSelection() {
    const init: Record<string, DurationState> = {}
    selected.forEach(id => { init[id] = { days: 0, months: 0, years: 0 } })
    setDurations(init)
    setPreview({})
    setOutcome({})
    setPhase('calculate')
  }

  function setDuration(id: string, patch: Partial<DurationState>) {
    setDurations(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }))
  }

  async function recompute(id: string) {
    const d = durations[id] ?? { days: 0, months: 0, years: 0 }
    try {
      const res = await previewRefunds([{ order_id: id, ...d }])
      setPreview(prev => {
        const next = { ...prev }
        res.rows.forEach(r => { next[r.order_id] = r })
        return next
      })
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    }
  }

  async function doConfirm(ids: string[], mode: RefundMode) {
    if (ids.length === 0) {
      toast.error(t('refunds.noEligibleSelected'))
      return
    }
    const confirmed = await confirm({
      title: t(mode === 'credit' ? 'refunds.confirmCreditMsg' : 'refunds.confirmStatusMsg'),
      variant: 'destructive',
    })
    if (!confirmed) return

    const items = ids.map(id => ({ order_id: id, ...(durations[id] ?? { days: 0, months: 0, years: 0 }), mode }))
    try {
      const res = await confirmRefunds(items)
      setOutcome(prev => {
        const next = { ...prev }
        res.results.forEach(r => { next[r.order_id] = r.success })
        return next
      })
      const ok = res.results.filter(r => r.success).length
      toast.success(t('refunds.successSummary', { ok, total: res.results.length }))
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    }
  }

  const selectedOrders: RefundOrderRow[] =
    data?.orders.filter(o => selected.has(o.id)) ?? []
  const eligibleSelectedIds = selectedOrders.filter(o => o.eligible).map(o => o.id)
  const totalRefund = eligibleSelectedIds.reduce(
    (sum, id) => sum + (preview[id]?.refund_amount ?? 0), 0)

  // ── Phase 2: select columns ────────────────────────────────────────
  const selectColumns: ColumnDef<RefundOrderRow>[] = [
    {
      id: 'sel',
      header: '',
      width: 40,
      cell: row => (
        <Checkbox
          disabled={!row.eligible}
          checked={selected.has(row.id)}
          onChange={() => toggle(row.id)}
        />
      ),
    },
    {
      id: 'id',
      header: t('refunds.order'),
      cell: row => (
        <span style={{ opacity: row.eligible ? 1 : 0.45, fontFamily: 'var(--font-mono, monospace)', fontSize: 13 }}>
          {row.id}
        </span>
      ),
    },
    {
      id: 'items',
      header: t('refunds.items'),
      cell: row => (
        <span style={{ opacity: row.eligible ? 1 : 0.45 }}>
          {row.items.map(i => `${i.product ?? ''} ${i.variation ?? ''}×${i.quantity}`.trim()).join(', ')}
        </span>
      ),
    },
    {
      id: 'total',
      header: t('refunds.total'),
      align: 'right',
      width: 140,
      cell: row => (
        <span style={{ opacity: row.eligible ? 1 : 0.45 }}>
          {fmtVnd(row.total_amount)}
        </span>
      ),
    },
    {
      id: 'buyDate',
      header: t('refunds.buyDate'),
      width: 170,
      cell: row => (
        <span style={{ opacity: row.eligible ? 1 : 0.45, color: 'var(--text-muted)', fontSize: 13 }}>
          {fmtBuyDate(row.created_at)}
        </span>
      ),
    },
    {
      id: 'status',
      header: t('refunds.status'),
      width: 200,
      cell: row => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Badge status={row.status as OrderStatus} size="sm">{row.status}</Badge>
          {!row.eligible && row.ineligible_reason && (
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{row.ineligible_reason}</span>
          )}
        </span>
      ),
    },
  ]

  // ── Phase 3: calculate columns ─────────────────────────────────────
  type CalcRow = RefundOrderRow & { _dur: DurationState }

  const calcColumns: ColumnDef<CalcRow>[] = [
    {
      id: 'id',
      header: t('refunds.order'),
      cell: row => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 13 }}>{row.id}</span>
      ),
    },
    {
      id: 'items',
      header: t('refunds.items'),
      cell: row => row.items.map(i => `${i.product ?? ''} ${i.variation ?? ''}×${i.quantity}`.trim()).join(', '),
    },
    {
      id: 'total',
      header: t('refunds.total'),
      align: 'right',
      width: 140,
      cell: row => fmtVnd(row.total_amount),
    },
    {
      id: 'buyDate',
      header: t('refunds.buyDate'),
      width: 170,
      cell: row => (
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{fmtBuyDate(row.created_at)}</span>
      ),
    },
    {
      id: 'days',
      header: t('refunds.days'),
      width: 80,
      align: 'center',
      cell: row => (
        <input
          type="number"
          min={0}
          style={{ width: 64, padding: '2px 6px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 4, color: 'var(--text-primary)', textAlign: 'center' }}
          value={row._dur.days}
          onChange={e => setDuration(row.id, { days: Number(e.target.value) || 0 })}
          onBlur={() => recompute(row.id)}
        />
      ),
    },
    {
      id: 'months',
      header: t('refunds.months'),
      width: 80,
      align: 'center',
      cell: row => (
        <input
          type="number"
          min={0}
          style={{ width: 64, padding: '2px 6px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 4, color: 'var(--text-primary)', textAlign: 'center' }}
          value={row._dur.months}
          onChange={e => setDuration(row.id, { months: Number(e.target.value) || 0 })}
          onBlur={() => recompute(row.id)}
        />
      ),
    },
    {
      id: 'years',
      header: t('refunds.years'),
      width: 80,
      align: 'center',
      cell: row => (
        <input
          type="number"
          min={0}
          style={{ width: 64, padding: '2px 6px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 4, color: 'var(--text-primary)', textAlign: 'center' }}
          value={row._dur.years}
          onChange={e => setDuration(row.id, { years: Number(e.target.value) || 0 })}
          onBlur={() => recompute(row.id)}
        />
      ),
    },
    {
      id: 'refund',
      header: t('refunds.refundAmount'),
      align: 'right',
      width: 140,
      cell: row => (
        <strong style={{ color: 'var(--brand-500)' }}>
          {fmtVnd(preview[row.id]?.refund_amount ?? 0)}
        </strong>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 220,
      cell: row => {
        if (outcome[row.id] === true) {
          return <Badge status="refunded" size="sm">{t('refunds.done')}</Badge>
        }
        if (outcome[row.id] === false) {
          return <span style={{ color: 'var(--danger-500)', fontSize: 13 }}>{t('refunds.failed')}</span>
        }
        return (
          <span style={{ display: 'inline-flex', gap: 4 }}>
            <Button
              variant="primary"
              tone="solid"
              size="sm"
              onClick={() => doConfirm([row.id], 'credit')}
            >
              {t('refunds.refundAndCredit')}
            </Button>
            <Button
              variant="secondary"
              tone="solid"
              size="sm"
              onClick={() => doConfirm([row.id], 'status')}
            >
              {t('refunds.markRefunded')}
            </Button>
          </span>
        )
      },
    },
  ]

  const calcData: CalcRow[] = selectedOrders.map(o => ({
    ...o,
    _dur: durations[o.id] ?? { days: 0, months: 0, years: 0 },
  }))

  const eligibleCount = data ? countEligibleSelected(selected, data) : 0

  return (
    <div className="refunds-page">
      <PageHeader
        title={t('refunds.title')}
        description={t('refunds.selectOrders')}
      />

      {/* ── Phase 1: Search ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('refunds.searchPlaceholder')}
          value={search}
          size="sm"
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
          clearable
          onClear={() => setSearch('')}
          style={{ minWidth: 220 }}
        />
        <Input
          type="date"
          size="sm"
          value={from}
          aria-label={t('refunds.from')}
          onChange={e => setFrom(e.target.value)}
          style={{ width: 160 }}
        />
        <Input
          type="date"
          size="sm"
          value={to}
          aria-label={t('refunds.to')}
          onChange={e => setTo(e.target.value)}
          style={{ width: 160 }}
        />
        <Button
          variant="primary"
          tone="solid"
          size="sm"
          loading={loading}
          iconLeft={<Search size={14} />}
          onClick={doSearch}
          disabled={!search.trim()}
        >
          {t('refunds.search')}
        </Button>
        {data && (
          <Button
            variant="secondary"
            tone="ghost"
            size="sm"
            iconLeft={<RotateCcw size={14} />}
            onClick={reset}
          >
            {t('refunds.reset')}
          </Button>
        )}
      </div>

      {/* ── User header (phases 2 + 3) ──────────────────────────────── */}
      {data && (
        <div style={{
          padding: '10px 14px',
          marginBottom: 12,
          background: 'var(--bg-surface)',
          borderRadius: 6,
          border: '1px solid var(--border-subtle)',
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          flexWrap: 'wrap',
          fontSize: 14,
        }}>
          <strong>
            {data.user.name || data.user.username || String(data.user.telegram_user_id)}
          </strong>
          {data.user.username && (
            <span style={{ color: 'var(--text-muted)' }}>@{data.user.username}</span>
          )}
          <span style={{ color: 'var(--text-muted)' }}>
            {t('refunds.balance')}: <strong style={{ color: 'var(--brand-500)' }}>{fmtVnd(data.user.balance)}</strong>
          </span>
        </div>
      )}

      {/* ── Phase 2: Select ─────────────────────────────────────────── */}
      {phase === 'select' && data && (
        <>
          <div style={{
            background: 'var(--bg-surface)',
            borderRadius: 8,
            border: '1px solid var(--border-subtle)',
            overflow: 'hidden',
            marginBottom: 12,
          }}>
            <Table<RefundOrderRow>
              columns={selectColumns}
              data={data.orders}
              keyFn={row => row.id}
              emptyTitle={t('refunds.noOrders')}
              stickyHeader
            />
          </div>
          <Button
            variant="primary"
            tone="solid"
            size="sm"
            disabled={eligibleCount === 0}
            onClick={confirmSelection}
          >
            {t('refunds.confirmSelection')}
          </Button>
        </>
      )}

      {/* ── Phase 3: Calculate + Act ─────────────────────────────────── */}
      {phase === 'calculate' && data && (
        <>
          <div style={{
            background: 'var(--bg-surface)',
            borderRadius: 8,
            border: '1px solid var(--border-subtle)',
            overflow: 'hidden',
            marginBottom: 12,
          }}>
            <Table<CalcRow>
              columns={calcColumns}
              data={calcData}
              keyFn={row => row.id}
              stickyHeader
            />
          </div>

          {/* Bulk action bar */}
          <div style={{
            display: 'flex',
            gap: 8,
            alignItems: 'center',
            flexWrap: 'wrap',
            padding: '12px 0',
          }}>
            <strong style={{ marginRight: 8 }}>
              {t('refunds.totalRefund')}: {fmtVnd(totalRefund)}
            </strong>
            <Button
              variant="primary"
              tone="solid"
              size="sm"
              disabled={eligibleSelectedIds.length === 0}
              onClick={() => doConfirm(eligibleSelectedIds, 'credit')}
            >
              {t('refunds.refundAndCreditAll')}
            </Button>
            <Button
              variant="secondary"
              tone="solid"
              size="sm"
              disabled={eligibleSelectedIds.length === 0}
              onClick={() => doConfirm(eligibleSelectedIds, 'status')}
            >
              {t('refunds.markRefundedAll')}
            </Button>
            <Button
              variant="secondary"
              tone="ghost"
              size="sm"
              iconLeft={<RotateCcw size={14} />}
              onClick={reset}
            >
              {t('refunds.reset')}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function countEligibleSelected(selected: Set<string>, data: RefundOrdersResponse): number {
  return data.orders.filter(o => selected.has(o.id) && o.eligible).length
}
