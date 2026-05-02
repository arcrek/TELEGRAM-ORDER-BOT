import { useState, useEffect, useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Download, RefreshCw, Eye, PenLine, ShoppingCart, Info, List, Truck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef, type SortState } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { Badge, type OrderStatus } from '../shared/components/Badge'
import { Modal } from '../shared/components/Modal'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Select } from '../shared/components/Select'
import { Tooltip } from '../shared/components/Tooltip'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './OrdersPage.css'

interface Order {
  id: string
  user_id: number
  status: OrderStatus
  total_amount: number
  payment_transaction_id: string | null
  created_at: string
  updated_at: string
}

interface OrderItem {
  id: string
  quantity: number
  unit_price: number
  subtotal: number
  product: { id: string; name: string; description: string | null } | null
  variation: { id: string; name: string; price: number } | null
  delivered_products?: Array<{ id: string; used_at: string | null; display: string }>
}

interface OrderDetail extends Order {
  items: OrderItem[]
  supplier_orders: Array<{
    id: string
    supplier_id: string
    status: string
    created_at: string
    updated_at: string
  }>
}

interface OrdersResponse {
  items: Order[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

const STATUS_OPTIONS = [
  { value: 'pending', label: '' },
  { value: 'paid', label: '' },
  { value: 'processing', label: '' },
  { value: 'delivered', label: '' },
  { value: 'cancelled', label: '' },
] satisfies Array<{ value: string; label: string }>

const CANCEL_STATUSES: OrderStatus[] = ['cancelled']

export function OrdersPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()

  // ── URL-synced filters ─────────────────────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSearch = searchParams.get('q') ?? ''
  const urlStatus = searchParams.get('status') ?? null
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))
  const urlSortId = searchParams.get('sort') ?? 'created_at'
  const urlSortDir = (searchParams.get('dir') ?? 'desc') as 'asc' | 'desc'

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

  // ── Local input state (debounced into URL) ─────────────────────────
  const [searchInput, setSearchInput] = useState(urlSearch)
  useEffect(() => { setSearchInput(urlSearch) }, [urlSearch])

  // ── Data state ─────────────────────────────────────────────────────
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [perPage, setPerPage] = useState(15)

  // ── Selection ──────────────────────────────────────────────────────
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())

  // ── Detail modal ───────────────────────────────────────────────────
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailOrder, setDetailOrder] = useState<Order | null>(null)
  const [orderDetail, setOrderDetail] = useState<OrderDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // ── Status modal ───────────────────────────────────────────────────
  const [statusOpen, setStatusOpen] = useState(false)
  const [statusTarget, setStatusTarget] = useState<Order | null>(null)
  const [statusUpdating, setStatusUpdating] = useState(false)

  // ── Derived sort state ─────────────────────────────────────────────
  const sortState: SortState = { id: urlSortId, direction: urlSortDir }

  const handleSortChange = (sort: SortState) => {
    setParam({ sort: sort.id, dir: sort.direction ?? 'desc', page: null })
  }

  // ── Fetch orders ───────────────────────────────────────────────────
  const fetchOrders = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {
        page: String(urlPage),
        per_page: String(perPage),
        sort_by: urlSortId,
        sort_order: urlSortDir,
      }
      if (urlSearch) params.search = urlSearch
      if (urlStatus) params.status = urlStatus

      const res = await apiClient.get<OrdersResponse>('/api/orders', { params })
      setOrders(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      setError(formatApiError(err, t('orders.loadError', 'Không thể tải đơn hàng')))
    } finally {
      setLoading(false)
    }
  }, [urlPage, perPage, urlSortId, urlSortDir, urlSearch, urlStatus, t])

  useEffect(() => { fetchOrders() }, [fetchOrders])

  // ── View detail ────────────────────────────────────────────────────
  const handleViewDetail = async (order: Order) => {
    setDetailOrder(order)
    setDetailOpen(true)
    setOrderDetail(null)
    setDetailLoading(true)
    try {
      const res = await apiClient.get<OrderDetail>(`/api/orders/${order.id}`)
      setOrderDetail(res.data)
    } catch (err) {
      toast.error(formatApiError(err, t('orders.detailError', 'Không thể tải chi tiết đơn')))
    } finally {
      setDetailLoading(false)
    }
  }

  // ── Open status modal ──────────────────────────────────────────────
  const handleOpenStatus = (order: Order) => {
    setStatusTarget(order)
    setStatusOpen(true)
  }

  // ── Update status ──────────────────────────────────────────────────
  const handleStatusChange = async (newStatus: string) => {
    if (!statusTarget) return

    if (CANCEL_STATUSES.includes(newStatus as OrderStatus)) {
      const ok = await confirm({
        title: t('orders.cancelConfirmTitle', 'Huỷ đơn hàng?'),
        description: t('orders.cancelConfirmDesc', 'Hành động này không thể hoàn tác.'),
        confirmLabel: t('orders.cancelConfirmBtn', 'Huỷ đơn'),
        variant: 'destructive',
      })
      if (!ok) return
    }

    setStatusUpdating(true)
    try {
      await apiClient.put(`/api/orders/${statusTarget.id}/status`, { status: newStatus })
      toast.success(t('orders.statusUpdated', 'Đã cập nhật trạng thái'))
      setStatusOpen(false)
      fetchOrders()
      // Refresh detail if it's open for the same order
      if (detailOpen && detailOrder?.id === statusTarget.id) {
        const res = await apiClient.get<OrderDetail>(`/api/orders/${statusTarget.id}`)
        setOrderDetail(res.data)
        setDetailOrder(res.data)
      }
    } catch (err) {
      toast.error(formatApiError(err, t('orders.statusError', 'Không thể cập nhật trạng thái')))
    } finally {
      setStatusUpdating(false)
    }
  }

  // ── Export ─────────────────────────────────────────────────────────
  const handleExport = async () => {
    try {
      const params: Record<string, string> = {}
      if (urlSearch) params.search = urlSearch
      if (urlStatus) params.status = urlStatus

      const res = await apiClient.get('/api/orders/export', {
        params,
        responseType: 'blob',
      })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `orders_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(formatApiError(err, t('orders.exportError', 'Không thể xuất dữ liệu')))
    }
  }

  // ── Column definitions ─────────────────────────────────────────────
  const statusOptions = useMemo(
    () => STATUS_OPTIONS.map(o => ({
      value: o.value,
      label: t(`orders.status.${o.value}`, o.value),
    })),
    [t],
  )

  const columns = useMemo<ColumnDef<Order>[]>(() => [
    {
      id: 'id',
      header: t('orders.colId', 'Mã đơn'),
      mono: true,
      width: 140,
      cell: row => (
        <span className="orders-page__id" title={row.id}>
          #{row.id.slice(0, 8)}
        </span>
      ),
    },
    {
      id: 'user_id',
      header: t('orders.colUser', 'User'),
      mono: true,
      width: 80,
      align: 'right',
      accessor: 'user_id',
    },
    {
      id: 'status',
      header: t('orders.colStatus', 'Trạng thái'),
      width: 140,
      cell: row => (
        <Badge status={row.status} size="sm">
          {t(`orders.status.${row.status}`, row.status)}
        </Badge>
      ),
    },
    {
      id: 'total_amount',
      header: t('orders.colTotal', 'Tổng tiền'),
      mono: true,
      align: 'right',
      sortable: true,
      width: 140,
      cell: row => fmt.currency(row.total_amount),
    },
    {
      id: 'payment_id',
      header: t('orders.colPayment', 'Mã thanh toán'),
      mono: true,
      width: 160,
      cell: row => (
        <span className="orders-page__payment-id">
          {row.payment_transaction_id ?? '—'}
        </span>
      ),
    },
    {
      id: 'created_at',
      header: t('orders.colCreated', 'Thời gian'),
      sortable: true,
      width: 120,
      cell: row => (
        <Tooltip content={fmt.dateTime(row.created_at)} placement="top">
          <span className="orders-page__rel-time">{fmt.relative(row.created_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 80,
      align: 'right',
      cell: row => (
        <div className="orders-page__actions">
          <Tooltip content={t('orders.viewDetail', 'Xem chi tiết')}>
            <IconButton
              icon={<Eye size={14} />}
              aria-label={t('orders.viewDetail', 'Xem chi tiết')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleViewDetail(row) }}
            />
          </Tooltip>
          <Tooltip content={t('orders.updateStatus', 'Cập nhật trạng thái')}>
            <IconButton
              icon={<PenLine size={14} />}
              aria-label={t('orders.updateStatus', 'Cập nhật trạng thái')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleOpenStatus(row) }}
            />
          </Tooltip>
        </div>
      ),
    },
  ], [t, fmt])

  return (
    <div className="orders-page">
      <PageHeader
        title={t('nav.orders', 'Đơn hàng')}
        actions={
          <div className="orders-page__header-actions">
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
              onClick={fetchOrders}
            />
          </div>
        }
      />

      {/* ── Filter bar ─────────────────────────────────────────────── */}
      <div className="orders-page__filters">
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('orders.searchPlaceholder', 'Tìm theo mã đơn...')}
          value={searchInput}
          clearable
          size="sm"
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') setParam({ q: searchInput, page: null })
          }}
          onBlur={() => { if (searchInput !== urlSearch) setParam({ q: searchInput, page: null }) }}
          className="orders-page__search"
        />
        <Select
          options={statusOptions}
          value={urlStatus}
          onChange={v => setParam({ status: v, page: null })}
          placeholder={t('orders.allStatuses', 'Tất cả trạng thái')}
          clearable
          size="sm"
          className="orders-page__status-select"
        />
      </div>

      {/* ── Error banner ──────────────────────────────────────────── */}
      {error && (
        <div className="orders-page__error" role="alert">
          <span>{error}</span>
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.retry', 'Thử lại')}
            size="sm"
            variant="ghost"
            onClick={fetchOrders}
          />
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────── */}
      <div className="orders-page__table-card">
        <Table<Order>
          columns={columns}
          data={orders}
          keyFn={row => row.id}
          loading={loading}
          skeletonRows={perPage}
          selectable
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          sortState={sortState}
          onSortChange={handleSortChange}
          stickyHeader
          emptyIcon={<ShoppingCart size={40} />}
          emptyTitle={t('orders.empty', 'Chưa có đơn hàng')}
          emptyDescription={t('orders.emptyDesc', 'Thay đổi bộ lọc hoặc chờ đơn mới')}
          onRowClick={handleViewDetail}
        />

        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
          className="orders-page__pagination"
        />
      </div>

      {/* ── Order Detail Modal ─────────────────────────────────────── */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        size="lg"
        title={detailOrder ? `${t('orders.detailTitle', 'Chi tiết đơn')} #${detailOrder.id.slice(0, 8)}` : t('orders.detailTitle', 'Chi tiết đơn')}
        stickyHeader
        stickyFooter
        footer={
          <div className="orders-page__modal-footer">
            {detailOrder && (
              <Button
                variant="secondary"
                tone="subtle"
                size="sm"
                iconLeft={<PenLine size={14} />}
                onClick={() => { setDetailOpen(false); handleOpenStatus(detailOrder) }}
              >
                {t('orders.updateStatus', 'Cập nhật trạng thái')}
              </Button>
            )}
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setDetailOpen(false)}>
              {t('common.close', 'Đóng')}
            </Button>
          </div>
        }
      >
        {detailLoading ? (
          <div className="orders-page__detail-loading">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="orders-page__detail-skel-row">
                <Skeleton variant="line" width="30%" height={12} />
                <Skeleton variant="line" width="55%" height={12} />
              </div>
            ))}
          </div>
        ) : orderDetail ? (
          <div className="orders-page__detail">
            {/* Order info grid */}
            <section className="orders-page__detail-section">
              <h3 className="orders-page__detail-heading">
                <Info size={14} />
                {t('orders.orderInfo', 'Thông tin đơn')}
              </h3>
              <dl className="orders-page__detail-grid">
                <dt>{t('orders.colId', 'Mã đơn')}</dt>
                <dd className="num">{orderDetail.id}</dd>
                <dt>{t('orders.colUser', 'User')}</dt>
                <dd className="num">{orderDetail.user_id}</dd>
                <dt>{t('orders.colStatus', 'Trạng thái')}</dt>
                <dd>
                  <Badge status={orderDetail.status} size="sm">
                    {t(`orders.status.${orderDetail.status}`, orderDetail.status)}
                  </Badge>
                </dd>
                <dt>{t('orders.colTotal', 'Tổng tiền')}</dt>
                <dd className="num">{fmt.currency(orderDetail.total_amount)}</dd>
                <dt>{t('orders.colPayment', 'Mã thanh toán')}</dt>
                <dd className="num">{orderDetail.payment_transaction_id ?? '—'}</dd>
                <dt>{t('orders.colCreated', 'Thời gian tạo')}</dt>
                <dd>{fmt.dateTime(orderDetail.created_at)}</dd>
                <dt>{t('orders.updatedAt', 'Cập nhật lúc')}</dt>
                <dd>{fmt.dateTime(orderDetail.updated_at)}</dd>
              </dl>
            </section>

            {/* Order items */}
            <section className="orders-page__detail-section">
              <h3 className="orders-page__detail-heading">
                <List size={14} />
                {t('orders.items', 'Sản phẩm')}
              </h3>
              {orderDetail.items.length === 0 ? (
                <p className="orders-page__detail-empty">{t('orders.noItems', 'Không có sản phẩm')}</p>
              ) : (
                <div className="orders-page__items-table-wrap">
                  <table className="orders-page__items-table">
                    <thead>
                      <tr>
                        <th>{t('orders.product', 'Sản phẩm')}</th>
                        <th>{t('orders.variation', 'Phân loại')}</th>
                        <th className="num">{t('orders.qty', 'SL')}</th>
                        <th className="num">{t('orders.unitPrice', 'Đơn giá')}</th>
                        <th className="num">{t('orders.subtotal', 'Thành tiền')}</th>
                        <th>{t('orders.deliveredData', 'Dữ liệu giao')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderDetail.items.map(item => (
                        <tr key={item.id}>
                          <td>
                            {item.product
                              ? <strong>{item.product.name}</strong>
                              : <span className="orders-page__deleted">{t('orders.productDeleted', '(Đã xoá)')}</span>
                            }
                          </td>
                          <td>
                            {item.variation
                              ? item.variation.name
                              : <span className="orders-page__deleted">{t('orders.variationDeleted', '(Đã xoá)')}</span>
                            }
                          </td>
                          <td className="num">{item.quantity}</td>
                          <td className="num">{fmt.currency(item.unit_price)}</td>
                          <td className="num">{fmt.currency(item.subtotal)}</td>
                          <td>
                            {item.delivered_products && item.delivered_products.length > 0 ? (
                              <details className="orders-page__delivered">
                                <summary>
                                  {t('orders.viewDelivered', 'Xem')} ({item.delivered_products.length})
                                </summary>
                                <div className="orders-page__delivered-list">
                                  {item.delivered_products.map(dp => (
                                    <div key={dp.id} className="orders-page__delivered-entry">
                                      {dp.used_at && (
                                        <span className="orders-page__delivered-meta">
                                          {fmt.dateTime(dp.used_at)}
                                        </span>
                                      )}
                                      <pre className="orders-page__delivered-pre">{dp.display || '—'}</pre>
                                    </div>
                                  ))}
                                </div>
                              </details>
                            ) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Supplier orders */}
            {orderDetail.supplier_orders.length > 0 && (
              <section className="orders-page__detail-section">
                <h3 className="orders-page__detail-heading">
                  <Truck size={14} />
                  {t('orders.supplierOrders', 'Đơn nhà cung cấp')}
                </h3>
                <div className="orders-page__items-table-wrap">
                  <table className="orders-page__items-table">
                    <thead>
                      <tr>
                        <th>{t('orders.colId', 'Mã đơn')}</th>
                        <th>{t('orders.supplierId', 'NCC')}</th>
                        <th>{t('orders.colStatus', 'Trạng thái')}</th>
                        <th>{t('orders.colCreated', 'Thời gian')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderDetail.supplier_orders.map(so => (
                        <tr key={so.id}>
                          <td className="num">{so.id.slice(0, 8)}</td>
                          <td className="num">{so.supplier_id}</td>
                          <td>
                            <Badge status={so.status as OrderStatus} size="sm">
                              {t(`orders.status.${so.status}`, so.status)}
                            </Badge>
                          </td>
                          <td>{fmt.dateTime(so.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        ) : null}
      </Modal>

      {/* ── Status Update Modal ────────────────────────────────────── */}
      <Modal
        open={statusOpen}
        onClose={() => setStatusOpen(false)}
        size="sm"
        title={t('orders.updateStatus', 'Cập nhật trạng thái')}
        footer={
          <Button variant="secondary" tone="ghost" size="sm" onClick={() => setStatusOpen(false)}>
            {t('common.cancel', 'Huỷ')}
          </Button>
        }
      >
        {statusTarget && (
          <div className="orders-page__status-body">
            <p className="orders-page__status-current">
              {t('orders.currentStatus', 'Trạng thái hiện tại')}:{' '}
              <Badge status={statusTarget.status} size="sm">
                {t(`orders.status.${statusTarget.status}`, statusTarget.status)}
              </Badge>
            </p>
            <div className="orders-page__status-options">
              {(['pending', 'paid', 'processing', 'delivered', 'cancelled'] as OrderStatus[]).map(s => (
                <Button
                  key={s}
                  variant={s === 'cancelled' ? 'destructive' : 'secondary'}
                  tone={statusTarget.status === s ? 'solid' : 'subtle'}
                  size="sm"
                  disabled={statusTarget.status === s || statusUpdating}
                  loading={statusUpdating}
                  onClick={() => handleStatusChange(s)}
                >
                  {t(`orders.status.${s}`, s)}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
