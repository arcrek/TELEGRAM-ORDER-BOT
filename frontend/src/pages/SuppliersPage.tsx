import { useState, useEffect, useMemo, useCallback } from 'react'
import { Users, History, BarChart3, Link2, Plus, Trash2, RefreshCw, Star } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { Badge } from '../shared/components/Badge'
import { Modal } from '../shared/components/Modal'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Select } from '../shared/components/Select'
import { Switch } from '../shared/components/Switch'
import { Tooltip } from '../shared/components/Tooltip'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './SuppliersPage.css'

interface Supplier {
  id: string
  telegram_user_id: number
  name: string
  is_active: boolean
  created_at: string
}

interface SupplierOrder {
  supplier_order_id: string
  order_id: string
  status: string
  order_status: string
  total_amount: number
  created_at: string
  updated_at: string
}

interface SupplierStatistics {
  total_orders: number
  pending_orders: number
  delivered_orders: number
  cancelled_orders: number
  total_revenue: number
}

interface AssignedProduct {
  assignment_id: string
  product_id: string
  product_name: string
  is_primary: boolean
  created_at: string
}

interface AvailableProduct {
  id: string
  name: string
  delivery_type: string
  is_active: boolean
}

export function SuppliersPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()

  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)

  // ── Detail / history / stats / assignments modals ──────────────────
  const [detailSupplier, setDetailSupplier] = useState<Supplier | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyOrders, setHistoryOrders] = useState<SupplierOrder[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const [statsOpen, setStatsOpen] = useState(false)
  const [stats, setStats] = useState<SupplierStatistics | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  const [assignOpen, setAssignOpen] = useState(false)
  const [assignedProducts, setAssignedProducts] = useState<AssignedProduct[]>([])
  const [assignLoading, setAssignLoading] = useState(false)

  const [addProductOpen, setAddProductOpen] = useState(false)
  const [allProducts, setAllProducts] = useState<AvailableProduct[]>([])
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)
  const [isPrimary, setIsPrimary] = useState(false)
  const [addLoading, setAddLoading] = useState(false)

  const fetchSuppliers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (activeFilter !== null) params.only_active = activeFilter
      const res = await apiClient.get<{ items: Supplier[] }>('/api/suppliers', { params })
      setSuppliers(res.data.items)
    } catch (err) {
      setError(formatApiError(err, t('suppliers.loadError', 'Không thể tải nhà cung cấp')))
    } finally {
      setLoading(false)
    }
  }, [activeFilter, t])

  useEffect(() => { fetchSuppliers() }, [fetchSuppliers])

  // ── Toggle active optimistically ───────────────────────────────────
  const handleToggleActive = async (supplier: Supplier) => {
    const newActive = !supplier.is_active
    const action = newActive ? t('suppliers.activate', 'kích hoạt') : t('suppliers.deactivate', 'tắt')
    const ok = await confirm({
      title: t('suppliers.toggleTitle', `${action} ${supplier.name}?`),
      variant: newActive ? 'default' : 'destructive',
      confirmLabel: action,
    })
    if (!ok) return
    setSuppliers(prev => prev.map(s => s.id === supplier.id ? { ...s, is_active: newActive } : s))
    try {
      await apiClient.put(`/api/suppliers/${supplier.id}/status`, { is_active: newActive })
      toast.success(t('suppliers.toggled', `Đã ${action} nhà cung cấp`))
    } catch (err) {
      setSuppliers(prev => prev.map(s => s.id === supplier.id ? { ...s, is_active: !newActive } : s))
      toast.error(formatApiError(err, t('suppliers.toggleError', 'Không thể thay đổi trạng thái')))
    }
  }

  // ── Order history ──────────────────────────────────────────────────
  const openHistory = async (supplier: Supplier) => {
    setDetailSupplier(supplier)
    setHistoryOpen(true)
    setHistoryLoading(true)
    try {
      const res = await apiClient.get<{ items: SupplierOrder[] }>(`/api/suppliers/${supplier.id}/orders`)
      setHistoryOrders(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('suppliers.historyError', 'Không thể tải lịch sử')))
    } finally {
      setHistoryLoading(false)
    }
  }

  // ── Statistics ─────────────────────────────────────────────────────
  const openStats = async (supplier: Supplier) => {
    setDetailSupplier(supplier)
    setStatsOpen(true)
    setStatsLoading(true)
    try {
      const res = await apiClient.get<SupplierStatistics>(`/api/suppliers/${supplier.id}/statistics`)
      setStats(res.data)
    } catch (err) {
      toast.error(formatApiError(err, t('suppliers.statsError', 'Không thể tải thống kê')))
    } finally {
      setStatsLoading(false)
    }
  }

  // ── Assigned products ──────────────────────────────────────────────
  const openAssignments = async (supplier: Supplier) => {
    setDetailSupplier(supplier)
    setAssignOpen(true)
    setAssignLoading(true)
    try {
      const res = await apiClient.get<{ items: AssignedProduct[] }>(`/api/suppliers/${supplier.id}/products`)
      setAssignedProducts(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('suppliers.assignError', 'Không thể tải phân công')))
    } finally {
      setAssignLoading(false)
    }
  }

  const handleRemoveAssignment = async (assignmentId: string) => {
    if (!detailSupplier) return
    const ok = await confirm({ title: t('suppliers.removeAssignTitle', 'Xoá phân công?'), variant: 'destructive', confirmLabel: t('common.delete', 'Xoá') })
    if (!ok) return
    try {
      await apiClient.delete(`/api/suppliers/assignments/${assignmentId}`)
      const res = await apiClient.get<{ items: AssignedProduct[] }>(`/api/suppliers/${detailSupplier.id}/products`)
      setAssignedProducts(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('suppliers.removeAssignError', 'Không thể xoá phân công')))
    }
  }

  // ── Add product assignment ─────────────────────────────────────────
  const openAddProduct = async () => {
    setAddProductOpen(true)
    setSelectedProductId(null)
    setIsPrimary(false)
    if (allProducts.length === 0) {
      setAddLoading(true)
      try {
        const res = await apiClient.get<{ items: AvailableProduct[] }>('/api/products/', {
          params: { page: 1, per_page: 100, only_active: 'true' },
        })
        setAllProducts(res.data.items.filter(p => p.delivery_type === 'supplier_based'))
      } catch (err) {
        toast.error(formatApiError(err, t('suppliers.productsError', 'Không thể tải sản phẩm')))
      } finally {
        setAddLoading(false)
      }
    }
  }

  const handleAddAssignment = async () => {
    if (!detailSupplier || !selectedProductId) return
    try {
      await apiClient.post(`/api/suppliers/${detailSupplier.id}/products`, {
        product_id: selectedProductId,
        is_primary: isPrimary,
      })
      toast.success(t('suppliers.assigned', 'Đã phân công sản phẩm'))
      setAddProductOpen(false)
      const res = await apiClient.get<{ items: AssignedProduct[] }>(`/api/suppliers/${detailSupplier.id}/products`)
      setAssignedProducts(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('suppliers.assignSaveError', 'Không thể phân công')))
    }
  }

  // ── Table columns ──────────────────────────────────────────────────
  const activeOptions = useMemo(() => [
    { value: 'true', label: t('suppliers.active', 'Đang hoạt động') },
    { value: 'false', label: t('suppliers.inactive', 'Tắt') },
  ], [t])

  const productOptions = useMemo(() =>
    allProducts.map(p => ({ value: p.id, label: p.name })),
    [allProducts],
  )

  const columns = useMemo<ColumnDef<Supplier>[]>(() => [
    {
      id: 'name',
      header: t('suppliers.colName', 'Tên NCC'),
      sortable: false,
      cell: row => (
        <div className="suppliers-page__name-cell">
          <span className="suppliers-page__name">{row.name}</span>
          <span className="suppliers-page__tgid num">TG: {row.telegram_user_id}</span>
        </div>
      ),
    },
    {
      id: 'is_active',
      header: t('suppliers.colActive', 'Trạng thái'),
      width: 110,
      align: 'center',
      cell: row => (
        <span onClick={e => e.stopPropagation()}>
          <Switch
            checked={row.is_active}
            onChange={() => handleToggleActive(row)}
            aria-label={t('suppliers.toggleActive', 'Bật/tắt')}
          />
        </span>
      ),
    },
    {
      id: 'created_at',
      header: t('suppliers.colCreated', 'Tham gia'),
      width: 120,
      cell: row => (
        <Tooltip content={fmt.dateTime(row.created_at)}>
          <span className="suppliers-page__rel-time">{fmt.relative(row.created_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 140,
      align: 'right',
      cell: row => (
        <div className="suppliers-page__actions">
          <Tooltip content={t('suppliers.history', 'Lịch sử đơn')}>
            <IconButton icon={<History size={13} />} aria-label={t('suppliers.history', 'Lịch sử')} size="sm" variant="ghost" onClick={e => { e.stopPropagation(); openHistory(row) }} />
          </Tooltip>
          <Tooltip content={t('suppliers.stats', 'Thống kê')}>
            <IconButton icon={<BarChart3 size={13} />} aria-label={t('suppliers.stats', 'Thống kê')} size="sm" variant="ghost" onClick={e => { e.stopPropagation(); openStats(row) }} />
          </Tooltip>
          <Tooltip content={t('suppliers.assignments', 'Phân công sản phẩm')}>
            <IconButton icon={<Link2 size={13} />} aria-label={t('suppliers.assignments', 'Phân công')} size="sm" variant="ghost" onClick={e => { e.stopPropagation(); openAssignments(row) }} />
          </Tooltip>
        </div>
      ),
    },
  ], [t, fmt])

  const paginated = suppliers.slice((page - 1) * perPage, page * perPage)

  return (
    <div className="suppliers-page">
      <PageHeader
        title={t('nav.suppliers', 'Nhà cung cấp')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Làm mới')}
            variant="ghost"
            size="sm"
            onClick={fetchSuppliers}
          />
        }
      />

      <div className="suppliers-page__filters">
        <Select
          options={activeOptions}
          value={activeFilter}
          onChange={v => setActiveFilter(v)}
          placeholder={t('suppliers.allStatus', 'Tất cả trạng thái')}
          clearable
          size="sm"
          className="suppliers-page__active-select"
        />
      </div>

      {error && <div className="suppliers-page__error" role="alert">{error}</div>}

      <div className="suppliers-page__table-card">
        <Table<Supplier>
          columns={columns}
          data={paginated}
          keyFn={row => row.id}
          loading={loading}
          skeletonRows={10}
          stickyHeader
          emptyIcon={<Users size={40} />}
          emptyTitle={t('suppliers.empty', 'Chưa có nhà cung cấp')}
          emptyDescription={t('suppliers.emptyDesc', 'Nhà cung cấp đăng ký qua bot Telegram')}
        />
        <Pagination
          page={page}
          pageSize={perPage}
          total={suppliers.length}
          onPageChange={setPage}
          onPageSizeChange={size => { setPerPage(size); setPage(1) }}
          className="suppliers-page__pagination"
        />
      </div>

      {/* ── Order history modal ────────────────────────────────── */}
      <Modal
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        size="lg"
        title={`${t('suppliers.history', 'Lịch sử đơn')} — ${detailSupplier?.name ?? ''}`}
        footer={<Button variant="secondary" tone="ghost" size="sm" onClick={() => setHistoryOpen(false)}>{t('common.close', 'Đóng')}</Button>}
      >
        {historyLoading ? (
          <div className="suppliers-page__modal-skel">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="line" height={36} />)}
          </div>
        ) : historyOrders.length === 0 ? (
          <p className="suppliers-page__modal-empty">{t('suppliers.noHistory', 'Chưa có lịch sử đơn hàng')}</p>
        ) : (
          <div className="suppliers-page__inner-table-wrap">
            <table className="suppliers-page__inner-table">
              <thead>
                <tr>
                  <th>{t('orders.colId', 'Mã đơn')}</th>
                  <th>{t('orders.colStatus', 'Trạng thái')}</th>
                  <th className="num">{t('orders.colTotal', 'Tổng tiền')}</th>
                  <th>{t('orders.colCreated', 'Thời gian')}</th>
                </tr>
              </thead>
              <tbody>
                {historyOrders.map(o => (
                  <tr key={o.supplier_order_id}>
                    <td className="num">#{o.order_id.slice(0, 8)}</td>
                    <td><Badge variant="info" size="sm">{o.status}</Badge></td>
                    <td className="num">{fmt.currency(o.total_amount)}</td>
                    <td>{fmt.dateTime(o.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>

      {/* ── Stats modal ────────────────────────────────────────── */}
      <Modal
        open={statsOpen}
        onClose={() => setStatsOpen(false)}
        size="sm"
        title={`${t('suppliers.stats', 'Thống kê')} — ${detailSupplier?.name ?? ''}`}
        footer={<Button variant="secondary" tone="ghost" size="sm" onClick={() => setStatsOpen(false)}>{t('common.close', 'Đóng')}</Button>}
      >
        {statsLoading ? (
          <div className="suppliers-page__modal-skel">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="line" height={24} />)}
          </div>
        ) : stats ? (
          <dl className="suppliers-page__stats-grid">
            <dt>{t('suppliers.totalOrders', 'Tổng đơn')}</dt><dd className="num">{stats.total_orders}</dd>
            <dt>{t('suppliers.pendingOrders', 'Chờ xử lý')}</dt><dd className="num">{stats.pending_orders}</dd>
            <dt>{t('suppliers.deliveredOrders', 'Đã giao')}</dt><dd className="num">{stats.delivered_orders}</dd>
            <dt>{t('suppliers.cancelledOrders', 'Đã huỷ')}</dt><dd className="num">{stats.cancelled_orders}</dd>
            <dt>{t('suppliers.totalRevenue', 'Tổng doanh thu')}</dt><dd className="num">{fmt.currency(stats.total_revenue)}</dd>
          </dl>
        ) : null}
      </Modal>

      {/* ── Assignments modal ──────────────────────────────────── */}
      <Modal
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        size="md"
        title={`${t('suppliers.assignments', 'Phân công')} — ${detailSupplier?.name ?? ''}`}
        footer={
          <div className="suppliers-page__modal-footer">
            <Button variant="primary" size="sm" iconLeft={<Plus size={13} />} onClick={openAddProduct}>
              {t('suppliers.addProduct', 'Thêm sản phẩm')}
            </Button>
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setAssignOpen(false)}>{t('common.close', 'Đóng')}</Button>
          </div>
        }
      >
        {assignLoading ? (
          <div className="suppliers-page__modal-skel">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} variant="line" height={36} />)}
          </div>
        ) : assignedProducts.length === 0 ? (
          <p className="suppliers-page__modal-empty">{t('suppliers.noAssignments', 'Chưa có sản phẩm phân công')}</p>
        ) : (
          <div className="suppliers-page__inner-table-wrap">
            <table className="suppliers-page__inner-table">
              <thead>
                <tr>
                  <th>{t('products.colName', 'Sản phẩm')}</th>
                  <th>{t('suppliers.isPrimary', 'Chính')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {assignedProducts.map(ap => (
                  <tr key={ap.assignment_id}>
                    <td>{ap.product_name}</td>
                    <td>
                      {ap.is_primary && <Star size={13} className="suppliers-page__primary-star" />}
                    </td>
                    <td>
                      <IconButton
                        icon={<Trash2 size={13} />}
                        aria-label={t('common.delete', 'Xoá')}
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemoveAssignment(ap.assignment_id)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>

      {/* ── Add product assignment modal ───────────────────────── */}
      <Modal
        open={addProductOpen}
        onClose={() => setAddProductOpen(false)}
        size="sm"
        title={t('suppliers.addProduct', 'Thêm sản phẩm')}
        footer={
          <div className="suppliers-page__modal-footer">
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setAddProductOpen(false)}>{t('common.cancel', 'Huỷ')}</Button>
            <Button variant="primary" size="sm" disabled={!selectedProductId} onClick={handleAddAssignment}>
              {t('suppliers.assign', 'Phân công')}
            </Button>
          </div>
        }
      >
        <div className="suppliers-page__add-form">
          {addLoading ? (
            <Skeleton variant="rect" height={40} radius="8px" />
          ) : (
            <Select
              options={productOptions}
              value={selectedProductId}
              onChange={setSelectedProductId}
              placeholder={t('suppliers.selectProduct', 'Chọn sản phẩm')}
              searchable
            />
          )}
          <label className="suppliers-page__primary-label">
            <input
              type="checkbox"
              checked={isPrimary}
              onChange={e => setIsPrimary(e.target.checked)}
            />
            <span>{t('suppliers.isPrimary', 'Đặt làm nhà cung cấp chính')}</span>
          </label>
        </div>
      </Modal>
    </div>
  )
}
