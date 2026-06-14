import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Package, RefreshCw, Trash2, Copy, Check, Download, CheckCircle, XCircle, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { StatCard } from '../shared/components/StatCard'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { Badge } from '../shared/components/Badge'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Select } from '../shared/components/Select'
import { Input } from '../shared/components/Input'
import { Modal } from '../shared/components/Modal'
import { Tooltip } from '../shared/components/Tooltip'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { DateRangePicker, type DateRange } from '../shared/components/DateRangePicker/DateRangePicker'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './InventoryPage.css'

function extractProductData(raw: string): string {
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed === 'object' && parsed !== null && 'value' in parsed) return String(parsed.value)
    return raw
  } catch { return raw }
}

function downloadTxt(lines: string[], filename: string): void {
  const content = lines.join('\n')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
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

interface VariationOption {
  id: string
  name: string
}

interface ExportResponse {
  requested: number
  exported: number
  short: boolean
  data: string[]
}

// ── DeleteByDateModal ─────────────────────────────────────────────────────────

interface DeleteByDateModalProps {
  open: boolean
  onClose: () => void
  onDeleted: () => void
  productOptions: { value: string; label: string }[]
}

function DeleteByDateModal({ open, onClose, onDeleted, productOptions }: DeleteByDateModalProps) {
  const { t } = useTranslation()
  const { toast } = useToast()

  const [productId, setProductId] = useState<string | null>(null)
  const [variationId, setVariationId] = useState<string | null>(null)
  const [variations, setVariations] = useState<VariationOption[]>([])
  const [dateRange, setDateRange] = useState<DateRange>({ from: null, to: null })
  const [previewCount, setPreviewCount] = useState<number | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!open) {
      setProductId(null)
      setVariationId(null)
      setVariations([])
      setDateRange({ from: null, to: null })
      setPreviewCount(null)
    }
  }, [open])

  // Fetch variations when product changes
  useEffect(() => {
    if (!productId) { setVariations([]); setVariationId(null); return }
    apiClient
      .get<{ items: { product_id: string; product_name: string; variations: VariationOption[] }[] }>(
        '/api/variations',
        { params: { product_id: productId } },
      )
      .then(res => {
        const flat: VariationOption[] = []
        for (const group of res.data.items) flat.push(...group.variations)
        setVariations(flat)
        setVariationId(null)
      })
      .catch(() => setVariations([]))
  }, [productId])

  // Live dry-run preview, debounced ~300ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (!dateRange.from && !dateRange.to) {
      setPreviewCount(null)
      return
    }

    debounceRef.current = setTimeout(async () => {
      setPreviewLoading(true)
      try {
        const body: Record<string, unknown> = { dry_run: true }
        if (productId) body.product_id = productId
        if (variationId) body.variation_id = variationId
        if (dateRange.from) body.uploaded_from = dateRange.from.toISOString()
        if (dateRange.to) body.uploaded_to = dateRange.to.toISOString()
        const res = await apiClient.post<{ matching: number }>('/api/pre-uploaded-products/delete-by-date', body)
        setPreviewCount(res.data.matching)
      } catch {
        setPreviewCount(null)
      } finally {
        setPreviewLoading(false)
      }
    }, 300)

    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [productId, variationId, dateRange])

  const handleConfirm = async () => {
    setSubmitting(true)
    try {
      const body: Record<string, unknown> = { dry_run: false }
      if (productId) body.product_id = productId
      if (variationId) body.variation_id = variationId
      if (dateRange.from) body.uploaded_from = dateRange.from.toISOString()
      if (dateRange.to) body.uploaded_to = dateRange.to.toISOString()
      const res = await apiClient.post<{ deleted: number }>('/api/pre-uploaded-products/delete-by-date', body)
      toast.success(t('preUploaded.deleteByDateSuccess', `Đã xoá ${res.data.deleted} mục`))
      onClose()
      onDeleted()
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.deleteByDateError', 'Không thể xoá')))
    } finally {
      setSubmitting(false)
    }
  }

  const hasDateRange = !!(dateRange.from || dateRange.to)
  const confirmDisabled = submitting || previewLoading || !hasDateRange || previewCount === 0 || previewCount === null

  const variationOpts = variations.map(v => ({ value: v.id, label: v.name }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('preUploaded.deleteByDate', 'Xoá theo ngày upload')}
      description={t('preUploaded.deleteByDateDesc', 'Chỉ xoá hàng chưa bán. Hàng đã bán luôn được giữ lại.')}
      size="sm"
      footer={
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="secondary" tone="subtle" size="sm" onClick={onClose}>
            {t('common.cancel', 'Huỷ')}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleConfirm}
            disabled={confirmDisabled}
            loading={submitting}
          >
            {t('preUploaded.deleteByDateConfirm', 'Xoá')}
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Select
          options={productOptions}
          value={productId}
          onChange={v => { setProductId(v); setVariationId(null) }}
          placeholder={t('preUploaded.allProducts', 'Tất cả sản phẩm')}
          clearable
          searchable
          size="sm"
        />
        <Select
          options={variationOpts}
          value={variationId}
          onChange={setVariationId}
          placeholder={t('preUploaded.filterVariation', 'Tất cả phân loại')}
          clearable
          size="sm"
          disabled={!productId}
        />
        <DateRangePicker
          value={dateRange}
          onChange={r => setDateRange(r)}
          placeholder={t('preUploaded.filterUploadDate', 'Ngày upload')}
          size="sm"
        />
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          {previewLoading
            ? '…'
            : previewCount !== null
              ? t('preUploaded.deleteByDatePreview', `Sẽ xoá ${previewCount} mục chưa bán`)
              : hasDateRange
                ? '…'
                : t('preUploaded.deleteByDateHint', 'Chọn khoảng ngày để xem trước')}
        </div>
      </div>
    </Modal>
  )
}

// ── ExportModal ───────────────────────────────────────────────────────────────

interface ExportModalProps {
  open: boolean
  onClose: () => void
  onExported: () => void
  productOptions: { value: string; label: string }[]
}

function ExportModal({ open, onClose, onExported, productOptions }: ExportModalProps) {
  const { t } = useTranslation()
  const { toast } = useToast()

  const [productId, setProductId] = useState<string | null>(null)
  const [variationId, setVariationId] = useState<string | null>(null)
  const [variations, setVariations] = useState<VariationOption[]>([])
  const [amount, setAmount] = useState<number>(1)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ExportResponse | null>(null)

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!open) {
      setProductId(null)
      setVariationId(null)
      setVariations([])
      setAmount(1)
      setSubmitting(false)
      setResult(null)
    }
  }, [open])

  // Fetch variations when product changes
  useEffect(() => {
    if (!productId) { setVariations([]); setVariationId(null); return }
    apiClient
      .get<{ items: { product_id: string; product_name: string; variations: VariationOption[] }[] }>(
        '/api/variations',
        { params: { product_id: productId } },
      )
      .then(res => {
        const flat: VariationOption[] = []
        for (const group of res.data.items) flat.push(...group.variations)
        setVariations(flat)
        setVariationId(null)
      })
      .catch(() => setVariations([]))
  }, [productId])

  const handleExport = async () => {
    if (!productId || !variationId || amount <= 0) return
    setSubmitting(true)
    try {
      const res = await apiClient.post<ExportResponse>('/api/pre-uploaded-products/export', {
        product_id: productId,
        variation_id: variationId,
        amount,
      })
      const data = res.data
      setResult(data)
      if (data.exported === 0) {
        toast.info(t('preUploaded.exportNone', 'Không có hàng để xuất'))
      } else if (data.short) {
        toast.warning(
          t('preUploaded.exportShort', `Chỉ xuất được ${data.exported}/${data.requested} mục`, {
            exported: data.exported,
            requested: data.requested,
          }),
        )
      } else {
        toast.success(
          t('preUploaded.exportSuccess', `Đã xuất ${data.exported} mục`, { count: data.exported }),
        )
      }
      onExported()
    } catch (err) {
      toast.error(formatApiError(err, t('preUploaded.exportError', 'Không thể xuất kho hàng')))
    } finally {
      setSubmitting(false)
    }
  }

  const variationOpts = variations.map(v => ({ value: v.id, label: v.name }))
  const submitDisabled = !productId || !variationId || amount <= 0 || submitting

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('preUploaded.exportTitle', 'Xuất kho hàng')}
      description={t('preUploaded.exportDesc', 'Đánh dấu hàng là đã bán và tải về file .txt')}
      size="sm"
      footer={
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="secondary" tone="subtle" size="sm" onClick={onClose}>
            {t('common.cancel', 'Huỷ')}
          </Button>
          {result && result.data.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              iconLeft={<Download size={13} />}
              onClick={() =>
                downloadTxt(
                  result.data.map(extractProductData),
                  `export_${new Date().toISOString().slice(0, 10)}.txt`,
                )
              }
            >
              {t('preUploaded.exportDownload', 'Tải xuống .txt')}
            </Button>
          )}
          {!result && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleExport}
              disabled={submitDisabled}
              loading={submitting}
            >
              {t('preUploaded.exportConfirm', 'Xuất')}
            </Button>
          )}
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!result ? (
          <>
            <Select
              options={productOptions}
              value={productId}
              onChange={v => { setProductId(v); setVariationId(null) }}
              placeholder={t('preUploaded.allProducts', 'Tất cả sản phẩm')}
              clearable
              searchable
              size="sm"
            />
            <Select
              options={variationOpts}
              value={variationId}
              onChange={setVariationId}
              placeholder={t('preUploaded.filterVariation', 'Tất cả phân loại')}
              clearable
              size="sm"
              disabled={!productId}
            />
            <Input
              type="number"
              value={String(amount)}
              onChange={e => {
                const v = parseInt(e.target.value, 10)
                if (!isNaN(v)) setAmount(v)
              }}
              placeholder={t('preUploaded.exportAmount', 'Số lượng')}
              size="sm"
            />
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div
              style={{
                fontSize: 13,
                color: result.short ? 'var(--color-warning)' : 'var(--text-muted)',
              }}
            >
              {t('preUploaded.exportResult', `Đã xuất ${result.exported}/${result.requested} mục`, {
                exported: result.exported,
                requested: result.requested,
              })}
            </div>
            {result.data.length > 0 && (
              <pre
                style={{
                  maxHeight: 240,
                  overflowY: 'auto',
                  background: 'var(--surface-subtle, #111)',
                  borderRadius: 6,
                  padding: '8px 10px',
                  fontSize: 12,
                  fontFamily: 'monospace',
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {result.data.map(extractProductData).join('\n')}
              </pre>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

// ── InventoryPage ─────────────────────────────────────────────────────────────

export function InventoryPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()

  const [searchParams, setSearchParams] = useSearchParams()
  const urlProductId = searchParams.get('product') ?? null
  const urlVariationId = searchParams.get('variation') ?? null
  const urlUsed = searchParams.get('used') ?? null
  const urlAging = searchParams.get('aging') ?? null
  const urlFrom = searchParams.get('from') ?? null
  const urlTo = searchParams.get('to') ?? null
  const urlDataSearch = searchParams.get('data_search') ?? ''
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))

  // Local state for the data search input so typing is instant; URL update is debounced
  const [dataSearchInput, setDataSearchInput] = useState(urlDataSearch)
  const dataSearchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
  const [filterVariations, setFilterVariations] = useState<VariationOption[]>([])
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [exportModalOpen, setExportModalOpen] = useState(false)

  // Fetch variation options when product filter changes
  useEffect(() => {
    if (!urlProductId) { setFilterVariations([]); return }
    apiClient
      .get<{ items: { product_id: string; product_name: string; variations: VariationOption[] }[] }>(
        '/api/variations',
        { params: { product_id: urlProductId } },
      )
      .then(res => {
        const flat: VariationOption[] = []
        for (const group of res.data.items) flat.push(...group.variations)
        setFilterVariations(flat)
      })
      .catch(() => setFilterVariations([]))
  }, [urlProductId])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {
        page: String(urlPage),
        per_page: String(perPage),
      }
      if (urlProductId) params.product_id = urlProductId
      if (urlVariationId) params.variation_id = urlVariationId
      if (urlUsed !== null) params.is_used = urlUsed
      if (urlAging && urlUsed !== 'true') params.aging_status = urlAging
      if (urlFrom) params.uploaded_from = urlFrom
      if (urlTo) params.uploaded_to = urlTo
      if (urlDataSearch) params.data_search = urlDataSearch

      const statsParams: Record<string, string> = { ...params }
      // stats endpoint doesn't accept pagination params
      delete statsParams.page
      delete statsParams.per_page

      const [dataRes, statsRes] = await Promise.all([
        apiClient.get<{ items: PreUploadedProduct[]; total: number; total_pages: number }>('/api/pre-uploaded-products', { params }),
        apiClient.get<Statistics>('/api/pre-uploaded-products/statistics', { params: statsParams }),
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
  }, [urlPage, perPage, urlProductId, urlVariationId, urlUsed, urlAging, urlFrom, urlTo, urlDataSearch, t])

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
    downloadTxt(
      selected.map(p => extractProductData(p.product_data)),
      `inventory_${new Date().toISOString().slice(0, 10)}.txt`,
    )
  }

  // ── Filter options ────────────────────────────────────────────────────
  const productOptions = useMemo(() => {
    if (!statistics) return []
    return Object.values(statistics.by_product).map(p => ({ value: p.product_id, label: p.product_name }))
  }, [statistics])

  const variationOptions = useMemo(
    () => filterVariations.map(v => ({ value: v.id, label: v.name })),
    [filterVariations],
  )

  // Upload date range reconstructed from URL params for the DateRangePicker
  const uploadDateRange: DateRange = useMemo(() => ({
    from: urlFrom ? new Date(urlFrom) : null,
    to: urlTo ? new Date(urlTo) : null,
  }), [urlFrom, urlTo])

  const columns = useMemo<ColumnDef<PreUploadedProduct>[]>(() => [
    {
      id: 'product',
      header: t('preUploaded.colProduct', 'Sản phẩm'),
      cell: row => (
        <div className="inventory-page__product-cell">
          <span>{row.product_name}</span>
          <span className="inventory-page__variation">{row.variation_name}</span>
        </div>
      ),
    },
    {
      id: 'product_data',
      header: t('preUploaded.colData', 'Dữ liệu'),
      mono: true,
      cell: row => (
        <div className="inventory-page__data-cell">
          <span className="inventory-page__data-preview">{extractProductData(row.product_data).slice(0, 32)}&hellip;</span>
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
          <span className="inventory-page__rel-time">{fmt.relative(row.used_at)}</span>
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
          <span className="inventory-page__rel-time">{fmt.relative(row.created_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 110,
      align: 'right',
      cell: row => (
        <div className="inventory-page__actions">
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
    <div className="inventory-page">
      <PageHeader
        title={t('nav.preUploaded', 'Kho hàng')}
        actions={
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Button
              variant="primary"
              size="sm"
              iconLeft={<Download size={13} />}
              onClick={() => setExportModalOpen(true)}
            >
              {t('preUploaded.export', 'Xuất kho')}
            </Button>
            <Button
              variant="destructive"
              tone="subtle"
              size="sm"
              iconLeft={<Trash2 size={13} />}
              onClick={() => setDeleteModalOpen(true)}
            >
              {t('preUploaded.deleteByDate', 'Xoá theo ngày upload')}
            </Button>
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={fetchData}
            />
          </div>
        }
      />

      {/* KPI row */}
      {statistics && (
        <div className="inventory-page__kpi-row">
          <StatCard label={t('preUploaded.total', 'Tổng cộng')} value={String(statistics.total)} icon={<Package size={16} />} loading={loading} />
          <StatCard label={t('preUploaded.available', 'Có hàng')} value={String(statistics.available)} icon={<CheckCircle size={16} />} loading={loading} />
          <StatCard label={t('preUploaded.sold', 'Đã bán')} value={String(statistics.used)} icon={<XCircle size={16} />} loading={loading} />
        </div>
      )}

      {/* Filters: Product, Variation, Status, Aging, Upload date range */}
      <div className="inventory-page__filters">
        <Select
          options={productOptions}
          value={urlProductId}
          onChange={v => setParam({ product: v, variation: null, page: null })}
          placeholder={t('preUploaded.allProducts', 'Tất cả sản phẩm')}
          clearable
          searchable
          size="sm"
          className="inventory-page__product-select"
        />
        <Select
          options={variationOptions}
          value={urlVariationId}
          onChange={v => setParam({ variation: v, page: null })}
          placeholder={t('preUploaded.filterVariation', 'Tất cả phân loại')}
          clearable
          size="sm"
          disabled={!urlProductId}
          className="inventory-page__variation-select"
        />
        <Select
          options={[
            { value: 'false', label: t('preUploaded.available', 'Có hàng') },
            { value: 'true', label: t('preUploaded.sold', 'Đã bán') },
          ]}
          value={urlUsed}
          onChange={v => {
            // Selling filter clears aging (aging only applies to unsold)
            setParam({ used: v, aging: v === 'true' ? null : urlAging, page: null })
          }}
          placeholder={t('preUploaded.allStatus', 'Tất cả trạng thái')}
          clearable
          size="sm"
          className="inventory-page__status-select"
        />
        <Select
          options={[
            { value: 'in_stock', label: t('preUploaded.agingInStock', 'Còn mới') },
            { value: 'aging', label: t('preUploaded.agingAging', 'Đã cũ') },
            { value: 'expiring_soon', label: t('preUploaded.agingExpiring', 'Sắp hết hạn') },
          ]}
          value={urlAging}
          onChange={v => setParam({ aging: v, page: null })}
          placeholder={t('preUploaded.filterAging', 'Tình trạng lưu kho')}
          clearable
          size="sm"
          // Aging is only meaningful for unsold items
          disabled={urlUsed === 'true'}
          className="inventory-page__aging-select"
        />
        <DateRangePicker
          value={uploadDateRange}
          onChange={r => setParam({
            from: r.from ? r.from.toISOString() : null,
            to: r.to ? r.to.toISOString() : null,
            page: null,
          })}
          placeholder={t('preUploaded.filterUploadDate', 'Ngày upload')}
          size="sm"
          className="inventory-page__date-filter"
        />
        <Input
          value={dataSearchInput}
          onChange={e => {
            const val = e.target.value
            setDataSearchInput(val)
            if (dataSearchDebounceRef.current) clearTimeout(dataSearchDebounceRef.current)
            dataSearchDebounceRef.current = setTimeout(() => {
              setParam({ data_search: val || null, page: null })
            }, 350)
          }}
          onClear={() => {
            setDataSearchInput('')
            if (dataSearchDebounceRef.current) clearTimeout(dataSearchDebounceRef.current)
            setParam({ data_search: null, page: null })
          }}
          leftIcon={<Search size={13} />}
          clearable
          placeholder={t('preUploaded.searchData', 'Tìm theo dữ liệu')}
          size="sm"
          className="inventory-page__data-search"
        />
      </div>

      {/* Bulk bar */}
      {selectedKeys.size > 0 && (
        <div className="inventory-page__bulk-bar">
          <span>{t('preUploaded.selected', `Đã chọn ${selectedKeys.size}`)}</span>
          <Button variant="secondary" tone="subtle" size="sm" iconLeft={<Download size={13} />} onClick={handleDownloadSelected}>
            {t('preUploaded.download', 'Tải xuống')}
          </Button>
          <Button variant="destructive" tone="subtle" size="sm" iconLeft={<Trash2 size={13} />} onClick={handleBulkDelete}>
            {t('preUploaded.bulkDelete', 'Xoá')}
          </Button>
        </div>
      )}

      <div className="inventory-page__table-card">
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
          className="inventory-page__pagination"
        />
      </div>

      <DeleteByDateModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onDeleted={fetchData}
        productOptions={productOptions}
      />

      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        onExported={fetchData}
        productOptions={productOptions}
      />
    </div>
  )
}
