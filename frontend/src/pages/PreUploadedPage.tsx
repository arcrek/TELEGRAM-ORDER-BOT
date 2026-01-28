/**
 * Pre-uploaded Product Management page.
 * Premium Dark SaaS Design System.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Select } from '../components/Select'
import {
  Package,
  CheckCircle,
  XCircle,
  RefreshCw,
  Filter,
  Trash2,
} from 'lucide-react'
import axios from 'axios'
import './PreUploadedPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

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
  by_product: {
    [key: string]: {
      product_id: string
      product_name: string
      total: number
      used: number
      available: number
    }
  }
}

export function PreUploadedPage() {
  const [products, setProducts] = useState<PreUploadedProduct[]>([])
  const [statistics, setStatistics] = useState<Statistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [perPage] = useState(15)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  
  // Filters
  const [productFilter, setProductFilter] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<boolean | null>(null)
  
  // Available products for filters
  const [availableProducts, setAvailableProducts] = useState<Array<{id: string, name: string}>>([])
  
  // Delete modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<PreUploadedProduct | null>(null)

  // Bulk selection & delete state
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([])
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false)

  useEffect(() => {
    fetchData()
    fetchStatistics()
  }, [page, productFilter, statusFilter])

  const fetchData = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
      })
      
      if (productFilter) {
        params.append('product_id', productFilter)
      }
      if (statusFilter !== null) {
        params.append('is_used', statusFilter.toString())
      }
      
      const response = await axios.get(
        `${API_BASE_URL}/api/pre-uploaded-products?${params.toString()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      
      setProducts(response.data.items)
      setTotalPages(response.data.total_pages)
      setTotal(response.data.total)
      setSelectedProductIds([])
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load pre-uploaded products')
    } finally {
      setLoading(false)
    }
  }

  const fetchStatistics = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get(
        `${API_BASE_URL}/api/pre-uploaded-products/statistics`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setStatistics(response.data)
      
      // Extract products and variations for filters
      const productsList = Object.values(response.data.by_product || {}).map((p: any) => ({
        id: p.product_id,
        name: p.product_name,
      }))
      setAvailableProducts(productsList)
    } catch (err: any) {
      console.error('Failed to load statistics:', err)
    }
  }

  const handleMarkUsed = async (productId: string) => {
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/pre-uploaded-products/${productId}/mark-used`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      await fetchData()
      await fetchStatistics()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to mark product as sold')
    }
  }

  const handleMarkUnused = async (productId: string) => {
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/pre-uploaded-products/${productId}/mark-unused`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      await fetchData()
      await fetchStatistics()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to mark product as available')
    }
  }

  const handleDelete = (product: PreUploadedProduct) => {
    setSelectedProduct(product)
    setShowDeleteModal(true)
  }

  const handleToggleSelectAll = () => {
    if (selectedProductIds.length === products.length) {
      setSelectedProductIds([])
    } else {
      setSelectedProductIds(products.map((p) => p.id))
    }
  }

  const handleToggleSelectOne = (productId: string) => {
    setSelectedProductIds((prev) =>
      prev.includes(productId) ? prev.filter((id) => id !== productId) : [...prev, productId]
    )
  }

  const handleBulkDelete = () => {
    if (!selectedProductIds.length) return
    setShowBulkDeleteModal(true)
  }

  const handleConfirmDelete = async () => {
    if (!selectedProduct) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.delete(
        `${API_BASE_URL}/api/pre-uploaded-products/${selectedProduct.id}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setShowDeleteModal(false)
      setSelectedProductIds((prev) => prev.filter((id) => id !== selectedProduct.id))
      await fetchData()
      await fetchStatistics()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete product')
    }
  }

  if (loading && !products.length) {
    return (
      <div className="pre-uploaded-page">
        <div className="loading-state">
          <RefreshCw className="spinning" />
          <p>Loading pre-uploaded products...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="pre-uploaded-page">
      <div className="page-header">
        <h1>Pre-uploaded Products</h1>
        <p>Manage pre-uploaded product inventory</p>
      </div>

      {/* Statistics */}
      {statistics && (
        <div className="statistics-grid">
          <Card className="stat-card">
            <div className="stat-content">
              <div className="stat-icon total">
                <Package size={24} />
              </div>
              <div className="stat-info">
                <h3>Total</h3>
                <p className="stat-value">{statistics.total}</p>
              </div>
            </div>
          </Card>

          <Card className="stat-card">
            <div className="stat-content">
              <div className="stat-icon available">
                <CheckCircle size={24} />
              </div>
              <div className="stat-info">
                <h3>Available</h3>
                <p className="stat-value">{statistics.available}</p>
              </div>
            </div>
          </Card>

          <Card className="stat-card">
            <div className="stat-content">
              <div className="stat-icon sold">
                <XCircle size={24} />
              </div>
              <div className="stat-info">
                <h3>Sold</h3>
                <p className="stat-value">{statistics.used}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card className="filters-card">
        <div className="filters-content">
          <div className="filter-icon-wrapper">
            <Filter size={18} />
          </div>
          <div className="filter-group">
            <Select
              options={[
                { value: null, label: 'All Products' },
                ...availableProducts.map(p => ({ value: p.id, label: p.name })),
              ]}
              value={productFilter}
              onChange={(value) => {
                setProductFilter(value as string | null)
                setPage(1)
              }}
              placeholder="Filter by Product"
            />
          </div>
          <div className="filter-group">
            <Select
              options={[
                { value: null, label: 'All Status' },
                { value: false, label: 'Available' },
                { value: true, label: 'Sold' },
              ]}
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value as boolean | null)
                setPage(1)
              }}
              placeholder="Filter by Status"
            />
          </div>
        </div>
      </Card>

      {/* Products List */}
      <Card className="products-card">
        <div className="products-header">
          <h2>Products ({total})</h2>
          <div className="products-bulk-actions">
            <span className="selected-count">
              {selectedProductIds.length > 0 ? `${selectedProductIds.length} selected` : ''}
            </span>
            <Button
              onClick={handleBulkDelete}
              variant="secondary"
              size="small"
              disabled={selectedProductIds.length === 0}
              title="Delete selected products"
            >
              <Trash2 size={14} />
              Delete Selected
            </Button>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        {products.length === 0 ? (
          <div className="empty-state">
            <Package size={48} />
            <p>No pre-uploaded products found</p>
          </div>
        ) : (
          <>
            <div className="products-table">
              <table>
                <thead>
                  <tr>
                    <th className="select-column">
                      <input
                        type="checkbox"
                        className="select-checkbox"
                        checked={products.length > 0 && selectedProductIds.length === products.length}
                        onChange={handleToggleSelectAll}
                      />
                    </th>
                    <th>Product</th>
                    <th>Variation</th>
                    <th>Product Data</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td className="select-column">
                        <input
                          type="checkbox"
                          className="select-checkbox"
                          checked={selectedProductIds.includes(product.id)}
                          onChange={() => handleToggleSelectOne(product.id)}
                        />
                      </td>
                      <td>
                        <div className="product-info">
                          <strong>{product.product_name}</strong>
                          <span className="product-id">ID: {product.product_id}</span>
                        </div>
                      </td>
                      <td>
                        <div className="variation-info">
                          <span>{product.variation_name}</span>
                          <span className="variation-id">ID: {product.variation_id}</span>
                        </div>
                      </td>
                      <td>
                        <div className="product-data-cell">
                          <span className="product-data-text" title={product.product_data}>
                            {product.product_data}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`status-badge ${product.is_used ? 'sold' : 'available'}`}>
                          {product.is_used ? (
                            <>
                              <XCircle size={14} />
                              Sold
                            </>
                          ) : (
                            <>
                              <CheckCircle size={14} />
                              Available
                            </>
                          )}
                        </span>
                      </td>
                      <td className="date-cell">
                        {new Date(product.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <div className="action-buttons">
                          {product.is_used ? (
                            product.used_by_order_id ? null : (
                              <Button
                                onClick={() => handleMarkUnused(product.id)}
                                variant="secondary"
                                size="small"
                              >
                                <CheckCircle size={14} />
                                Mark Available
                              </Button>
                            )
                          ) : (
                            <Button
                              onClick={() => handleMarkUsed(product.id)}
                              variant="secondary"
                              size="small"
                            >
                              <XCircle size={14} />
                              Mark Sold
                            </Button>
                          )}
                          <Button
                            onClick={() => handleDelete(product)}
                            variant="secondary"
                            size="small"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="pagination">
                <Button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  variant="secondary"
                  size="small"
                >
                  Previous
                </Button>
                <span className="pagination-info">
                  Page {page} of {totalPages}
                </span>
                <Button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  variant="secondary"
                  size="small"
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </Card>

      {/* Delete Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Trash2 size={20} />
                Delete Pre-uploaded Product
              </h2>
              <button onClick={() => setShowDeleteModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete this pre-uploaded product?</p>
              {selectedProduct && (
                <div style={{ marginTop: '16px', padding: '12px', background: 'var(--bg-secondary, #141412)', borderRadius: '8px' }}>
                  <p style={{ margin: '4px 0', fontWeight: 600 }}>Product: {selectedProduct.product_name}</p>
                  <p style={{ margin: '4px 0' }}>Variation: {selectedProduct.variation_name}</p>
                  <p style={{ margin: '4px 0', fontSize: '12px', color: 'var(--text-muted, #8F8F8F)' }}>ID: {selectedProduct.id}</p>
                </div>
              )}
              <p className="delete-warning" style={{ marginTop: '16px', color: '#EF4444', fontSize: '14px' }}>
                This will permanently delete the product. This action cannot be undone.
              </p>
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleConfirmDelete} style={{ background: '#EF4444', borderColor: '#EF4444' }}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Delete Modal */}
      {showBulkDeleteModal && selectedProductIds.length > 0 && (
        <div className="modal-overlay" onClick={() => setShowBulkDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Trash2 size={20} />
                Delete Selected Pre-uploaded Products
              </h2>
              <button onClick={() => setShowBulkDeleteModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete{' '}
                <strong>{selectedProductIds.length}</strong> selected pre-uploaded products?
              </p>
              <p className="delete-warning" style={{ marginTop: '16px', color: '#EF4444', fontSize: '14px' }}>
                This will permanently delete the selected products. This action cannot be undone.
              </p>
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowBulkDeleteModal(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={async () => {
                  try {
                    const token = localStorage.getItem('token')
                    await axios.post(
                      `${API_BASE_URL}/api/pre-uploaded-products/bulk-delete`,
                      { ids: selectedProductIds },
                      {
                        headers: { Authorization: `Bearer ${token}` },
                      }
                    )
                    setShowBulkDeleteModal(false)
                    setSelectedProductIds([])
                    await fetchData()
                    await fetchStatistics()
                  } catch (err: any) {
                    setError(
                      err.response?.data?.detail || 'Failed to bulk delete pre-uploaded products'
                    )
                  }
                }}
                style={{ background: '#EF4444', borderColor: '#EF4444' }}
              >
                Delete Selected
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

