/**
 * Orders Management page.
 * Premium Dark SaaS Design System.
 */
import { useState, useEffect, KeyboardEvent } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Select } from '../components/Select'
import {
  Eye,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ShoppingCart,
  Filter,
  X,
  RefreshCw,
  Download,
  Info,
  Package,
  Truck,
  List,
} from 'lucide-react'
import axios from 'axios'
import './OrdersPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface Order {
  id: string
  user_id: number
  status: 'pending' | 'paid' | 'processing' | 'delivered' | 'cancelled'
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
  product: {
    id: string
    name: string
    description: string | null
  } | null
  variation: {
    id: string
    name: string
    price: number
  } | null
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

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [perPage] = useState(15)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  
  // Filters and search
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [userIdFilter, setUserIdFilter] = useState<string>('')
  const [productIdFilter, setProductIdFilter] = useState<string>('')
  const [sortBy, setSortBy] = useState<'created_at' | 'total_amount' | 'status'>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  
  // Modal states
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [showStatusModal, setShowStatusModal] = useState(false)
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [orderDetail, setOrderDetail] = useState<OrderDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    fetchOrders()
  }, [page, search, statusFilter, userIdFilter, productIdFilter, sortBy, sortOrder])

  const fetchOrders = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      })
      
      if (search) {
        params.append('search', search)
      }
      if (statusFilter) {
        params.append('status', statusFilter)
      }
      if (userIdFilter) {
        params.append('user_id', userIdFilter)
      }
      if (productIdFilter) {
        params.append('product_id', productIdFilter)
      }
      
      const response = await axios.get<OrdersResponse>(
        `${API_BASE_URL}/api/orders?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      
      setOrders(response.data.items)
      setTotalPages(response.data.total_pages)
      setTotal(response.data.total)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load orders')
      console.error('Error fetching orders:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setSearch(searchInput)
    setPage(1)
  }

  const handleClearSearch = () => {
    setSearchInput('')
    setSearch('')
    setPage(1)
  }

  const handleSort = (field: 'created_at' | 'total_amount' | 'status') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  const handleViewDetails = async (order: Order) => {
    setSelectedOrder(order)
    setShowDetailModal(true)
    setLoadingDetail(true)
    
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<OrderDetail>(
        `${API_BASE_URL}/api/orders/${order.id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      setOrderDetail(response.data)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load order details')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleUpdateStatus = (order: Order) => {
    setSelectedOrder(order)
    setShowStatusModal(true)
  }

  const handleStatusChange = async (newStatus: string) => {
    if (!selectedOrder) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/orders/${selectedOrder.id}/status`,
        { status: newStatus },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      setShowStatusModal(false)
      fetchOrders()
      // Refresh detail if modal is open
      if (showDetailModal && orderDetail) {
        handleViewDetails(selectedOrder)
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update order status')
    }
  }

  const handleExport = async () => {
    try {
      const token = localStorage.getItem('token')
      const params = new URLSearchParams()
      
      if (search) {
        params.append('search', search)
      }
      if (statusFilter) {
        params.append('status', statusFilter)
      }
      if (userIdFilter) {
        params.append('user_id', userIdFilter)
      }
      if (productIdFilter) {
        params.append('product_id', productIdFilter)
      }
      
      const response = await axios.get(
        `${API_BASE_URL}/api/orders/export?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          responseType: 'blob',
        }
      )
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `orders_export_${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to export orders')
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: 'VND',
    }).format(price)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('vi-VN')
  }

  const getStatusBadgeClass = (status: string) => {
    const statusMap: Record<string, string> = {
      pending: 'pending',
      paid: 'paid',
      processing: 'processing',
      delivered: 'delivered',
      cancelled: 'cancelled',
    }
    return statusMap[status] || 'pending'
  }

  const getStatusLabel = (status: string) => {
    const statusMap: Record<string, string> = {
      pending: 'Pending',
      paid: 'Paid',
      processing: 'Processing',
      delivered: 'Delivered',
      cancelled: 'Cancelled',
    }
    return statusMap[status] || status
  }

  if (loading && orders.length === 0) {
    return (
      <div className="orders-page">
        <div className="loading-state">
          <RefreshCw className="spinning" />
          <p>Loading orders...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="orders-page">
      <div className="page-header">
        <h1>Order Management</h1>
        <div className="header-actions">
          <Button onClick={handleExport} variant="secondary" size="small">
            <Download size={16} />
            <span>Export</span>
          </Button>
          <Button onClick={fetchOrders} variant="secondary" size="small">
            <RefreshCw size={16} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="filters-card">
        <div className="filters-content">
          <div className="filter-icon-wrapper">
            <Filter size={18} />
          </div>
          <div className="filter-group">
            <Input
              placeholder="Search by Order ID..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyPress={(e: KeyboardEvent<HTMLInputElement>) => {
                if (e.key === 'Enter') {
                  handleSearch()
                }
              }}
            />
          </div>
          {search && (
            <Button onClick={handleClearSearch} variant="secondary" size="small">
              <X size={14} />
            </Button>
          )}
          <div className="filter-group">
            <Select
              options={[
                { value: null, label: 'All Status' },
                { value: 'pending', label: 'Pending' },
                { value: 'paid', label: 'Paid' },
                { value: 'processing', label: 'Processing' },
                { value: 'delivered', label: 'Delivered' },
                { value: 'cancelled', label: 'Cancelled' },
              ]}
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value as string | null)
                setPage(1)
              }}
              placeholder="Filter by Status"
            />
          </div>
          <div className="filter-group">
            <Input
              placeholder="User ID..."
              value={userIdFilter}
              onChange={(e) => {
                setUserIdFilter(e.target.value)
                setPage(1)
              }}
              type="number"
            />
          </div>
          <div className="filter-group">
            <Input
              placeholder="Product ID..."
              value={productIdFilter}
              onChange={(e) => {
                setProductIdFilter(e.target.value)
                setPage(1)
              }}
            />
          </div>
        </div>
      </Card>

      {/* Error Banner */}
      {error && (
        <Card>
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        </Card>
      )}

      {/* Orders Table */}
      <Card>
        <div className="table-container">
          <table className="orders-table">
            <thead>
              <tr>
                <th>
                  <button
                    className="sort-button"
                    onClick={() => handleSort('created_at')}
                  >
                    Order ID
                    {sortBy === 'created_at' && (
                      <ArrowUpDown size={14} className={sortOrder === 'asc' ? 'asc' : 'desc'} />
                    )}
                  </button>
                </th>
                <th>User ID</th>
                <th>
                  <button
                    className="sort-button"
                    onClick={() => handleSort('status')}
                  >
                    Status
                    {sortBy === 'status' && (
                      <ArrowUpDown size={14} className={sortOrder === 'asc' ? 'asc' : 'desc'} />
                    )}
                  </button>
                </th>
                <th>
                  <button
                    className="sort-button"
                    onClick={() => handleSort('total_amount')}
                  >
                    Total Amount
                    {sortBy === 'total_amount' && (
                      <ArrowUpDown size={14} className={sortOrder === 'asc' ? 'asc' : 'desc'} />
                    )}
                  </button>
                </th>
                <th>Payment ID</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-state-cell">
                    <ShoppingCart size={48} />
                    <p>No orders found</p>
                  </td>
                </tr>
              ) : (
                orders.map((order) => (
                  <tr key={order.id}>
                    <td className="order-id">{order.id}</td>
                    <td>{order.user_id}</td>
                    <td>
                      <span className={`status-badge ${getStatusBadgeClass(order.status)}`}>
                        {getStatusLabel(order.status)}
                      </span>
                    </td>
                    <td className="amount">{formatPrice(order.total_amount)}</td>
                    <td className="payment-id">
                      {order.payment_transaction_id || '-'}
                    </td>
                    <td>{formatDate(order.created_at)}</td>
                    <td>
                      <div className="action-buttons">
                        <Button
                          onClick={() => handleViewDetails(order)}
                          variant="secondary"
                          size="small"
                          title="View Details"
                        >
                          <Eye size={14} />
                        </Button>
                        <Button
                          onClick={() => handleUpdateStatus(order)}
                          variant="secondary"
                          size="small"
                          title="Update Status"
                        >
                          <RefreshCw size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pagination">
            <Button
              onClick={() => setPage(page - 1)}
              disabled={page === 1}
              variant="secondary"
              size="small"
            >
              <ChevronLeft size={16} />
              <span>Previous</span>
            </Button>
            <span className="pagination-info">
              Page {page} of {totalPages} ({total} total)
            </span>
            <Button
              onClick={() => setPage(page + 1)}
              disabled={page >= totalPages}
              variant="secondary"
              size="small"
            >
              <span>Next</span>
              <ChevronRight size={16} />
            </Button>
          </div>
        )}
      </Card>

      {/* Order Detail Modal */}
      {showDetailModal && selectedOrder && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Info size={20} />
                Order Details - {selectedOrder.id}
              </h2>
              <button onClick={() => setShowDetailModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {loadingDetail ? (
                <div className="loading-state">
                  <RefreshCw className="spinning" />
                  <p>Loading order details...</p>
                </div>
              ) : orderDetail ? (
                <>
                  {/* Order Information */}
                  <div className="detail-section">
                    <h3>
                      <Info size={18} />
                      Order Information
                    </h3>
                    <div className="detail-grid">
                      <div className="detail-item">
                        <span className="label">Order ID:</span>
                        <span className="value">{orderDetail.id}</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">User ID:</span>
                        <span className="value">{orderDetail.user_id}</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Status:</span>
                        <span className={`status-badge ${getStatusBadgeClass(orderDetail.status)}`}>
                          {getStatusLabel(orderDetail.status)}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Total Amount:</span>
                        <span className="value amount">{formatPrice(orderDetail.total_amount)}</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Payment Transaction ID:</span>
                        <span className="value">{orderDetail.payment_transaction_id || '-'}</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Created At:</span>
                        <span className="value">{formatDate(orderDetail.created_at)}</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Updated At:</span>
                        <span className="value">{formatDate(orderDetail.updated_at)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Order Items */}
                  <div className="detail-section">
                    <h3>
                      <List size={18} />
                      Order Items
                    </h3>
                    {orderDetail.items.length === 0 ? (
                      <p className="empty-message">No items found</p>
                    ) : (
                      <table className="items-table">
                        <thead>
                          <tr>
                            <th>Product</th>
                            <th>Variation</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Subtotal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {orderDetail.items.map((item) => (
                            <tr key={item.id}>
                              <td>
                                {item.product ? (
                                  <>
                                    <strong>{item.product.name}</strong>
                                    {item.product.description && (
                                      <p className="item-description">{item.product.description}</p>
                                    )}
                                  </>
                                ) : (
                                  <span className="deleted-item">Product Deleted</span>
                                )}
                              </td>
                              <td>
                                {item.variation ? (
                                  <>
                                    <strong>{item.variation.name}</strong>
                                    <p className="item-price">{formatPrice(item.variation.price)}</p>
                                  </>
                                ) : (
                                  <span className="deleted-item">Variation Deleted</span>
                                )}
                              </td>
                              <td>{item.quantity}</td>
                              <td>{formatPrice(item.unit_price)}</td>
                              <td className="amount">{formatPrice(item.subtotal)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  {/* Supplier Orders */}
                  {orderDetail.supplier_orders.length > 0 && (
                    <div className="detail-section">
                      <h3>
                        <Truck size={18} />
                        Supplier Orders
                      </h3>
                      <table className="items-table">
                        <thead>
                          <tr>
                            <th>Supplier Order ID</th>
                            <th>Supplier ID</th>
                            <th>Status</th>
                            <th>Created At</th>
                            <th>Updated At</th>
                          </tr>
                        </thead>
                        <tbody>
                          {orderDetail.supplier_orders.map((so) => (
                            <tr key={so.id}>
                              <td>{so.id}</td>
                              <td>{so.supplier_id}</td>
                              <td>
                                <span className={`status-badge ${getStatusBadgeClass(so.status)}`}>
                                  {so.status}
                                </span>
                              </td>
                              <td>{formatDate(so.created_at)}</td>
                              <td>{formatDate(so.updated_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              ) : (
                <div className="empty-state">
                  <Package size={48} />
                  <p>Failed to load order details</p>
                </div>
              )}
            </div>
            <div className="modal-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => handleUpdateStatus(selectedOrder)}
              >
                <RefreshCw size={16} />
                <span>Update Status</span>
              </Button>
              <Button type="button" variant="secondary" onClick={() => setShowDetailModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Status Update Modal */}
      {showStatusModal && selectedOrder && (
        <div className="modal-overlay" onClick={() => setShowStatusModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <RefreshCw size={20} />
                Update Order Status
              </h2>
              <button onClick={() => setShowStatusModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Current Status: <strong>{getStatusLabel(selectedOrder.status)}</strong></p>
              <div className="status-options">
                {['pending', 'paid', 'processing', 'delivered', 'cancelled'].map((status) => (
                  <Button
                    key={status}
                    onClick={() => handleStatusChange(status)}
                    variant={selectedOrder.status === status ? 'primary' : 'secondary'}
                    size="small"
                    disabled={selectedOrder.status === status}
                  >
                    {getStatusLabel(status)}
                  </Button>
                ))}
              </div>
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowStatusModal(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
