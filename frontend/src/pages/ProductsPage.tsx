/**
 * Products page with product management UI.
 * Premium Dark SaaS Design System.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Select } from '../components/Select'
import {
  Search,
  Plus,
  Edit,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  Package,
  Filter,
  X,
} from 'lucide-react'
import axios from 'axios'
import './ProductsPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface Product {
  id: string
  name: string
  description: string | null
  delivery_type: 'pre_uploaded' | 'supplier_based'
  is_active: boolean
  created_at: string
  updated_at: string
}

interface ProductsResponse {
  items: Product[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [perPage] = useState(15)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  
  // Filters and search
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [onlyActive, setOnlyActive] = useState<boolean | null>(null)
  const [sortBy, setSortBy] = useState<'name' | 'created_at'>('name')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  
  // Form states
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    description: '',
    delivery_type: 'pre_uploaded' as 'pre_uploaded' | 'supplier_based',
    is_active: true,
  })

  useEffect(() => {
    fetchProducts()
  }, [page, search, onlyActive, sortBy, sortOrder])

  const fetchProducts = async () => {
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
      if (onlyActive !== null) {
        params.append('only_active', onlyActive.toString())
      }
      
      const response = await axios.get<ProductsResponse>(
        `${API_BASE_URL}/api/products/?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      
      setProducts(response.data.items)
      setTotalPages(response.data.total_pages)
      setTotal(response.data.total)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load products')
      console.error('Error fetching products:', err)
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

  const handleFilterActive = (value: boolean | null) => {
    setOnlyActive(value)
    setPage(1)
  }

  const handleSort = (field: 'name' | 'created_at') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
  }

  const handleCreate = () => {
    setFormData({
      id: '',
      name: '',
      description: '',
      delivery_type: 'pre_uploaded',
      is_active: true,
    })
    setShowCreateModal(true)
  }

  const handleEdit = (product: Product) => {
    setSelectedProduct(product)
    setFormData({
      id: product.id,
      name: product.name,
      description: product.description || '',
      delivery_type: product.delivery_type,
      is_active: product.is_active,
    })
    setShowEditModal(true)
  }

  const handleDelete = (product: Product) => {
    setSelectedProduct(product)
    setShowDeleteModal(true)
  }

  const handleView = (product: Product) => {
    setSelectedProduct(product)
    setShowDetailModal(true)
  }

  const handleSubmitCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const token = localStorage.getItem('token')
      await axios.post(
        `${API_BASE_URL}/api/products/`,
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      setShowCreateModal(false)
      fetchProducts()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create product')
    }
  }

  const handleSubmitEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedProduct) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/products/${selectedProduct.id}`,
        {
          name: formData.name,
          description: formData.description,
          delivery_type: formData.delivery_type,
          is_active: formData.is_active,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      setShowEditModal(false)
      fetchProducts()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update product')
    }
  }

  const handleConfirmDelete = async () => {
    if (!selectedProduct) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.delete(
        `${API_BASE_URL}/api/products/${selectedProduct.id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      setShowDeleteModal(false)
      fetchProducts()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete product')
    }
  }

  return (
    <div className="products-page">
      <div className="products-header">
        <h1>Product Management</h1>
        <Button onClick={handleCreate}>
          <Plus size={18} />
          <span>Create Product</span>
        </Button>
      </div>

      {/* Search and Filters */}
      <Card className="products-filters">
        <div className="filters-row">
          <div className="search-container">
            <div className="search-input-wrapper">
              <Input
                placeholder="Search products..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <div className="search-actions">
              {search && (
                <button onClick={handleClearSearch} className="clear-search">
                  <X size={16} />
                </button>
              )}
              <Button onClick={handleSearch} size="small">
                <Search size={16} />
              </Button>
            </div>
          </div>
          
          <div className="filter-group">
            <Filter size={18} />
            <Select
              options={[
                { value: null, label: 'All' },
                { value: true, label: 'Active' },
                { value: false, label: 'Inactive' },
              ]}
              value={onlyActive}
              onChange={(value) => handleFilterActive(value as boolean | null)}
              placeholder="Status"
            />
          </div>
        </div>
      </Card>

      {/* Products Table */}
      {loading ? (
        <Card>
          <div className="products-loading">Loading products...</div>
        </Card>
      ) : error ? (
        <Card>
          <div className="products-error">Error: {error}</div>
        </Card>
      ) : (
        <>
          <Card className="products-table-card">
            <table className="products-table">
              <thead>
                <tr>
                  <th>
                    <button
                      className="sort-button"
                      onClick={() => handleSort('name')}
                    >
                      Name
                      <ArrowUpDown size={14} />
                    </button>
                  </th>
                  <th>Description</th>
                  <th>Delivery Type</th>
                  <th>Status</th>
                  <th>
                    <button
                      className="sort-button"
                      onClick={() => handleSort('created_at')}
                    >
                      Created
                      <ArrowUpDown size={14} />
                    </button>
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      <Package size={48} />
                      <p>No products found</p>
                    </td>
                  </tr>
                ) : (
                  products.map((product) => (
                    <tr key={product.id}>
                      <td className="product-name">{product.name}</td>
                      <td className="product-description">
                        {product.description || '-'}
                      </td>
                      <td>
                        <span className={`delivery-badge ${product.delivery_type}`}>
                          {product.delivery_type === 'pre_uploaded' ? 'Pre-uploaded' : 'Supplier-based'}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${product.is_active ? 'active' : 'inactive'}`}>
                          {product.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="product-date">
                        {new Date(product.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <div className="action-buttons">
                          <button
                            className="action-button"
                            onClick={() => handleView(product)}
                            title="View"
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            className="action-button"
                            onClick={() => handleEdit(product)}
                            title="Edit"
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            className="action-button danger"
                            onClick={() => handleDelete(product)}
                            title="Delete"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <Card className="pagination-card">
              <div className="pagination">
                <button
                  className="pagination-button"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                >
                  <ChevronLeft size={18} />
                  Previous
                </button>
                <span className="pagination-info">
                  Page {page} of {totalPages} ({total} total)
                </span>
                <button
                  className="pagination-button"
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                >
                  Next
                  <ChevronRight size={18} />
                </button>
              </div>
            </Card>
          )}
        </>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <ProductModal
          title="Create Product"
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleSubmitCreate}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {/* Edit Modal */}
      {showEditModal && selectedProduct && (
        <ProductModal
          title="Edit Product"
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleSubmitEdit}
          onClose={() => setShowEditModal(false)}
          isEdit={true}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && selectedProduct && (
        <DeleteModal
          productName={selectedProduct.name}
          onConfirm={handleConfirmDelete}
          onClose={() => setShowDeleteModal(false)}
        />
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          onClose={() => setShowDetailModal(false)}
        />
      )}
    </div>
  )
}

interface ProductModalProps {
  title: string
  formData: {
    id: string
    name: string
    description: string
    delivery_type: 'pre_uploaded' | 'supplier_based'
    is_active: boolean
  }
  setFormData: React.Dispatch<React.SetStateAction<{
    id: string
    name: string
    description: string
    delivery_type: 'pre_uploaded' | 'supplier_based'
    is_active: boolean
  }>>
  onSubmit: (e: React.FormEvent) => void
  onClose: () => void
  isEdit?: boolean
}

function ProductModal({
  title,
  formData,
  setFormData,
  onSubmit,
  onClose,
  isEdit = false,
}: ProductModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <Card className="modal-content" onClick={(e) => e?.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <form onSubmit={onSubmit} className="product-form">
          {!isEdit && (
            <Input
              label="Product ID"
              value={formData.id}
              onChange={(e) => setFormData({ ...formData, id: e.target.value })}
              required
            />
          )}
          <Input
            label="Product Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <div className="form-group">
            <label>Description</label>
            <textarea
              className="form-textarea"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={4}
            />
          </div>
          <div className="form-group">
            <label>Delivery Type</label>
            <select
              className="form-select"
              value={formData.delivery_type}
              onChange={(e) => setFormData({ ...formData, delivery_type: e.target.value as 'pre_uploaded' | 'supplier_based' })}
            >
              <option value="pre_uploaded">Pre-uploaded</option>
              <option value="supplier_based">Supplier-based</option>
            </select>
          </div>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              <span>Active</span>
            </label>
          </div>
          <div className="modal-actions">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              {isEdit ? 'Update' : 'Create'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

interface DeleteModalProps {
  productName: string
  onConfirm: () => void
  onClose: () => void
}

function DeleteModal({ productName, onConfirm, onClose }: DeleteModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <Card className="modal-content delete-modal" onClick={(e) => e?.stopPropagation()}>
        <div className="modal-header">
          <h2>Delete Product</h2>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="delete-content">
          <Trash2 size={48} className="delete-icon" />
          <p>Are you sure you want to delete <strong>{productName}</strong>?</p>
          <p className="delete-warning">This will permanently delete the product. This action cannot be undone.</p>
        </div>
        <div className="modal-actions">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" variant="primary" onClick={onConfirm} className="danger-button">
            Delete
          </Button>
        </div>
      </Card>
    </div>
  )
}

interface ProductDetailModalProps {
  product: Product
  onClose: () => void
}

function ProductDetailModal({ product, onClose }: ProductDetailModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <Card className="modal-content detail-modal" onClick={(e) => e?.stopPropagation()}>
        <div className="modal-header">
          <h2>Product Details</h2>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="detail-content">
          <div className="detail-row">
            <span className="detail-label">ID:</span>
            <span className="detail-value">{product.id}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Name:</span>
            <span className="detail-value">{product.name}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Description:</span>
            <span className="detail-value">{product.description || '-'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Delivery Type:</span>
            <span className={`delivery-badge ${product.delivery_type}`}>
              {product.delivery_type === 'pre_uploaded' ? 'Pre-uploaded' : 'Supplier-based'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Status:</span>
            <span className={`status-badge ${product.is_active ? 'active' : 'inactive'}`}>
              {product.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Created:</span>
            <span className="detail-value">
              {new Date(product.created_at).toLocaleString()}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Updated:</span>
            <span className="detail-value">
              {new Date(product.updated_at).toLocaleString()}
            </span>
          </div>
        </div>
        <div className="modal-actions">
          <Button type="button" onClick={onClose}>
            Close
          </Button>
        </div>
      </Card>
    </div>
  )
}
