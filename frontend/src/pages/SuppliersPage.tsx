/**
 * Suppliers Management page.
 * Premium Dark SaaS Design System.
 * Note: Suppliers register and interact via Telegram bot only, not through dashboard.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Select } from '../components/Select'
import {
  Users,
  Info,
  CheckCircle,
  XCircle,
  History,
  BarChart3,
  RefreshCw,
  Filter,
  Eye,
  User,
  Phone,
  Calendar,
  DollarSign,
  Package,
  Clock,
  Link2,
  Plus,
  Trash2,
  Star,
} from 'lucide-react'
import axios from 'axios'
import './SuppliersPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface Supplier {
  id: string
  telegram_user_id: number
  name: string
  is_active: boolean
  created_at: string
}

interface SuppliersResponse {
  items: Supplier[]
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

interface SupplierOrderHistoryResponse {
  items: SupplierOrder[]
}

interface SupplierStatistics {
  supplier_id: string
  supplier_name: string
  total_orders: number
  pending_orders: number
  in_progress_orders: number
  delivered_orders: number
  cancelled_orders: number
  total_revenue: number
}

interface Product {
  id: string
  name: string
  description: string | null
  delivery_type: 'pre_uploaded' | 'supplier_based'
  is_active: boolean
}

interface AssignedProduct {
  assignment_id: string
  product_id: string
  product_name: string
  is_primary: boolean
  created_at: string
}

interface AssignedProductResponse {
  items: AssignedProduct[]
}

export function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Filters
  const [onlyActive, setOnlyActive] = useState<boolean | null>(null)
  
  // Modal states
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [showOrderHistoryModal, setShowOrderHistoryModal] = useState(false)
  const [showStatisticsModal, setShowStatisticsModal] = useState(false)
  const [showAssignmentModal, setShowAssignmentModal] = useState(false)
  const [showAssignProductModal, setShowAssignProductModal] = useState(false)
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null)
  const [orderHistory, setOrderHistory] = useState<SupplierOrder[]>([])
  const [statistics, setStatistics] = useState<SupplierStatistics | null>(null)
  const [assignedProducts, setAssignedProducts] = useState<AssignedProduct[]>([])
  const [allProducts, setAllProducts] = useState<Product[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loadingStatistics, setLoadingStatistics] = useState(false)
  const [loadingAssignments, setLoadingAssignments] = useState(false)
  const [loadingProducts, setLoadingProducts] = useState(false)

  useEffect(() => {
    fetchSuppliers()
  }, [onlyActive])

  const fetchSuppliers = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      const params = new URLSearchParams()
      
      if (onlyActive !== null) {
        params.append('only_active', onlyActive.toString())
      }
      
      const response = await axios.get<SuppliersResponse>(
        `${API_BASE_URL}/api/suppliers?${params.toString()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      
      setSuppliers(response.data.items)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load suppliers')
      console.error('Error fetching suppliers:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleViewDetails = (supplier: Supplier) => {
    setSelectedSupplier(supplier)
    setShowDetailModal(true)
  }

  const handleViewOrderHistory = async (supplier: Supplier) => {
    setSelectedSupplier(supplier)
    setShowOrderHistoryModal(true)
    setLoadingHistory(true)
    
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<SupplierOrderHistoryResponse>(
        `${API_BASE_URL}/api/suppliers/${supplier.id}/orders`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setOrderHistory(response.data.items)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load order history')
    } finally {
      setLoadingHistory(false)
    }
  }

  const handleViewStatistics = async (supplier: Supplier) => {
    setSelectedSupplier(supplier)
    setShowStatisticsModal(true)
    setLoadingStatistics(true)
    
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<SupplierStatistics>(
        `${API_BASE_URL}/api/suppliers/${supplier.id}/statistics`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setStatistics(response.data)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load statistics')
    } finally {
      setLoadingStatistics(false)
    }
  }

  const handleToggleStatus = async (supplier: Supplier) => {
    if (!confirm(`Are you sure you want to ${supplier.is_active ? 'deactivate' : 'activate'} ${supplier.name}?`)) {
      return
    }
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/suppliers/${supplier.id}/status`,
        { is_active: !supplier.is_active },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      fetchSuppliers()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update supplier status')
    }
  }

  const handleViewAssignments = async (supplier: Supplier) => {
    setSelectedSupplier(supplier)
    setShowAssignmentModal(true)
    setLoadingAssignments(true)
    
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<AssignedProductResponse>(
        `${API_BASE_URL}/api/suppliers/${supplier.id}/products`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setAssignedProducts(response.data.items)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load assigned products')
    } finally {
      setLoadingAssignments(false)
    }
  }

  const handleAssignProduct = async (supplier: Supplier) => {
    setSelectedSupplier(supplier)
    setShowAssignProductModal(true)
    setLoadingProducts(true)
    
    try {
      const token = localStorage.getItem('token')
      // Fetch all products
      const allProductsList: Product[] = []
      let page = 1
      const perPage = 100
      let hasMore = true
      
      while (hasMore) {
        const response = await axios.get<{ items: Product[], total: number, total_pages: number }>(
          `${API_BASE_URL}/api/products?page=${page}&per_page=${perPage}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        )
        
        allProductsList.push(...response.data.items)
        
        if (page >= response.data.total_pages) {
          hasMore = false
        } else {
          page++
        }
      }
      
      // Filter to only supplier_based products
      setAllProducts(allProductsList.filter(p => p.delivery_type === 'supplier_based' && p.is_active))
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load products')
    } finally {
      setLoadingProducts(false)
    }
  }

  const handleCreateAssignment = async (productId: string, isPrimary: boolean) => {
    if (!selectedSupplier) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.post(
        `${API_BASE_URL}/api/suppliers/assignments`,
        {
          product_id: productId,
          supplier_id: selectedSupplier.id,
          is_primary: isPrimary,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      alert('Product assigned successfully')
      setShowAssignProductModal(false)
      if (showAssignmentModal) {
        handleViewAssignments(selectedSupplier)
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to assign product')
    }
  }

  const handleDeleteAssignment = async (productId: string) => {
    if (!selectedSupplier) return
    if (!confirm('Are you sure you want to remove this product assignment?')) {
      return
    }
    
    try {
      const token = localStorage.getItem('token')
      await axios.delete(
        `${API_BASE_URL}/api/suppliers/assignments?product_id=${productId}&supplier_id=${selectedSupplier.id}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      alert('Assignment removed successfully')
      handleViewAssignments(selectedSupplier)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to remove assignment')
    }
  }

  const handleSetPrimary = async (productId: string) => {
    if (!selectedSupplier) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/suppliers/assignments`,
        {
          product_id: productId,
          supplier_id: selectedSupplier.id,
          is_primary: true,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      alert('Primary supplier updated')
      handleViewAssignments(selectedSupplier)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update primary supplier')
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

  if (loading && suppliers.length === 0) {
    return (
      <div className="suppliers-page">
        <div className="loading-state">
          <RefreshCw className="spinning" />
          <p>Loading suppliers...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="suppliers-page">
      <div className="page-header">
        <h1>Supplier Management</h1>
        <div className="header-actions">
          <Button onClick={fetchSuppliers} variant="secondary" size="small">
            <RefreshCw size={16} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <Card className="info-banner">
        <div className="info-content">
          <Info size={18} />
          <p>
            <strong>Note:</strong> Suppliers register and interact via Telegram bot only, not through dashboard.
            This page is read-only for viewing supplier information and managing status.
          </p>
        </div>
      </Card>

      {/* Filters */}
      <Card className="filters-card">
        <div className="filters-content">
          <div className="filter-icon-wrapper">
            <Filter size={18} />
          </div>
          <div className="filter-group">
            <Select
              options={[
                { value: null, label: 'All Status' },
                { value: true, label: 'Active' },
                { value: false, label: 'Inactive' },
              ]}
              value={onlyActive}
              onChange={(value) => {
                setOnlyActive(value as boolean | null)
              }}
              placeholder="Filter by Status"
            />
          </div>
        </div>
      </Card>

      {/* Suppliers List */}
      {error && (
        <Card>
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        </Card>
      )}

      {suppliers.length === 0 ? (
        <Card>
          <div className="empty-state">
            <Users size={48} />
            <p>No suppliers found</p>
          </div>
        </Card>
      ) : (
        <div className="suppliers-grid">
          {suppliers.map((supplier) => (
            <Card key={supplier.id} className="supplier-card">
              <div className="supplier-header">
                <div className="supplier-info">
                  <User size={20} />
                  <h3>{supplier.name}</h3>
                  <span className={`status-badge ${supplier.is_active ? 'active' : 'inactive'}`}>
                    {supplier.is_active ? (
                      <>
                        <CheckCircle size={14} />
                        Active
                      </>
                    ) : (
                      <>
                        <XCircle size={14} />
                        Inactive
                      </>
                    )}
                  </span>
                </div>
              </div>
              
              <div className="supplier-details">
                <div className="detail-item">
                  <Phone size={16} />
                  <span className="label">Telegram ID:</span>
                  <span className="value">{supplier.telegram_user_id}</span>
                </div>
                <div className="detail-item">
                  <Calendar size={16} />
                  <span className="label">Registered:</span>
                  <span className="value">{formatDate(supplier.created_at)}</span>
                </div>
              </div>
              
              <div className="supplier-actions">
                <Button
                  onClick={() => handleViewDetails(supplier)}
                  variant="secondary"
                  size="small"
                  title="View Details"
                >
                  <Eye size={14} />
                  <span>Details</span>
                </Button>
                <Button
                  onClick={() => handleViewOrderHistory(supplier)}
                  variant="secondary"
                  size="small"
                  title="Order History"
                >
                  <History size={14} />
                  <span>Orders</span>
                </Button>
                <Button
                  onClick={() => handleViewStatistics(supplier)}
                  variant="secondary"
                  size="small"
                  title="Statistics"
                >
                  <BarChart3 size={14} />
                  <span>Stats</span>
                </Button>
                <Button
                  onClick={() => handleViewAssignments(supplier)}
                  variant="secondary"
                  size="small"
                  title="Product Assignments"
                >
                  <Link2 size={14} />
                  <span>Products</span>
                </Button>
                <Button
                  onClick={() => handleToggleStatus(supplier)}
                  variant={supplier.is_active ? "secondary" : "primary"}
                  size="small"
                  title={supplier.is_active ? "Deactivate" : "Activate"}
                >
                  {supplier.is_active ? (
                    <>
                      <XCircle size={14} />
                      <span>Deactivate</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle size={14} />
                      <span>Activate</span>
                    </>
                  )}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedSupplier && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Info size={20} />
                Supplier Details
              </h2>
              <button onClick={() => setShowDetailModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="detail-section">
                <div className="detail-row">
                  <span className="label">Supplier ID:</span>
                  <span className="value">{selectedSupplier.id}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Name:</span>
                  <span className="value">{selectedSupplier.name}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Telegram User ID:</span>
                  <span className="value">{selectedSupplier.telegram_user_id}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Status:</span>
                  <span className={`status-badge ${selectedSupplier.is_active ? 'active' : 'inactive'}`}>
                    {selectedSupplier.is_active ? (
                      <>
                        <CheckCircle size={14} />
                        Active
                      </>
                    ) : (
                      <>
                        <XCircle size={14} />
                        Inactive
                      </>
                    )}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="label">Registered:</span>
                  <span className="value">{formatDate(selectedSupplier.created_at)}</span>
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowDetailModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Order History Modal */}
      {showOrderHistoryModal && selectedSupplier && (
        <div className="modal-overlay" onClick={() => setShowOrderHistoryModal(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <History size={20} />
                Order History - {selectedSupplier.name}
              </h2>
              <button onClick={() => setShowOrderHistoryModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {loadingHistory ? (
                <div className="loading-state">
                  <RefreshCw className="spinning" />
                  <p>Loading order history...</p>
                </div>
              ) : orderHistory.length === 0 ? (
                <div className="empty-state">
                  <Package size={48} />
                  <p>No orders found</p>
                </div>
              ) : (
                <table className="orders-table">
                  <thead>
                    <tr>
                      <th>Order ID</th>
                      <th>Status</th>
                      <th>Order Status</th>
                      <th>Amount</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orderHistory.map((order) => (
                      <tr key={order.supplier_order_id}>
                        <td>{order.order_id}</td>
                        <td>
                          <span className={`status-badge ${order.status.toLowerCase()}`}>
                            {order.status}
                          </span>
                        </td>
                        <td>
                          <span className={`status-badge ${order.order_status.toLowerCase()}`}>
                            {order.order_status}
                          </span>
                        </td>
                        <td>{formatPrice(order.total_amount)}</td>
                        <td>{formatDate(order.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowOrderHistoryModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Statistics Modal */}
      {showStatisticsModal && selectedSupplier && statistics && (
        <div className="modal-overlay" onClick={() => setShowStatisticsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <BarChart3 size={20} />
                Performance Statistics - {selectedSupplier.name}
              </h2>
              <button onClick={() => setShowStatisticsModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {loadingStatistics ? (
                <div className="loading-state">
                  <RefreshCw className="spinning" />
                  <p>Loading statistics...</p>
                </div>
              ) : (
                <div className="statistics-grid">
                  <div className="stat-card">
                    <Package size={24} />
                    <div className="stat-content">
                      <span className="stat-label">Total Orders</span>
                      <span className="stat-value">{statistics.total_orders}</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <Clock size={24} />
                    <div className="stat-content">
                      <span className="stat-label">Pending</span>
                      <span className="stat-value">{statistics.pending_orders}</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <RefreshCw size={24} />
                    <div className="stat-content">
                      <span className="stat-label">In Progress</span>
                      <span className="stat-value">{statistics.in_progress_orders}</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <CheckCircle size={24} />
                    <div className="stat-content">
                      <span className="stat-label">Delivered</span>
                      <span className="stat-value">{statistics.delivered_orders}</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <XCircle size={24} />
                    <div className="stat-content">
                      <span className="stat-label">Cancelled</span>
                      <span className="stat-value">{statistics.cancelled_orders}</span>
                    </div>
                  </div>
                  <div className="stat-card highlight">
                    <DollarSign size={24} />
                    <div className="stat-content">
                      <span className="stat-label">Total Revenue</span>
                      <span className="stat-value">{formatPrice(statistics.total_revenue)}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowStatisticsModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Product Assignments Modal */}
      {showAssignmentModal && selectedSupplier && (
        <div className="modal-overlay" onClick={() => setShowAssignmentModal(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Link2 size={20} />
                Product Assignments - {selectedSupplier.name}
              </h2>
              <button onClick={() => setShowAssignmentModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {loadingAssignments ? (
                <div className="loading-state">
                  <RefreshCw className="spinning" />
                  <p>Loading assignments...</p>
                </div>
              ) : (
                <>
                  <div className="modal-actions-top">
                    <Button
                      onClick={() => handleAssignProduct(selectedSupplier)}
                      variant="primary"
                      size="small"
                    >
                      <Plus size={14} />
                      <span>Assign Product</span>
                    </Button>
                  </div>
                  {assignedProducts.length === 0 ? (
                    <div className="empty-state">
                      <Package size={48} />
                      <p>No products assigned</p>
                    </div>
                  ) : (
                    <table className="assignments-table">
                      <thead>
                        <tr>
                          <th>Product Name</th>
                          <th>Primary</th>
                          <th>Assigned</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {assignedProducts.map((assignment) => (
                          <tr key={assignment.assignment_id}>
                            <td>{assignment.product_name}</td>
                            <td>
                              {assignment.is_primary ? (
                                <span className="status-badge active">
                                  <Star size={14} />
                                  Primary
                                </span>
                              ) : (
                                <span className="status-badge inactive">Secondary</span>
                              )}
                            </td>
                            <td>{formatDate(assignment.created_at)}</td>
                            <td>
                              <div className="action-buttons">
                                {!assignment.is_primary && (
                                  <Button
                                    onClick={() => handleSetPrimary(assignment.product_id)}
                                    variant="secondary"
                                    size="small"
                                    title="Set as Primary"
                                  >
                                    <Star size={12} />
                                  </Button>
                                )}
                                <Button
                                  onClick={() => handleDeleteAssignment(assignment.product_id)}
                                  variant="secondary"
                                  size="small"
                                  title="Remove"
                                >
                                  <Trash2 size={12} />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowAssignmentModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Product Modal */}
      {showAssignProductModal && selectedSupplier && (
        <div className="modal-overlay" onClick={() => setShowAssignProductModal(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Plus size={20} />
                Assign Product to {selectedSupplier.name}
              </h2>
              <button onClick={() => setShowAssignProductModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {loadingProducts ? (
                <div className="loading-state">
                  <RefreshCw className="spinning" />
                  <p>Loading products...</p>
                </div>
              ) : allProducts.length === 0 ? (
                <div className="empty-state">
                  <Package size={48} />
                  <p>No supplier-based products available</p>
                </div>
              ) : (
                <div className="products-list">
                  {allProducts
                    .filter(p => !assignedProducts.some(ap => ap.product_id === p.id))
                    .map((product) => (
                      <Card key={product.id} className="product-assignment-card">
                        <div className="product-info">
                          <h4>{product.name}</h4>
                          {product.description && (
                            <p className="product-description">{product.description}</p>
                          )}
                        </div>
                        <div className="assignment-actions">
                          <Button
                            onClick={() => handleCreateAssignment(product.id, true)}
                            variant="primary"
                            size="small"
                          >
                            <Star size={14} />
                            <span>Assign as Primary</span>
                          </Button>
                          <Button
                            onClick={() => handleCreateAssignment(product.id, false)}
                            variant="secondary"
                            size="small"
                          >
                            <Plus size={14} />
                            <span>Assign</span>
                          </Button>
                        </div>
                      </Card>
                    ))}
                  {allProducts.filter(p => !assignedProducts.some(ap => ap.product_id === p.id)).length === 0 && (
                    <div className="empty-state">
                      <Package size={48} />
                      <p>All available products are already assigned</p>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowAssignProductModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

