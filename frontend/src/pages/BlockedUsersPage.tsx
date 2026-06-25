import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Ban, RefreshCw, Trash2, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { IconButton } from '../shared/components/IconButton'
import { Button } from '../shared/components/Button'
import { Input } from '../shared/components/Input'
import { Tooltip } from '../shared/components/Tooltip'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'

interface BlockedUserRow {
  id: number
  telegram_user_id: number | null
  username: string | null
  created_at: string
}

interface BlockedListResponse {
  items: BlockedUserRow[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export function BlockedUsersPage() {
  const { t } = useTranslation()
  const fmt = useFormat()
  const confirm = useConfirm()
  const { toast } = useToast()

  const [searchParams, setSearchParams] = useSearchParams()
  const urlSearch = searchParams.get('q') ?? ''
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))

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

  const [searchInput, setSearchInput] = useState(urlSearch)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => { setSearchInput(urlSearch) }, [urlSearch])
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setParam({ q: val || null, page: null }), 300)
  }

  const [rows, setRows] = useState<BlockedUserRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [perPage, setPerPage] = useState(15)
  const [addValue, setAddValue] = useState('')
  const [adding, setAdding] = useState(false)

  const fetchRows = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = { page: String(urlPage), per_page: String(perPage) }
      if (urlSearch) params.search = urlSearch
      const res = await apiClient.get<BlockedListResponse>('/api/blocked-users', { params })
      setRows(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      setError(formatApiError(err, t('blockedUsers.loadError', 'Không thể tải danh sách')))
    } finally {
      setLoading(false)
    }
  }, [urlPage, perPage, urlSearch, t])

  useEffect(() => { fetchRows() }, [fetchRows])

  const handleAdd = useCallback(async () => {
    const identifier = addValue.trim()
    if (!identifier) return
    setAdding(true)
    try {
      await apiClient.post('/api/blocked-users', { identifier })
      setAddValue('')
      toast.success(t('blockedUsers.added', 'Đã khóa người dùng'))
      setParam({ page: null })
      fetchRows()
    } catch (err) {
      toast.error(formatApiError(err, t('blockedUsers.addError', 'Không thể khóa người dùng')))
    } finally {
      setAdding(false)
    }
  }, [addValue, t, toast, setParam, fetchRows])

  const handleRemove = useCallback(async (row: BlockedUserRow) => {
    const label = row.username ? `@${row.username}` : String(row.telegram_user_id)
    const ok = await confirm({
      title: t('blockedUsers.confirmTitle', 'Mở khóa người dùng?'),
      description: t('blockedUsers.confirmMessage', { defaultValue: 'Bỏ khóa {{label}}?', label }),
      variant: 'destructive',
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/blocked-users/${row.id}`)
      toast.success(t('blockedUsers.removed', 'Đã mở khóa'))
      fetchRows()
    } catch (err) {
      toast.error(formatApiError(err, t('blockedUsers.removeError', 'Không thể mở khóa')))
    }
  }, [confirm, t, toast, fetchRows])

  const columns = useMemo<ColumnDef<BlockedUserRow>[]>(() => [
    {
      id: 'identifier',
      header: t('blockedUsers.colIdentifier', 'Người dùng'),
      cell: row => row.username
        ? <span style={{ color: 'var(--brand-500)', fontWeight: 500 }}>@{row.username}</span>
        : <span style={{ fontFamily: 'monospace' }}>{row.telegram_user_id}</span>,
    },
    {
      id: 'type',
      header: t('blockedUsers.colType', 'Loại'),
      width: 140,
      cell: row => row.username
        ? t('blockedUsers.typeUsername', 'Username')
        : t('blockedUsers.typeId', 'Telegram ID'),
    },
    {
      id: 'created_at',
      header: t('blockedUsers.colBlockedAt', 'Thời gian khóa'),
      width: 180,
      cell: row => row.created_at ? fmt.dateTime(row.created_at) : '—',
    },
    {
      id: 'actions',
      header: '',
      width: 64,
      align: 'right',
      cell: row => (
        <Tooltip content={t('blockedUsers.unblock', 'Mở khóa')}>
          <IconButton
            icon={<Trash2 size={14} />}
            aria-label={t('blockedUsers.unblock', 'Mở khóa')}
            size="sm"
            variant="ghost"
            onClick={e => { e.stopPropagation(); handleRemove(row) }}
          />
        </Tooltip>
      ),
    },
  ], [t, fmt, handleRemove])

  return (
    <div className="blocked-users-page">
      <PageHeader
        title={t('nav.blockedUsers', 'Người dùng bị khóa')}
        description={t('blockedUsers.description', 'Người dùng bị khóa không thể tạo đơn hàng hoặc nạp tiền')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Làm mới')}
            variant="ghost"
            size="sm"
            onClick={fetchRows}
          />
        }
      />

      {/* Add block */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Input
          placeholder={t('blockedUsers.addPlaceholder', 'Nhập Telegram ID hoặc @username...')}
          value={addValue}
          size="sm"
          onChange={e => setAddValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAdd() }}
          style={{ minWidth: 280 }}
        />
        <Button
          size="sm"
          iconLeft={<Plus size={14} />}
          onClick={handleAdd}
          disabled={adding || !addValue.trim()}
        >
          {t('blockedUsers.addButton', 'Khóa')}
        </Button>
      </div>

      {/* Search */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('blockedUsers.searchPlaceholder', 'Tìm theo username hoặc Telegram ID...')}
          value={searchInput}
          clearable
          size="sm"
          onChange={e => handleSearchChange(e.target.value)}
          onClear={() => handleSearchChange('')}
        />
      </div>

      {error && (
        <div role="alert" style={{ color: 'var(--danger-500)', marginBottom: 12, fontSize: 14 }}>
          {error}
        </div>
      )}

      <div style={{ background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
        <Table<BlockedUserRow>
          columns={columns}
          data={rows}
          keyFn={row => String(row.id)}
          loading={loading}
          skeletonRows={perPage}
          stickyHeader
          emptyIcon={<Ban size={40} />}
          emptyTitle={t('blockedUsers.empty', 'Chưa có người dùng bị khóa')}
          emptyDescription={t('blockedUsers.emptyDesc', 'Thêm Telegram ID hoặc @username phía trên để khóa')}
        />
        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
        />
      </div>
    </div>
  )
}
