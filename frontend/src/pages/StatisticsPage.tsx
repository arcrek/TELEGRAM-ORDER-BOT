import { useState, useEffect, useMemo, useCallback } from 'react'
import { RefreshCw, Image as ImageIcon, ChevronUp, ChevronDown } from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { Line, Bar, Doughnut } from 'react-chartjs-2'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { ChartCard } from '../shared/components/ChartCard'
import { Badge } from '../shared/components/Badge'
import type { OrderStatus } from '../shared/components/Badge'
import { IconButton } from '../shared/components/IconButton'
import { Tabs } from '../shared/components/Tabs'
import { DateRangePicker, type DateRange, type RangePreset } from '../shared/components/DateRangePicker'
import { useToast } from '../shared/components/Toast'
import { apiClient } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import { getChartTheme, getBaseChartOptions } from '../shared/lib/charts'
import { useTheme } from '../contexts/ThemeContext'
import './StatisticsPage.css'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Title, Tooltip, Legend, Filler,
)

interface RevenueByProduct {
  product_id: number
  product_name: string
  total_sold: number
  revenue: number
  pct_change?: number | null
}

interface StatisticsData {
  total_orders: number
  total_revenue: number
  total_sold_all_products: number
  total_orders_today: number
  total_revenue_today: number
  orders_by_status: Record<string, number>
  revenue_over_time_daily: Array<{ date: string; revenue: number }>
  revenue_over_time_weekly: Array<{ date: string; revenue: number }>
  revenue_over_time_monthly: Array<{ date: string; revenue: number }>
  top_selling_products: Array<{ product_name: string; quantity_sold: number; revenue: number }>
  revenue_by_product: RevenueByProduct[]
  recent_orders: Array<{ id: string; user_id: number; status: string; total_amount: number; created_at: string }>
  funnel: Array<{ status: string; count: number }>
  orders_heatmap: Array<{ day: number; hour: number; count: number }>
  revenue_delta: number | null
  orders_delta: number | null
  active_users?: { current: number; previous: number; pct_change: number | null }
  user_stats?: { started: number; active: number }
}

interface UpgradeOrderTodo {
  id: string
  status: string
  total_amount: number
  created_at: string
}

interface InventoryVariationTodo {
  product_id: string
  product_name: string
  variation_id: string
  variation_name: string
  in_stock: number
  aging: number
  expiring_soon: number
}

interface TodoData {
  upgrade_orders: UpgradeOrderTodo[]
  upgrade_orders_count: number
  aging_inventory: InventoryVariationTodo[]
  aging_inventory_count: number
  low_stock_inventory: InventoryVariationTodo[]
  low_stock_inventory_count: number
}

const DAY_LABELS = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7']

export function StatisticsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const fmt = useFormat()
  const { resolvedTheme } = useTheme()
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<StatisticsData | null>(null)
  const [range, setRange] = useState<DateRange>({ from: null, to: null })
  const [rangePreset, setRangePreset] = useState<RangePreset>('30d')
  const [revTab, setRevTab] = useState('daily')
  const [productSort, setProductSort] = useState<{ key: keyof RevenueByProduct; dir: 'asc' | 'desc' }>({ key: 'revenue', dir: 'desc' })

  const theme = useMemo(() => getChartTheme(), [resolvedTheme])
  const baseOpts = useMemo(() => getBaseChartOptions(theme), [theme])

  const loadData = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (rangePreset !== 'custom') {
        params.range = rangePreset
      } else if (range.from && range.to) {
        params.range = 'custom'
        params.from = range.from.toISOString()
        params.to = range.to.toISOString()
      }
      const res = await apiClient.get('/api/statistics/overview', { params })
      setData(res.data)
    } catch {
      toast.error(t('statistics.loadError', 'Không thể tải thống kê'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [rangePreset, range.from, range.to])

  const handleRangeChange = (r: DateRange, preset: RangePreset) => {
    setRange(r)
    setRangePreset(preset)
  }

  // Revenue chart data
  const revData = useMemo(() => {
    if (!data) return null
    const raw = revTab === 'daily' ? data.revenue_over_time_daily
      : revTab === 'weekly' ? data.revenue_over_time_weekly
      : data.revenue_over_time_monthly
    return {
      labels: raw.map(r => r.date.slice(5)),
      datasets: [{
        label: t('statistics.revenue', 'Doanh thu'),
        data: raw.map(r => r.revenue),
        borderColor: theme.brand500,
        backgroundColor: `${theme.brand500}22`,
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        pointHoverRadius: 4,
      }],
    }
  }, [data, revTab, theme])

  // Status donut
  const donutData = useMemo(() => {
    if (!data) return null
    const statusColors: Record<string, string> = {
      pending: theme.viz[2], paid: theme.viz[0],
      processing: theme.viz[5], delivered: theme.viz[1], cancelled: theme.viz[3],
    }
    const entries = Object.entries(data.orders_by_status)
    return {
      labels: entries.map(([s]) => t(`orders.status.${s}`, s)),
      datasets: [{
        data: entries.map(([, v]) => v),
        backgroundColor: entries.map(([s]) => statusColors[s] ?? theme.viz[4]),
        borderWidth: 0,
        hoverOffset: 4,
      }],
    }
  }, [data, theme])

  // Top products bar
  const topData = useMemo(() => {
    if (!data) return null
    const top = data.top_selling_products.slice(0, 8)
    return {
      labels: top.map(p => p.product_name.slice(0, 20)),
      datasets: [{
        label: t('statistics.sold', 'Đã bán'),
        data: top.map(p => p.quantity_sold),
        backgroundColor: theme.viz[0],
        borderRadius: 4,
        borderSkipped: false,
      }],
    }
  }, [data, theme])

  // Funnel data
  const funnelData = useMemo(() => {
    if (!data?.funnel) return null
    return {
      labels: data.funnel.map(f => t(`orders.status.${f.status}`, f.status)),
      datasets: [{
        label: '',
        data: data.funnel.map(f => f.count),
        backgroundColor: [theme.viz[2], theme.viz[0], theme.viz[5], theme.viz[1], theme.viz[3]],
        borderRadius: 4,
        borderSkipped: false,
      }],
    }
  }, [data, theme])

  const heatmapMax = useMemo(() => {
    if (!data?.orders_heatmap) return 1
    return Math.max(...data.orders_heatmap.map(c => c.count), 1)
  }, [data])

  const hasDelta = useMemo(
    () => (data?.revenue_by_product?.length ?? 0) > 0 && 'pct_change' in (data?.revenue_by_product[0] ?? {}),
    [data?.revenue_by_product],
  )

  const sortedProducts = useMemo(() => {
    if (!data?.revenue_by_product) return []
    return [...data.revenue_by_product].sort((a, b) => {
      const va = a[productSort.key] as number | string
      const vb = b[productSort.key] as number | string
      if (typeof va === 'string') return productSort.dir === 'asc' ? va.localeCompare(vb as string) : (vb as string).localeCompare(va)
      return productSort.dir === 'asc' ? (va as number) - (vb as number) : (vb as number) - (va as number)
    })
  }, [data?.revenue_by_product, productSort])

  const toggleProductSort = useCallback((key: keyof RevenueByProduct) => {
    setProductSort(prev => prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' })
  }, [])

  const [iotdUrl, setIotdUrl] = useState<string | null>(null)
  const [iotdImgError, setIotdImgError] = useState(false)

  const navigate = useNavigate()
  const [todoData, setTodoData] = useState<TodoData | null>(null)
  const [todoLoading, setTodoLoading] = useState(true)

  const loadTodo = async () => {
    setTodoLoading(true)
    try {
      const res = await apiClient.get<TodoData>('/api/statistics/todo')
      setTodoData(res.data)
    } catch {
      // fail silently
    } finally {
      setTodoLoading(false)
    }
  }

  useEffect(() => { loadTodo() }, [])

  useEffect(() => {
    apiClient.get<{ image_url: string | null }>('/api/iotd')
      .then(res => setIotdUrl(res.data.image_url))
      .catch(() => {})
  }, [])

  return (
    <div className="stats-page">
      <PageHeader
        title={t('nav.statistics', 'Thống kê')}
        actions={
          <div className="stats-page__header-actions">
            <DateRangePicker value={range} onChange={handleRangeChange} size="sm" />
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={() => { loadData(); loadTodo() }}
            />
          </div>
        }
      />

      {/* Vitals strip */}
      <div className="stats-vitals">
        {/* Revenue */}
        <div className="stats-vitals__item">
          <span className="stats-vitals__label">{t('statistics.totalRevenue', 'Tổng doanh thu')}</span>
          {loading ? <div className="stats-vitals__skeleton" /> : (
            <span className="stats-vitals__value">{fmt.currency(data?.total_revenue ?? 0)}</span>
          )}
          {!loading && data?.revenue_delta != null && (
            <span className={`stats-vitals__delta stats-vitals__delta--${data.revenue_delta > 0 ? 'pos' : data.revenue_delta < 0 ? 'neg' : 'flat'}`}>
              {data.revenue_delta > 0 ? '▲' : data.revenue_delta < 0 ? '▼' : '—'} {Math.abs(data.revenue_delta).toFixed(1)}%
            </span>
          )}
        </div>

        {/* Today revenue */}
        <div className="stats-vitals__item">
          <span className="stats-vitals__label">{t('statistics.todayRevenue', 'Hôm nay')}</span>
          {loading ? <div className="stats-vitals__skeleton" /> : (
            <span className="stats-vitals__value">{fmt.currency(data?.total_revenue_today ?? 0)}</span>
          )}
        </div>

        {/* Orders */}
        <div className="stats-vitals__item">
          <span className="stats-vitals__label">{t('statistics.totalOrders', 'Đơn hàng')}</span>
          {loading ? <div className="stats-vitals__skeleton" /> : (
            <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.total_orders ?? 0)}</span>
          )}
          {!loading && data?.orders_delta != null && (
            <span className={`stats-vitals__delta stats-vitals__delta--${data.orders_delta > 0 ? 'pos' : data.orders_delta < 0 ? 'neg' : 'flat'}`}>
              {data.orders_delta > 0 ? '▲' : data.orders_delta < 0 ? '▼' : '—'} {Math.abs(data.orders_delta).toFixed(1)}%
            </span>
          )}
        </div>

        {/* Sold */}
        <div className="stats-vitals__item">
          <span className="stats-vitals__label">{t('statistics.totalSold', 'Đã bán')}</span>
          {loading ? <div className="stats-vitals__skeleton" /> : (
            <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.total_sold_all_products ?? 0)}</span>
          )}
        </div>

        {/* Active buyers */}
        <div className="stats-vitals__item">
          <span className="stats-vitals__label">{t('statistics.activeBuyers', 'Người mua')}</span>
          {loading ? <div className="stats-vitals__skeleton" /> : (
            <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.active_users?.current ?? 0)}</span>
          )}
          {!loading && data?.active_users?.pct_change != null && (
            <span className={`stats-vitals__delta stats-vitals__delta--${data.active_users.pct_change > 0 ? 'pos' : data.active_users.pct_change < 0 ? 'neg' : 'flat'}`}>
              {data.active_users.pct_change > 0 ? '▲' : data.active_users.pct_change < 0 ? '▼' : '—'} {Math.abs(data.active_users.pct_change).toFixed(1)}%
            </span>
          )}
        </div>

        {/* Registered / started users */}
        <div className="stats-vitals__item">
          <span className="stats-vitals__label">{t('statistics.startedUsers', 'Đã dùng')}</span>
          {loading ? <div className="stats-vitals__skeleton" /> : (
            <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.user_stats?.started ?? 0)}</span>
          )}
        </div>
      </div>

      {/* Product Revenue Table */}
      <div className="stats-product-revenue chart-card">
        <div className="chart-card__header">
          <h3 className="chart-card__title">{t('statistics.revenueByProduct', 'Doanh thu theo sản phẩm')}</h3>
        </div>
        <div className="stats-product-revenue__table-wrap">
          <table className="stats-product-revenue__table">
            <thead>
              <tr>
                <th className="stats-product-revenue__th stats-product-revenue__th--num">#</th>
                <th
                  className={`stats-product-revenue__th stats-product-revenue__th--sortable${productSort.key === 'product_name' ? ' active' : ''}`}
                  onClick={() => toggleProductSort('product_name')}
                >
                  {t('statistics.productName', 'Sản phẩm')}
                  <span className="stats-product-revenue__sort-icon">
                    {productSort.key === 'product_name' ? (productSort.dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronDown size={12} className="muted" />}
                  </span>
                </th>
                <th
                  className={`stats-product-revenue__th stats-product-revenue__th--right stats-product-revenue__th--sortable${productSort.key === 'total_sold' ? ' active' : ''}`}
                  onClick={() => toggleProductSort('total_sold')}
                >
                  {t('statistics.unitsSold', 'Đã bán')}
                  <span className="stats-product-revenue__sort-icon">
                    {productSort.key === 'total_sold' ? (productSort.dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronDown size={12} className="muted" />}
                  </span>
                </th>
                <th
                  className={`stats-product-revenue__th stats-product-revenue__th--right stats-product-revenue__th--sortable${productSort.key === 'revenue' ? ' active' : ''}`}
                  onClick={() => toggleProductSort('revenue')}
                >
                  {t('statistics.revenue', 'Doanh thu')}
                  <span className="stats-product-revenue__sort-icon">
                    {productSort.key === 'revenue' ? (productSort.dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronDown size={12} className="muted" />}
                  </span>
                </th>
                {hasDelta && (
                  <th className="stats-product-revenue__th stats-product-revenue__th--right stats-product-revenue__th--delta">
                    {t('statistics.pctChange', '% Thay đổi')}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="stats-product-revenue__row stats-product-revenue__row--skeleton">
                    <td className="stats-product-revenue__td stats-product-revenue__td--num"><span className="skeleton-line" /></td>
                    <td className="stats-product-revenue__td"><span className="skeleton-line" /></td>
                    <td className="stats-product-revenue__td stats-product-revenue__td--right"><span className="skeleton-line" /></td>
                    <td className="stats-product-revenue__td stats-product-revenue__td--right"><span className="skeleton-line" /></td>
                    {hasDelta && <td className="stats-product-revenue__td stats-product-revenue__td--right"><span className="skeleton-line" /></td>}
                  </tr>
                ))
              ) : sortedProducts.length === 0 ? (
                <tr>
                  <td colSpan={hasDelta ? 5 : 4} className="stats-product-revenue__empty">{t('statistics.noData', 'Chưa có dữ liệu')}</td>
                </tr>
              ) : (
                sortedProducts.map((p, idx) => (
                  <tr key={p.product_id} className="stats-product-revenue__row">
                    <td className="stats-product-revenue__td stats-product-revenue__td--num">{idx + 1}</td>
                    <td className="stats-product-revenue__td stats-product-revenue__td--name">{p.product_name}</td>
                    <td className="stats-product-revenue__td stats-product-revenue__td--right num">{fmt.number(p.total_sold)}</td>
                    <td className="stats-product-revenue__td stats-product-revenue__td--right num stats-product-revenue__td--revenue">{fmt.currency(p.revenue)}</td>
                    {hasDelta && (
                      <td className="stats-product-revenue__td stats-product-revenue__td--right stats-product-revenue__td--delta num">
                        {p.pct_change == null ? (
                          <span className="stats-product-revenue__delta stats-product-revenue__delta--neutral">—</span>
                        ) : p.pct_change > 0 ? (
                          <span className="stats-product-revenue__delta stats-product-revenue__delta--pos">▲ {p.pct_change}%</span>
                        ) : p.pct_change < 0 ? (
                          <span className="stats-product-revenue__delta stats-product-revenue__delta--neg">▼ {Math.abs(p.pct_change)}%</span>
                        ) : (
                          <span className="stats-product-revenue__delta stats-product-revenue__delta--neutral">0%</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Todo Section */}
      <div className="stats-todo chart-card">
        <div className="chart-card__header">
          <h3 className="chart-card__title">Việc cần làm</h3>
        </div>
        <div className="stats-todo__body">

          {/* Group 1: Pending upgrade orders */}
          <div className="stats-todo__group">
            <div className="stats-todo__group-header">
              <span className="stats-todo__group-title">Đơn nâng cấp đang chờ</span>
              {todoData && (
                <span className={`stats-todo__badge${todoData.upgrade_orders_count > 0 ? ' stats-todo__badge--warn' : ''}`}>
                  {todoData.upgrade_orders_count}
                </span>
              )}
            </div>
            {todoLoading ? (
              <div className="stats-todo__skeleton" />
            ) : !todoData?.upgrade_orders.length ? (
              <p className="stats-todo__empty">Không có đơn nào</p>
            ) : (
              todoData.upgrade_orders.map(order => (
                <button
                  key={order.id}
                  className="stats-todo__row"
                  onClick={() => navigate(`/orders?q=${order.id}`)}
                >
                  <span className="stats-todo__row-id num">#{order.id.slice(0, 8)}</span>
                  <Badge status={order.status as OrderStatus} size="sm">
                    {t(`orders.status.${order.status}`, order.status)}
                  </Badge>
                  <span className="stats-todo__row-amount num">{fmt.currency(order.total_amount)}</span>
                  <span className="stats-todo__row-time">{fmt.relative(order.created_at)}</span>
                </button>
              ))
            )}
          </div>

          {/* Group 2: Aging / expiring-soon inventory */}
          <div className="stats-todo__group">
            <div className="stats-todo__group-header">
              <span className="stats-todo__group-title">Tồn kho đã cũ / sắp hết hạn</span>
              {todoData && (
                <span className={`stats-todo__badge${todoData.aging_inventory_count > 0 ? ' stats-todo__badge--warn' : ''}`}>
                  {todoData.aging_inventory_count}
                </span>
              )}
            </div>
            {todoLoading ? (
              <div className="stats-todo__skeleton" />
            ) : !todoData?.aging_inventory.length ? (
              <p className="stats-todo__empty">Không có phân loại nào</p>
            ) : (
              todoData.aging_inventory.map(v => (
                <button
                  key={`aging-${v.variation_id}`}
                  className="stats-todo__row"
                  onClick={() => navigate(`/pre-uploaded?product=${v.product_id}&variation=${v.variation_id}&aging=aging`)}
                >
                  <span className="stats-todo__row-name">{v.product_name}</span>
                  <span className="stats-todo__row-variation">{v.variation_name}</span>
                  <span className="stats-todo__row-tags">
                    {v.aging > 0 && <span className="stats-todo__tag stats-todo__tag--aged">{v.aging} cũ</span>}
                    {v.expiring_soon > 0 && <span className="stats-todo__tag stats-todo__tag--expiring">{v.expiring_soon} sắp hết</span>}
                  </span>
                </button>
              ))
            )}
          </div>

          {/* Group 3: Low stock inventory */}
          <div className="stats-todo__group">
            <div className="stats-todo__group-header">
              <span className="stats-todo__group-title">Tồn kho sắp hết</span>
              {todoData && (
                <span className={`stats-todo__badge${todoData.low_stock_inventory_count > 0 ? ' stats-todo__badge--danger' : ''}`}>
                  {todoData.low_stock_inventory_count}
                </span>
              )}
            </div>
            {todoLoading ? (
              <div className="stats-todo__skeleton" />
            ) : !todoData?.low_stock_inventory.length ? (
              <p className="stats-todo__empty">Không có phân loại nào</p>
            ) : (
              todoData.low_stock_inventory.map(v => (
                <button
                  key={`lowstock-${v.variation_id}`}
                  className="stats-todo__row"
                  onClick={() => navigate(`/pre-uploaded?product=${v.product_id}&variation=${v.variation_id}`)}
                >
                  <span className="stats-todo__row-name">{v.product_name}</span>
                  <span className="stats-todo__row-variation">{v.variation_name}</span>
                  <span className={`stats-todo__stock-pill${v.in_stock === 0 ? ' stats-todo__stock-pill--out' : ' stats-todo__stock-pill--low'}`}>
                    {v.in_stock === 0 ? 'Hết hàng' : `${v.in_stock} còn`}
                  </span>
                </button>
              ))
            )}
          </div>

        </div>
      </div>

      {/* Bento grid */}
      <div className="stats-page__bento">
        <ChartCard
          title={t('statistics.revenueTrend', 'Xu hướng doanh thu')}
          loading={loading}
          minHeight={200}
          className="stats-page__revenue-chart"
          actions={
            <Tabs
              tabs={[
                { key: 'daily', label: t('statistics.daily', 'Ngày'), panel: null },
                { key: 'weekly', label: t('statistics.weekly', 'Tuần'), panel: null },
                { key: 'monthly', label: t('statistics.monthly', 'Tháng'), panel: null },
              ]}
              activeKey={revTab}
              onChange={setRevTab}
              variant="pill"
              size="sm"
            />
          }
        >
          {revData && (
            <Line
              key={`rev-${resolvedTheme}-${revTab}`}
              data={revData}
              options={{ ...baseOpts, plugins: { ...baseOpts.plugins, legend: { display: false } } } as Parameters<typeof Line>[0]['options']}
            />
          )}
        </ChartCard>

        <ChartCard
          title={t('statistics.ordersByStatus', 'Đơn theo trạng thái')}
          loading={loading}
          minHeight={200}
          className="stats-page__donut-chart"
        >
          {donutData && (
            <Doughnut
              key={`donut-${resolvedTheme}`}
              data={donutData}
              options={{
                cutout: '65%',
                plugins: {
                  legend: { position: 'bottom', labels: { color: theme.textMuted, font: { size: 10 }, boxWidth: 10 } },
                },
              }}
            />
          )}
        </ChartCard>

        <ChartCard
          title={t('statistics.conversionFunnel', 'Phễu chuyển đổi')}
          loading={loading}
          minHeight={160}
          className="stats-page__funnel-chart"
        >
          {funnelData && (
            <Bar
              key={`funnel-${resolvedTheme}`}
              data={funnelData}
              options={{ ...baseOpts, indexAxis: 'y' as const, plugins: { ...baseOpts.plugins, legend: { display: false } } } as Parameters<typeof Bar>[0]['options']}
            />
          )}
        </ChartCard>

        <ChartCard
          title={t('statistics.topProducts', 'Sản phẩm bán chạy')}
          loading={loading}
          minHeight={160}
          className="stats-page__top-chart"
        >
          {topData && (
            <Bar
              key={`top-${resolvedTheme}`}
              data={topData}
              options={{ ...baseOpts, indexAxis: 'y' as const, plugins: { ...baseOpts.plugins, legend: { display: false } } } as Parameters<typeof Bar>[0]['options']}
            />
          )}
        </ChartCard>

        {/* Heatmap */}
        <div className="stats-page__heatmap chart-card">
          <div className="chart-card__header">
            <h3 className="chart-card__title">{t('statistics.heatmap', 'Mật độ đơn theo giờ')}</h3>
          </div>
          <div className="stats-heatmap">
            <div className="stats-heatmap__y-labels">
              {DAY_LABELS.map(d => <span key={d} className="stats-heatmap__label">{d}</span>)}
            </div>
            <div className="stats-heatmap__grid">
              {DAY_LABELS.map((_, day) => (
                <div key={day} className="stats-heatmap__row">
                  {Array.from({ length: 24 }).map((_, hour) => {
                    const cell = data?.orders_heatmap.find(c => c.day === day && c.hour === hour)
                    const intensity = cell ? cell.count / heatmapMax : 0
                    return (
                      <div
                        key={hour}
                        className="stats-heatmap__cell"
                        title={`${DAY_LABELS[day]} ${hour}h: ${cell?.count ?? 0}`}
                        style={{ opacity: intensity ? 0.1 + intensity * 0.9 : 0.04 }}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Image of the Day */}
        <div className="stats-page__iotd chart-card">
          <div className="chart-card__header">
            <h3 className="chart-card__title">{t('nav.iotd', 'Ảnh ngày')}</h3>
          </div>
          <div className="stats-iotd">
            {iotdUrl && !iotdImgError ? (
              <img
                src={iotdUrl}
                alt={t('iotd.previewAlt', 'Ảnh ngày')}
                className="stats-iotd__img"
                onError={() => setIotdImgError(true)}
              />
            ) : (
              <div className="stats-iotd__empty">
                <ImageIcon size={28} />
                <span>{iotdImgError ? t('iotd.imageError', 'Không tải được ảnh') : t('iotd.noImage', 'Chưa có ảnh')}</span>
              </div>
            )}
          </div>
        </div>

        {/* Activity feed */}
        <div className="stats-page__activity chart-card">
          <div className="chart-card__header">
            <h3 className="chart-card__title">{t('statistics.recentOrders', 'Đơn hàng gần đây')}</h3>
          </div>
          <div className="stats-activity">
            {data?.recent_orders.map(order => (
              <div key={order.id} className="stats-activity__row">
                <span className="stats-activity__id num">#{order.id.slice(0, 8)}</span>
                <Badge status={order.status as OrderStatus} size="sm">
                  {t(`orders.status.${order.status}`, order.status)}
                </Badge>
                <span className="stats-activity__amount num">
                  {fmt.currency(order.total_amount)}
                </span>
                <span className="stats-activity__time">
                  {fmt.relative(order.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
