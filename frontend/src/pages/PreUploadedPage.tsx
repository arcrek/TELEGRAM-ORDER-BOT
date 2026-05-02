import { useState, useEffect, useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Package, RefreshCw, Trash2, Copy, Check, Download, CheckCircle, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { StatCard } from '../shared/components/StatCard'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { Badge } from '../shared/components/Badge'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Select } from '../shared/components/Select'
import { Tooltip } from '../shared/components/Tooltip'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './PreUploadedPage.css'

function extractProductData(raw: string): string {
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed === 'object' && parsed !== null && 'value' in parsed) return String(parsed.value)
    return raw
  } catch { return raw }
}

interface PreUploadedProduct {
  id: string
  product_id: string
  product_name: string
  variation_id: string
  variation_name: string
  product_data: string
  is_used: boolean
  used_at: string | null
  used_by_order_id: string | null
  created_at: string
}

interface Statistics {
  total: number
  used: number
  available: number
  by_product: Record<string, { product_id: string; product_name: string; total: number; used: number; available: number }>
}

export function PreUploadedPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()

  const [searchParams, setSearchParams] = useSearchParams()
  const urlProductId = searchParams.get('product') ?? null
  const urlUsed = searchParams.get('used') ?? null
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))

  const setParam = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === '') next.delete(k); else next.set(k, v)
        }
        return next
      }, { replace: true })
    },
    [setSearchParams],
  )

  const [products, setProducts] = useState<PreUploadedProduct[]>([])
  const [statistics, setStatistics] = useState<Statistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [perPage, setPerPage] = useState(15)
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {
        page: String(urlPage),
        per_page: String(perPage),
      }
      if (urlProductId) params.product_id = urlProductId
      if (urlUsed !== null) params.is_used = urlUsed

      const [dataRes, statsRes] = await Promise.all([
        apiClient.get<{ items: PreUploadedProduct[]; total: number; total_pages: number }>('/api/pre-uploaded-products', { params }),
        apiClient.get<Statistics>('/api/pre-uploaded-products/statistics'),
      ])
      setProducts(dataRes.data.items)
      setTotal(dataRes.data.total)
      setStatistics(statsRes.data)
      setSelectedKeys(new Set())
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.loadError', 'Không thể tải kho hàng')))
    } finally {
      setLoading(false)
    }
  }, [urlPage, perPage, urlProductId, urlUsed, t])

  useEffect(() => { fetchData() }, [fetchData])

  const handleMarkUsed = async (id: string) => {
    try {
      await apiClient.put(`/api/pre-uploaded-products/${id}/mark-used`, {})
      fetchData()
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.markUsedError', 'Không thể cập nhật')))
    }
  }

  const handleMarkUnused = async (id: string) => {
    try {
      await apiClient.put(`/api/pre-uploaded-products/${id}/mark-unused`, {})
      fetchData()
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.markUnusedError', 'Không thể cập nhật')))
    }
  }

  const handleDelete = async (item: PreUploadedProduct) => {
    const ok = await confirm({
      title: t('preUploaded.deleteTitle', 'Xoá sản phẩm?'),
      description: t('preUploaded.deleteDesc', 'Hành động này không thể hoàn tác.'),
      confirmLabel: t('common.delete', 'Xoá'),
      variant: 'destructive',
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/pre-uploaded-products/${item.id}`)
      toast.success(t('preUploaded.deleted', 'Đã xoá'))
      fetchData()
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.deleteError', 'Không thể xoá')))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedKeys.size === 0) return
    const ok = await confirm({
      title: t('preUploaded.bulkDeleteTitle', `Xoá ${selectedKeys.size} mục?`),
      variant: 'destructive',
      confirmLabel: t('common.delete', 'Xoá'),
    })
    if (!ok) return
    try {
      await Promise.all(Array.from(selectedKeys).map(id => apiClient.delete(`/api/pre-uploaded-products/${id}`)))
      toast.success(t('preUploaded.bulkDeleted', 'Đã xoá các mục đã chọn'))
      setSelectedKeys(new Set())
      fetchData()
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.bulkDeleteError', 'Không thể xoá')))
    }
  }

  const handleCopy = async (item: PreUploadedProduct) => {
    await navigator.clipboard.writeText(extractProductData(item.product_data))
    setCopiedId(item.id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  const handleDownloadSelected = () => {
    const selected = products.filter(p => selectedKeys.has(p.id))
    const content = selected.map(p => extractProductData(p.product_data)).join('\n')
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `inventory_${new Date().toISOString().slice(0, 10)}.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  // ── Product filter options ─────────────────────────────────────────
  const productOptions = useMemo(() => {
    if (!statistics) return []
    return Object.values(statistics.by_product).map(p => ({ value: p.product_id, label: p.product_name }))
  }, [statistics])

  const columns = useMemo<ColumnDef<PreUploadedProduct>[]>(() => [
    {
      id: 'product',
      header: t('preUploaded.colProduct', 'Sản phẩm'),
      cell: row => (
        <div className="pre-uploaded-page__product-cell">
          <span>{row.product_name}</span>
          <span className="pre-uploaded-page__variation">{row.variation_name}</span>
        </div>
      ),
    },
    {
      id: 'product_data',
      header: t('preUploaded.colData', 'Dữ liệu'),
      mono: true,
      cell: row => (
        <div className="pre-uploaded-page__data-cell">
          <span className="pre-uploaded-page__data-preview">{extractProductData(row.product_data).slice(0, 32)}&hellip;</span>
          <Tooltip content={copiedId === row.id ? t('common.copied', 'Đã sao chép!') : t('common.copy', 'Sao chép')}>
            <IconButton
              icon={copiedId === row.id ? <Check size={13} /> : <Copy size={13} />}
              aria-label={t('common.copy', 'Sao chép')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleCopy(row) }}
            />
          </Tooltip>
        </div>
      ),
    },
    {
      id: 'status',
      header: t('preUploaded.colStatus', 'Trạng thái'),
      width: 110,
      cell: row => (
        <Badge variant={row.is_used ? 'neutral' : 'success'} size="sm">
          {row.is_used ? t('preUploaded.sold', 'Đã bán') : t('preUploaded.available', 'Có hàng')}
        </Badge>
      ),
    },
    {
      id: 'used_at',
      header: t('preUploaded.colUsedAt', 'Thời gian bán'),
      width: 130,
      cell: row => row.used_at ? (
        <Tooltip content={fmt.dateTime(row.used_at)}>
          <span className="pre-uploaded-page__rel-time">{fmt.relative(row.used_at)}</span>
        </Tooltip>
      ) : '—',
    },
    {
      id: 'order',
      header: t('preUploaded.colOrder', 'Đơn hàng'),
      mono: true,
      width: 110,
      cell: row => row.used_by_order_id ? `#${row.used_by_order_id.slice(0, 8)}` : '—',
    },
    {
      id: 'created_at',
      header: t('preUploaded.colCreated', 'Tạo lúc'),
      width: 120,
      cell: row => (
        <Tooltip content={fmt.dateTime(row.created_at)}>
          <span className="pre-uploaded-page__rel-time">{fmt.relative(row.created_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 110,
      align: 'right',
      cell: row => (
        <div className="pre-uploaded-page__actions">
          <Tooltip content={row.is_used ? t('preUploaded.markAvailable', 'Đánh dấu có hàng') : t('preUploaded.markSold', 'Đánh dấu đã bán')}>
            <IconButton
              icon={row.is_used ? <XCircle size={13} /> : <CheckCircle size={13} />}
              aria-label={row.is_used ? t('preUploaded.markAvailable', 'Đánh dấu có hàng') : t('preUploaded.markSold', 'Đánh dấu đã bán')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); row.is_used ? handleMarkUnused(row.id) : handleMarkUsed(row.id) }}
            />
          </Tooltip>
          <Tooltip content={t('common.delete', 'Xoá')}>
            <IconButton
              icon={<Trash2 size={13} />}
              aria-label={t('common.delete', 'Xoá')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleDelete(row) }}
            />
          </Tooltip>
        </div>
      ),
    },
  ], [t, fmt, copiedId])

  return (
    <div className="pre-uploaded-page">
      <PageHeader
        title={t('nav.preUploaded', 'Kho hàng')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Làm mới')}
            variant="ghost"
            size="sm"
            onClick={fetchData}
          />
        }
      />

      {/* KPI row */}
      {statistics && (
        <div className="pre-uploaded-page__kpi-row">
          <StatCard label={t('preUploaded.total', 'Tổng cộng')} value={String(statistics.total)} icon={<Package size={16} />} loading={loading} />
          <StatCard label={t('preUploaded.available', 'Có hàng')} value={String(statistics.available)} icon={<CheckCircle size={16} />} loading={loading} />
          <StatCard label={t('preUploaded.sold', 'Đã bán')} value={String(statistics.used)} icon={<XCircle size={16} />} loading={loading} />
        </div>
      )}

      {/* Filters */}
      <div className="pre-uploaded-page__filters">
        <Select
          options={productOptions}
          value={urlProductId}
          onChange={v => setParam({ product: v, page: null })}
          placeholder={t('preUploaded.allProducts', 'Tất cả sản phẩm')}
          clearable
          searchable
          size="sm"
          className="pre-uploaded-page__product-select"
        />
        <Select
          options={[
            { value: 'false', label: t('preUploaded.available', 'Có hàng') },
            { value: 'true', label: t('preUploaded.sold', 'Đã bán') },
          ]}
          value={urlUsed}
          onChange={v => setParam({ used: v, page: null })}
          placeholder={t('preUploaded.allStatus', 'Tất cả trạng thái')}
          clearable
          size="sm"
          className="pre-uploaded-page__status-select"
        />
      </div>

      {/* Bulk bar */}
      {selectedKeys.size > 0 && (
        <div className="pre-uploaded-page__bulk-bar">
          <span>{t('preUploaded.selected', `Đã chọn ${selectedKeys.size}`)}</span>
          <Button variant="secondary" tone="subtle" size="sm" iconLeft={<Download size={13} />} onClick={handleDownloadSelected}>
            {t('preUploaded.download', 'Tải xuống')}
          </Button>
          <Button variant="destructive" tone="subtle" size="sm" iconLeft={<Trash2 size={13} />} onClick={handleBulkDelete}>
            {t('preUploaded.bulkDelete', 'Xoá')}
          </Button>
        </div>
      )}

      <div className="pre-uploaded-page__table-card">
        <Table<PreUploadedProduct>
          columns={columns}
          data={products}
          keyFn={row => row.id}
          loading={loading}
          skeletonRows={perPage}
          selectable
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          stickyHeader
          emptyIcon={<Package size={40} />}
          emptyTitle={t('preUploaded.empty', 'Kho hàng trống')}
          emptyDescription={t('preUploaded.emptyDesc', 'Upload sản phẩm để bắt đầu')}
        />
        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
          className="pre-uploaded-page__pagination"
        />
      </div>
    </div>
  )
}
