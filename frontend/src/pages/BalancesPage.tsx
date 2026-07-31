import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Wallet, Download, RefreshCw, Eye, SlidersHorizontal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef, type SortState } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Select } from '../shared/components/Select'
import { Tooltip } from '../shared/components/Tooltip'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import { BalanceAdjustModal } from './balances/BalanceAdjustModal'
import { BalanceDetailDrawer } from './balances/BalanceDetailDrawer'
import type { BalanceUserRow, BalancesListResponse } from './balances/types'

const SORT_OPTIONS = [
  { value: 'balance|desc', label: 'Số dư: Cao → Thấp' },
  { value: 'balance|asc', label: 'Số dư: Thấp → Cao' },
  { value: 'total_topup|desc', label: 'Tổng nạp: Cao → Thấp' },
  { value: 'total_topup|asc', label: 'Tổng nạp: Thấp → Cao' },
  { value: 'updated_at|desc', label: 'Mới cập nhật nhất' },
  { value: 'updated_at|asc', label: 'Cũ nhất' },
]

export function BalancesPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const fmt = useFormat()

  // ── URL-synced filters ─────────────────────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSearch = searchParams.get('q') ?? ''
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))
  const urlSortKey = searchParams.get('sort') ?? 'balance|desc'

  const setParam = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === '') next.delete(k)
          else next.set(k, v)
        }
        return next
      }, { replace: true })
    },
    [setSearchParams],
  )

  const [sortBy, sortOrder] = urlSortKey.split('|') as [string, string]
  const sortState: SortState = {
    id: sortBy,
    direction: (sortOrder ?? 'desc') as 'asc' | 'desc',
  }

  // Debounced search input
  const [searchInput, setSearchInput] = useState(urlSearch)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => { setSearchInput(urlSearch) }, [urlSearch])
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setParam({ q: val || null, page: null })
    }, 300)
  }

  // ── Data state ─────────────────────────────────────────────────────
  const [users, setUsers] = useState<BalanceUserRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [perPage, setPerPage] = useState(15)

  // ── Modals ─────────────────────────────────────────────────────────
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailUser, setDetailUser] = useState<BalanceUserRow | null>(null)

  const [adjustOpen, setAdjustOpen] = useState(false)
  const [adjustUser, setAdjustUser] = useState<BalanceUserRow | null>(null)

  // ── Fetch ──────────────────────────────────────────────────────────
  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {
        page: String(urlPage),
        per_page: String(perPage),
        sort_by: sortBy,
        sort_order: sortOrder ?? 'desc',
      }
      if (urlSearch) params.search = urlSearch

      const res = await apiClient.get<BalancesListResponse>('/api/balances', { params })
      setUsers(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      setError(formatApiError(err, t('balances.loadError', 'Không thể tải danh sách số dư')))
    } finally {
      setLoading(false)
    }
  }, [urlPage, perPage, sortBy, sortOrder, urlSearch, t])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const handleExport = async () => {
    try {
      const res = await apiClient.get('/api/balances/export', { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `active_users_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(formatApiError(err, t('balances.exportError', 'Không thể xuất người dùng')))
    }
  }

  // ── Adjust success callback ────────────────────────────────────────
  const handleAdjustSuccess = useCallback((botUserId: string, newBalance: number) => {
    setUsers(prev =>
      prev.map(u => u.bot_user_id === botUserId ? { ...u, balance: newBalance } : u),
    )
  }, [])

  // ── Column definitions ─────────────────────────────────────────────
  const columns = useMemo<ColumnDef<BalanceUserRow>[]>(() => [
    {
      id: 'username',
      header: t('balances.colUsername', 'Tài khoản'),
      cell: row => (
        <span style={{ color: 'var(--brand-500)', fontWeight: 500 }}>
          {row.username ? `@${row.username}` : '—'}
        </span>
      ),
    },
    {
      id: 'name',
      header: t('balances.colName', 'Tên'),
      cell: row => (
        <span>
          {[row.first_name, row.last_name].filter(Boolean).join(' ') || '—'}
        </span>
      ),
    },
    {
      id: 'telegram_user_id',
      header: t('balances.colTelegramId', 'Telegram ID'),
      mono: true,
      width: 130,
      cell: row => String(row.telegram_user_id),
    },
    {
      id: 'balance',
      header: t('balances.colBalance', 'Số dư'),
      align: 'right',
      sortable: true,
      width: 150,
      cell: row => (
        <strong style={{ color: row.balance > 0 ? 'var(--brand-500)' : 'var(--text-muted)' }}>
          {row.balance.toLocaleString('vi-VN')} VND
        </strong>
      ),
    },
    {
      id: 'total_topup',
      header: t('balances.colTotalTopup', 'Tổng nạp'),
      align: 'right',
      sortable: true,
      width: 150,
      cell: row => `${row.total_topup.toLocaleString('vi-VN')} VND`,
    },
    {
      id: 'last_topup_at',
      header: t('balances.colLastTopup', 'Nạp cuối'),
      width: 150,
      cell: row => row.last_topup_at ? fmt.dateTime(row.last_topup_at) : '—',
    },
    {
      id: 'actions',
      header: '',
      width: 80,
      align: 'right',
      cell: row => (
        <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
          <Tooltip content={t('common.view', 'Xem')}>
            <IconButton
              icon={<Eye size={14} />}
              aria-label={t('common.view', 'Xem')}
              size="sm"
              variant="ghost"
              onClick={e => {
                e.stopPropagation()
                setDetailUser(row)
                setDetailOpen(true)
              }}
            />
          </Tooltip>
          <Tooltip content={t('balances.adjust', 'Điều chỉnh')}>
            <IconButton
              icon={<SlidersHorizontal size={14} />}
              aria-label={t('balances.adjust', 'Điều chỉnh')}
              size="sm"
              variant="ghost"
              onClick={e => {
                e.stopPropagation()
                setAdjustUser(row)
                setAdjustOpen(true)
              }}
            />
          </Tooltip>
        </div>
      ),
    },
  ], [t, fmt])

  return (
    <div className="balances-page">
      <PageHeader
        title={t('nav.balances', 'Số dư người dùng')}
        description={t('balances.description', 'Quản lý số dư và lịch sử nạp tiền của khách hàng')}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              variant="secondary"
              tone="subtle"
              size="sm"
              iconLeft={<Download size={14} />}
              onClick={handleExport}
            >
              {t('common.export', 'Xuất CSV')}
            </Button>
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={fetchUsers}
            />
          </div>
        }
      />

      {/* ── Filters ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('balances.searchPlaceholder', 'Tìm theo username, tên, hoặc Telegram ID...')}
          value={searchInput}
          clearable
          size="sm"
          onChange={e => handleSearchChange(e.target.value)}
          onClear={() => handleSearchChange('')}
          className="balances-page__search"
        />
        <Select
          options={SORT_OPTIONS}
          value={urlSortKey}
          onChange={v => v && setParam({ sort: v, page: null })}
          size="sm"
          className="balances-page__sort"
        />
      </div>

      {/* ── Error banner ─────────────────────────────────────────── */}
      {error && (
        <div role="alert" style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: 'var(--danger-500)', marginBottom: 12, fontSize: 14,
        }}>
          <span>{error}</span>
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.retry', 'Thử lại')}
            size="sm"
            variant="ghost"
            onClick={fetchUsers}
          />
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────── */}
      <div style={{
        background: 'var(--bg-surface)',
        borderRadius: 8,
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}>
        <Table<BalanceUserRow>
          columns={columns}
          data={users}
          keyFn={row => row.bot_user_id}
          loading={loading}
          skeletonRows={perPage}
          sortState={sortState}
          onSortChange={sort => setParam({ sort: `${sort.id}|${sort.direction ?? 'desc'}`, page: null })}
          stickyHeader
          emptyIcon={<Wallet size={40} />}
          emptyTitle={t('balances.empty', 'Chưa có dữ liệu số dư')}
          emptyDescription={t('balances.emptyDesc', 'Số dư người dùng sẽ xuất hiện ở đây khi họ nạp tiền hoặc được điều chỉnh')}
          onRowClick={row => { setDetailUser(row); setDetailOpen(true) }}
        />

        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
          className="balances-page__pagination"
        />
      </div>

      {/* ── Detail modal ─────────────────────────────────────────── */}
      <BalanceDetailDrawer
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        user={detailUser}
      />

      {/* ── Adjust modal ─────────────────────────────────────────── */}
      <BalanceAdjustModal
        open={adjustOpen}
        onClose={() => setAdjustOpen(false)}
        user={adjustUser}
        onSuccess={handleAdjustSuccess}
      />
    </div>
  )
}
