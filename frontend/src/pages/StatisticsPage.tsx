import { useState, useEffect, useMemo } from 'react'
import { RefreshCw, DollarSign, ShoppingCart, Package, TrendingUp, Image as ImageIcon } from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { Line, Bar, Doughnut } from 'react-chartjs-2'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { StatCard } from '../shared/components/StatCard'
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
  recent_orders: Array<{ id: string; user_id: number; status: string; total_amount: number; created_at: string }>
  funnel: Array<{ status: string; count: number }>
  orders_heatmap: Array<{ day: number; hour: number; count: number }>
  revenue_delta: number | null
  orders_delta: number | null
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

  const sparkline = useMemo(
    () => data?.revenue_over_time_daily.slice(-7).map(r => r.revenue) ?? [],
    [data],
  )

  const [iotdUrl, setIotdUrl] = useState<string | null>(null)
  const [iotdImgError, setIotdImgError] = useState(false)
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
              onClick={loadData}
            />
          </div>
        }
      />

      {/* KPI Row */}
      <div className="stats-page__kpi-row">
        <StatCard
          label={t('statistics.totalRevenue', 'Tổng doanh thu')}
          value={fmt.currency(data?.total_revenue ?? 0)}
          delta={data?.revenue_delta}
          deltaLabel={t('statistics.vsPreviousPeriod', 'So với kỳ trước')}
          icon={<DollarSign size={16} />}
          sparkline={sparkline}
          loading={loading}
        />
        <StatCard
          label={t('statistics.totalOrders', 'Tổng đơn hàng')}
          value={fmt.number(data?.total_orders ?? 0)}
          delta={data?.orders_delta}
          deltaLabel={t('statistics.vsPreviousPeriod', 'So với kỳ trước')}
          icon={<ShoppingCart size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('statistics.totalSold', 'Sản phẩm đã bán')}
          value={fmt.number(data?.total_sold_all_products ?? 0)}
          icon={<Package size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('statistics.todayRevenue', 'Doanh thu hôm nay')}
          value={fmt.currency(data?.total_revenue_today ?? 0)}
          icon={<TrendingUp size={16} />}
          loading={loading}
        />
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
