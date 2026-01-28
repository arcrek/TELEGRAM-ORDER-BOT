/**
 * Statistics page with order and revenue analytics.
 * Modern industrial dark analytics with subtle gradients.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { 
  TrendingUp, 
  ShoppingCart, 
  DollarSign, 
  Package,
  BarChart3,
  PieChart,
  RefreshCw,
} from 'lucide-react'
import { Button } from '../components/Button'
import axios from 'axios'
import { Link } from 'react-router-dom'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Line, Bar, Pie } from 'react-chartjs-2'
import './StatisticsPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
)

interface StatisticsOverview {
  total_orders: number
  total_orders_today: number
  total_orders_this_week: number
  total_orders_this_month: number
  total_revenue: number
  total_revenue_today: number
  total_revenue_this_week: number
  total_revenue_this_month: number
  orders_by_status: Record<string, number>
  orders_by_product: Array<{
    product_id: string
    product_name: string
    order_count: number
  }>
  top_selling_products: Array<{
    product_id: string
    product_name: string
    quantity_sold: number
    revenue: number
  }>
  total_sold_all_products: number
  revenue_over_time_daily: Array<{
    date: string
    revenue: number
  }>
  revenue_over_time_weekly: Array<{
    date: string
    revenue: number
  }>
  revenue_over_time_monthly: Array<{
    date: string
    revenue: number
  }>
}

interface IotdResponse {
  image_url: string | null
}

export function StatisticsPage() {
  const [loading, setLoading] = useState(true)
  const [statistics, setStatistics] = useState<StatisticsOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [iotdUrl, setIotdUrl] = useState<string | null>(null)

  useEffect(() => {
    fetchStatistics()
    fetchIotd()
  }, [])

  const fetchStatistics = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      const response = await axios.get(`${API_BASE_URL}/api/statistics/overview`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      setStatistics(response.data)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load statistics')
      console.error('Error fetching statistics:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchIotd = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<IotdResponse>(`${API_BASE_URL}/api/iotd`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      setIotdUrl(response.data.image_url || null)
    } catch (err: any) {
      console.error('Error fetching IOTD:', err)
      setIotdUrl(null)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: 'VND',
    }).format(amount)
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('vi-VN').format(num)
  }

  if (loading) {
    return (
      <div className="statistics-page">
        <div className="statistics-loading">
          <p>Loading statistics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="statistics-page">
        <Card>
          <div className="statistics-error">
            <p>Error: {error}</p>
            <button onClick={fetchStatistics} className="retry-button">
              Retry
            </button>
          </div>
        </Card>
      </div>
    )
  }

  if (!statistics) {
    return null
  }

  // Prepare chart data
  const revenueChartData = {
    labels: statistics.revenue_over_time_daily.map((item) => {
      const date = new Date(item.date)
      return date.toLocaleDateString('vi-VN', { month: 'short', day: 'numeric' })
    }),
    datasets: [
      {
        label: 'Revenue (VND)',
        data: statistics.revenue_over_time_daily.map((item) => item.revenue),
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37, 99, 235, 0.18)',
        tension: 0.3,
        pointRadius: 0,
        pointHitRadius: 8,
      },
    ],
  }

  const statusChartData = {
    labels: Object.keys(statistics.orders_by_status),
    datasets: [
      {
        label: 'Orders',
        data: Object.values(statistics.orders_by_status),
        backgroundColor: [
          '#22c55e', // delivered / success
          '#2563eb', // active / paid
          '#f59e0b', // pending / warning
          '#ef4444', // cancelled / error
          '#6b7280', // other
        ],
      },
    ],
  }

  const topProductsData = {
    labels: statistics.top_selling_products.slice(0, 5).map((p) => p.product_name),
    datasets: [
      {
        label: 'Quantity Sold',
        data: statistics.top_selling_products.slice(0, 5).map((p) => p.quantity_sold),
        backgroundColor: 'rgba(75, 130, 255, 0.9)',
        borderRadius: 4,
      },
    ],
  }

  return (
    <div className="statistics-page">
      <div className="statistics-header">
        <h1>Statistics Dashboard</h1>
        <Button
          onClick={() => {
            fetchStatistics()
            fetchIotd()
          }}
          variant="secondary"
          size="small"
          className="refresh-button"
          title="Reload statistics data"
        >
          <RefreshCw size={16} />
          <span>Refresh</span>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="statistics-cards">
        <Card className="stat-card stat-card--iotd">
          <div className="stat-card-content stat-card-content--iotd">
            <div className="stat-card-info">
              <div className="stat-card-iotd-head">
                <h3>Image of the Day</h3>
                <Link to="/iotd" className="stat-card-iotd-link" title="Configure Image of the Day">
                  Configure
                </Link>
              </div>
              <div className="stat-card-iotd-frame">
                {iotdUrl ? (
                  <img src={iotdUrl} alt="Image of the Day" />
                ) : (
                  <div className="stat-card-iotd-empty">No image configured</div>
                )}
              </div>
            </div>
          </div>
        </Card>

        <Card className="stat-card stat-card--orders">
          <div className="stat-card-content">
            <div className="stat-card-icon">
              <ShoppingCart size={24} />
            </div>
            <div className="stat-card-info">
              <h3>Total Orders</h3>
              <p className="stat-value">{formatNumber(statistics.total_orders)}</p>
              <p className="stat-subtitle">
                {formatNumber(statistics.total_orders_today)} today
              </p>
            </div>
          </div>
        </Card>

        <Card className="stat-card stat-card--revenue">
          <div className="stat-card-content">
            <div className="stat-card-icon">
              <DollarSign size={24} />
            </div>
            <div className="stat-card-info">
              <h3>Total Revenue</h3>
              <p className="stat-value">{formatCurrency(statistics.total_revenue)}</p>
              <p className="stat-subtitle">
                {formatCurrency(statistics.total_revenue_today)} today
              </p>
            </div>
          </div>
        </Card>

        <Card className="stat-card stat-card--sold">
          <div className="stat-card-content">
            <div className="stat-card-icon">
              <Package size={24} />
            </div>
            <div className="stat-card-info">
              <h3>Total Sold</h3>
              <p className="stat-value">
                {formatNumber(statistics.total_sold_all_products)}
              </p>
              <p className="stat-subtitle">items</p>
            </div>
          </div>
        </Card>

        <Card className="stat-card stat-card--week">
          <div className="stat-card-content">
            <div className="stat-card-icon">
              <TrendingUp size={24} />
            </div>
            <div className="stat-card-info">
              <h3>This Week</h3>
              <p className="stat-value">
                {formatNumber(statistics.total_orders_this_week)}
              </p>
              <p className="stat-subtitle">
                {formatCurrency(statistics.total_revenue_this_week)} revenue
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Charts */}
      <div className="statistics-charts">
        <Card className="chart-card">
          <div className="chart-header">
            <BarChart3 size={20} />
            <h2>Revenue Over Time</h2>
          </div>
          <div className="chart-container">
            <Line
              data={revenueChartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    labels: {
                      color: '#e5e7eb',
                    },
                  },
                  tooltip: {
                    mode: 'index',
                    intersect: false,
                  },
                },
                interaction: {
                  mode: 'nearest',
                  intersect: false,
                },
                scales: {
                  x: {
                    ticks: { color: '#9ca3af' },
                    grid: { color: 'rgba(148, 163, 184, 0.25)' },
                  },
                  y: {
                    ticks: { color: '#9ca3af' },
                    grid: { color: 'rgba(148, 163, 184, 0.22)' },
                  },
                },
              }}
            />
          </div>
        </Card>

        <Card className="chart-card">
          <div className="chart-header">
            <PieChart size={20} />
            <h2>Orders by Status</h2>
          </div>
          <div className="chart-container">
            <Pie
              data={statusChartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'bottom',
                    labels: {
                      color: '#e5e7eb',
                    },
                  },
                },
              }}
            />
          </div>
        </Card>

        <Card className="chart-card">
          <div className="chart-header">
            <BarChart3 size={20} />
            <h2>Top Selling Products</h2>
          </div>
          <div className="chart-container">
            <Bar
              data={topProductsData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                  legend: {
                    labels: {
                      color: '#e5e7eb',
                    },
                  },
                },
                scales: {
                  x: {
                    ticks: { color: '#9ca3af' },
                    grid: { color: 'rgba(148, 163, 184, 0.25)' },
                  },
                  y: {
                    ticks: { color: '#9ca3af' },
                    grid: { color: 'rgba(148, 163, 184, 0.18)' },
                  },
                },
              }}
            />
          </div>
        </Card>
      </div>
    </div>
  )
}
