/**
 * Variations Management page.
 * Premium Dark SaaS Design System.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Select } from '../components/Select'
import {
  Package,
  Plus,
  Edit,
  Trash2,
  RefreshCw,
  Filter,
  X,
  DollarSign,
  Box,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  CheckSquare,
  Square,
  Gift,
} from 'lucide-react'
import axios from 'axios'
import './VariationsPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface Variation {
  id: string
  name: string
  price: number
  stock: number
  is_active: boolean
  created_at: string
  updated_at: string
}

interface ProductGroup {
  product_id: string
  product_name: string
  variations: Variation[]
}

interface VariationsResponse {
  items: ProductGroup[]
}

interface Product {
  id: string
  name: string
}

interface BonusTier {
  id: string
  variation_id: string
  min_quantity: number
  bonus_quantity: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export function VariationsPage() {
  const [productGroups, setProductGroups] = useState<ProductGroup[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Filters
  const [productFilter, setProductFilter] = useState<string | null>(null)
  const [onlyActive, setOnlyActive] = useState<boolean | null>(null)
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(new Set())
  
  // Bulk selection
  const [selectedVariations, setSelectedVariations] = useState<Set<string>>(new Set())
  const [showBulkActions, setShowBulkActions] = useState(false)
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false)
  const [selectedVariation, setSelectedVariation] = useState<Variation | null>(null)
  
  // Form states
  const [formData, setFormData] = useState({
    id: '',
    product_id: '',
    name: '',
    price: '',
    is_active: true,
  })
  
  // Bonus modal states
  const [showBonusModal, setShowBonusModal] = useState(false)
  const [bonusVariation, setBonusVariation] = useState<{variation: Variation, productName: string} | null>(null)
  const [bonusTiers, setBonusTiers] = useState<BonusTier[]>([])
  const [bonusLoading, setBonusLoading] = useState(false)
  const [bonusForm, setBonusForm] = useState({
    min_quantity: '',
    bonus_quantity: '',
  })
  const [editingBonusTier, setEditingBonusTier] = useState<BonusTier | null>(null)

  useEffect(() => {
    fetchVariations()
    fetchProducts()
  }, [productFilter, onlyActive])

  const fetchVariations = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      const params = new URLSearchParams()
      
      if (productFilter) {
        params.append('product_id', productFilter)
      }
      if (onlyActive !== null) {
        params.append('only_active', onlyActive.toString())
      }
      
      const response = await axios.get<VariationsResponse>(
        `${API_BASE_URL}/api/variations?${params.toString()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      
      setProductGroups(response.data.items)
      // Auto-expand all products initially
      const allProductIds = new Set(response.data.items.map(p => p.product_id))
      setExpandedProducts(allProductIds)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load variations')
    } finally {
      setLoading(false)
    }
  }

  const fetchProducts = async () => {
    try {
      const token = localStorage.getItem('token')
      
      // Fetch all products using pagination
      const allProducts: Product[] = []
      let page = 1
      const perPage = 100 // Maximum allowed per page
      let hasMore = true
      
      while (hasMore) {
        const response = await axios.get<{ items: Product[], total: number, total_pages: number }>(
          `${API_BASE_URL}/api/products?page=${page}&per_page=${perPage}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        )
        
        allProducts.push(...response.data.items)
        
        if (page >= response.data.total_pages) {
          hasMore = false
        } else {
          page++
        }
      }
      
      setProducts(allProducts)
    } catch (err: any) {
      console.error('Failed to load products:', err)
    }
  }

  const toggleProductExpansion = (productId: string) => {
    const newExpanded = new Set(expandedProducts)
    if (newExpanded.has(productId)) {
      newExpanded.delete(productId)
    } else {
      newExpanded.add(productId)
    }
    setExpandedProducts(newExpanded)
  }

  const handleCreate = () => {
    setFormData({
      id: '',
      product_id: '',
      name: '',
      price: '',
      is_active: true,
    })
    setShowCreateModal(true)
  }

  const handleEdit = (variation: Variation, productId: string) => {
    setSelectedVariation(variation)
    setFormData({
      id: variation.id,
      product_id: productId,
      name: variation.name,
      price: variation.price.toString(),
      is_active: variation.is_active,
    })
    setShowEditModal(true)
  }

  const handleDelete = (variation: Variation) => {
    setSelectedVariation(variation)
    setShowDeleteModal(true)
  }

  const handleSelectVariation = (variationId: string) => {
    const newSelected = new Set(selectedVariations)
    if (newSelected.has(variationId)) {
      newSelected.delete(variationId)
    } else {
      newSelected.add(variationId)
    }
    setSelectedVariations(newSelected)
    setShowBulkActions(newSelected.size > 0)
  }

  const handleSelectAll = (variationIds: string[]) => {
    if (selectedVariations.size === variationIds.length) {
      setSelectedVariations(new Set())
      setShowBulkActions(false)
    } else {
      setSelectedVariations(new Set(variationIds))
      setShowBulkActions(true)
    }
  }

  const handleBulkActivate = async () => {
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/variations/bulk/activate`,
        { variation_ids: Array.from(selectedVariations) },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setSelectedVariations(new Set())
      setShowBulkActions(false)
      fetchVariations()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to activate variations')
    }
  }

  const handleBulkDeactivate = async () => {
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/variations/bulk/deactivate`,
        { variation_ids: Array.from(selectedVariations) },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setSelectedVariations(new Set())
      setShowBulkActions(false)
      fetchVariations()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to deactivate variations')
    }
  }

  const handleBulkDelete = () => {
    setShowBulkDeleteModal(true)
  }

  const handleConfirmBulkDelete = async () => {
    try {
      const token = localStorage.getItem('token')
      await axios.post(
        `${API_BASE_URL}/api/variations/bulk/delete`,
        { variation_ids: Array.from(selectedVariations) },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setSelectedVariations(new Set())
      setShowBulkActions(false)
      setShowBulkDeleteModal(false)
      fetchVariations()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete variations')
    }
  }


  const handleSubmitCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      const token = localStorage.getItem('token')
      await axios.post(
        `${API_BASE_URL}/api/variations`,
        {
          id: formData.id,
          product_id: formData.product_id,
          name: formData.name,
          price: parseInt(formData.price),
          is_active: formData.is_active,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setShowCreateModal(false)
      fetchVariations()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create variation')
    }
  }

  const handleSubmitEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedVariation) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/variations/${selectedVariation.id}`,
        {
          name: formData.name,
          price: parseInt(formData.price),
          is_active: formData.is_active,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setShowEditModal(false)
      fetchVariations()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update variation')
    }
  }

  const handleConfirmDelete = async () => {
    if (!selectedVariation) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.delete(
        `${API_BASE_URL}/api/variations/${selectedVariation.id}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setShowDeleteModal(false)
      fetchVariations()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete variation')
    }
  }


  const fetchLowStockVariations = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<VariationsResponse>(
        `${API_BASE_URL}/api/variations/low-stock?threshold=5`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setProductGroups(response.data.items)
      const allProductIds = new Set(response.data.items.map(p => p.product_id))
      setExpandedProducts(allProductIds)
    } catch (err: any) {
      alert('Failed to load low stock variations')
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: 'VND',
    }).format(price)
  }

  // Bonus management functions
  const handleOpenBonusModal = async (variation: Variation, productName: string) => {
    setBonusVariation({ variation, productName })
    setShowBonusModal(true)
    setBonusForm({ min_quantity: '', bonus_quantity: '' })
    setEditingBonusTier(null)
    await fetchBonusTiers(variation.id)
  }

  const fetchBonusTiers = async (variationId: string) => {
    try {
      setBonusLoading(true)
      const token = localStorage.getItem('token')
      const response = await axios.get<{ items: BonusTier[] }>(
        `${API_BASE_URL}/api/variations/${variationId}/bonus-tiers?only_active=false`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setBonusTiers(response.data.items)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load bonus tiers')
    } finally {
      setBonusLoading(false)
    }
  }

  const handleCreateBonusTier = async () => {
    if (!bonusVariation) return
    
    const minQty = parseInt(bonusForm.min_quantity)
    const bonusQty = parseInt(bonusForm.bonus_quantity)
    
    if (isNaN(minQty) || minQty < 1) {
      alert('Min quantity must be at least 1')
      return
    }
    if (isNaN(bonusQty) || bonusQty < 1) {
      alert('Bonus quantity must be at least 1')
      return
    }
    
    try {
      const token = localStorage.getItem('token')
      await axios.post(
        `${API_BASE_URL}/api/variations/${bonusVariation.variation.id}/bonus-tiers`,
        {
          min_quantity: minQty,
          bonus_quantity: bonusQty,
          is_active: true,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setBonusForm({ min_quantity: '', bonus_quantity: '' })
      await fetchBonusTiers(bonusVariation.variation.id)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create bonus tier')
    }
  }

  const handleUpdateBonusTier = async () => {
    if (!editingBonusTier || !bonusVariation) return
    
    const minQty = parseInt(bonusForm.min_quantity)
    const bonusQty = parseInt(bonusForm.bonus_quantity)
    
    if (isNaN(minQty) || minQty < 1) {
      alert('Min quantity must be at least 1')
      return
    }
    if (isNaN(bonusQty) || bonusQty < 1) {
      alert('Bonus quantity must be at least 1')
      return
    }
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/bonus-tiers/${editingBonusTier.id}`,
        {
          min_quantity: minQty,
          bonus_quantity: bonusQty,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setBonusForm({ min_quantity: '', bonus_quantity: '' })
      setEditingBonusTier(null)
      await fetchBonusTiers(bonusVariation.variation.id)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update bonus tier')
    }
  }

  const handleDeleteBonusTier = async (tierId: string) => {
    if (!bonusVariation) return
    
    if (!confirm('Are you sure you want to delete this bonus tier?')) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.delete(
        `${API_BASE_URL}/api/bonus-tiers/${tierId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      await fetchBonusTiers(bonusVariation.variation.id)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete bonus tier')
    }
  }

  const handleToggleBonusTierActive = async (tier: BonusTier) => {
    if (!bonusVariation) return
    
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/bonus-tiers/${tier.id}`,
        { is_active: !tier.is_active },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      await fetchBonusTiers(bonusVariation.variation.id)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update bonus tier')
    }
  }

  const handleEditBonusTier = (tier: BonusTier) => {
    setEditingBonusTier(tier)
    setBonusForm({
      min_quantity: tier.min_quantity.toString(),
      bonus_quantity: tier.bonus_quantity.toString(),
    })
  }

  const handleCancelEditBonusTier = () => {
    setEditingBonusTier(null)
    setBonusForm({ min_quantity: '', bonus_quantity: '' })
  }

  if (loading && productGroups.length === 0) {
    return (
      <div className="variations-page">
        <div className="loading-state">
          <RefreshCw className="spinning" />
          <p>Loading variations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="variations-page">
      <div className="page-header">
        <h1>Variation Management</h1>
        <div className="header-actions">
          <Button onClick={fetchLowStockVariations} variant="secondary" size="small">
            <AlertTriangle size={16} />
            <span>Low Stock</span>
          </Button>
          {showBulkActions && (
            <div className="bulk-actions">
              <Button onClick={handleBulkActivate} variant="secondary" size="small">
                <CheckCircle size={16} />
                <span>Activate ({selectedVariations.size})</span>
              </Button>
              <Button onClick={handleBulkDeactivate} variant="secondary" size="small">
                <XCircle size={16} />
                <span>Deactivate ({selectedVariations.size})</span>
              </Button>
              <Button onClick={handleBulkDelete} variant="secondary" size="small">
                <Trash2 size={16} />
                <span>Delete ({selectedVariations.size})</span>
              </Button>
              <Button onClick={() => { setSelectedVariations(new Set()); setShowBulkActions(false); }} variant="secondary" size="small">
                <X size={16} />
                <span>Clear</span>
              </Button>
            </div>
          )}
          <Button onClick={handleCreate}>
            <Plus size={18} />
            <span>Create Variation</span>
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
            <Select
              options={[
                { value: null, label: 'All Products' },
                ...products.map(p => ({ value: p.id, label: p.name })),
              ]}
              value={productFilter}
              onChange={(value) => {
                setProductFilter(value as string | null)
              }}
              placeholder="Filter by Product"
            />
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

      {/* Variations List */}
      {error && (
        <Card>
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        </Card>
      )}

      {productGroups.length === 0 ? (
        <Card>
          <div className="empty-state">
            <Package size={48} />
            <p>No variations found</p>
          </div>
        </Card>
      ) : (
        productGroups.map((group) => (
          <Card key={group.product_id} className="product-group-card">
            <div
              className="product-group-header"
              onClick={() => toggleProductExpansion(group.product_id)}
            >
              <div className="product-group-title">
                {expandedProducts.has(group.product_id) ? (
                  <ChevronDown size={20} />
                ) : (
                  <ChevronUp size={20} />
                )}
                <Package size={20} />
                <h2>{group.product_name}</h2>
                <span className="variation-count">({group.variations.length} variations)</span>
              </div>
            </div>
            
            {expandedProducts.has(group.product_id) && (
              <div className="variations-table-wrapper">
                <table className="variations-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>
                        <button
                          className="select-all-button"
                          onClick={() => handleSelectAll(group.variations.map(v => v.id))}
                          title="Select all"
                        >
                          {selectedVariations.size === group.variations.length && 
                           group.variations.every(v => selectedVariations.has(v.id)) ? (
                            <CheckSquare size={18} />
                          ) : (
                            <Square size={18} />
                          )}
                        </button>
                      </th>
                      <th>Name</th>
                      <th>Price</th>
                      <th>Stock</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.variations.map((variation) => (
                      <tr key={variation.id} className={selectedVariations.has(variation.id) ? 'selected' : ''}>
                        <td>
                          <button
                            className="select-variation-button"
                            onClick={() => handleSelectVariation(variation.id)}
                            title="Select variation"
                          >
                            {selectedVariations.has(variation.id) ? (
                              <CheckSquare size={18} />
                            ) : (
                              <Square size={18} />
                            )}
                          </button>
                        </td>
                        <td className="variation-name">{variation.name}</td>
                        <td className="variation-price">{formatPrice(variation.price)}</td>
                        <td>
                          <div className="stock-cell">
                            <Box size={16} />
                            <span className={variation.stock <= 5 ? 'low-stock' : ''}>
                              {variation.stock}
                            </span>
                            {variation.stock <= 5 && (
                              <AlertTriangle size={14} className="stock-alert-icon" />
                            )}
                          </div>
                        </td>
                        <td>
                          <span className={`status-badge ${variation.is_active ? 'active' : 'inactive'}`}>
                            {variation.is_active ? (
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
                        </td>
                        <td className="date-cell">
                          {new Date(variation.created_at).toLocaleDateString()}
                        </td>
                        <td>
                          <div className="action-buttons">
                            <Button
                              onClick={() => handleOpenBonusModal(variation, group.product_name)}
                              variant="secondary"
                              size="small"
                              title="Bonus Config"
                            >
                              <Gift size={14} />
                            </Button>
                            <Button
                              onClick={() => handleEdit(variation, group.product_id)}
                              variant="secondary"
                              size="small"
                              title="Edit"
                            >
                              <Edit size={14} />
                            </Button>
                            <Button
                              onClick={() => handleDelete(variation)}
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
            )}
          </Card>
        ))
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Plus size={20} />
                Create Variation
              </h2>
              <button onClick={() => setShowCreateModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmitCreate}>
              <div className="form-group">
                <label>
                  <Package size={16} />
                  Variation ID
                </label>
                <Input
                  value={formData.id}
                  onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                  placeholder="var_1"
                  required
                />
              </div>
              <div className="form-group">
                <label>
                  <Package size={16} />
                  Product
                </label>
                <Select
                  options={products.map(p => ({ value: p.id, label: p.name }))}
                  value={formData.product_id}
                  onChange={(value) => setFormData({ ...formData, product_id: value as string })}
                  placeholder="Select Product"
                />
              </div>
              <div className="form-group">
                <label>
                  <Package size={16} />
                  Name
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Pro 12M 1PCS"
                  required
                />
              </div>
              <div className="form-group">
                <label>
                  <DollarSign size={16} />
                  Price (VND)
                </label>
                <Input
                  type="number"
                  value={formData.price}
                  onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                  placeholder="100000"
                  required
                />
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
                <Button type="button" variant="secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit">Create</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Edit size={20} />
                Edit Variation
              </h2>
              <button onClick={() => setShowEditModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmitEdit}>
              <div className="form-group">
                <label>
                  <Package size={16} />
                  Name
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>
                  <DollarSign size={16} />
                  Price (VND)
                </label>
                <Input
                  type="number"
                  value={formData.price}
                  onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                  required
                />
              </div>
              {/* Stock is managed automatically based on pre-uploaded products; no manual editing needed here. */}
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
                <Button type="button" variant="secondary" onClick={() => setShowEditModal(false)}>
                  Cancel
                </Button>
                <Button type="submit">Update</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Trash2 size={20} />
                Delete Variation
              </h2>
              <button onClick={() => setShowDeleteModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete "{selectedVariation?.name}"?</p>
              <p className="delete-warning" style={{ marginTop: '12px', color: '#EF4444', fontSize: '14px' }}>
                This will permanently delete the variation. This action cannot be undone.
              </p>
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleConfirmDelete}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Delete Modal */}
      {showBulkDeleteModal && (
        <div className="modal-overlay" onClick={() => setShowBulkDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Trash2 size={20} />
                Delete Variations
              </h2>
              <button onClick={() => setShowBulkDeleteModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete {selectedVariations.size} variation(s)?</p>
              <p className="delete-warning" style={{ marginTop: '12px', color: '#EF4444', fontSize: '14px' }}>
                This will permanently delete the selected variations. This action cannot be undone.
              </p>
            </div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setShowBulkDeleteModal(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleConfirmBulkDelete}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bonus Configuration Modal */}
      {showBonusModal && bonusVariation && (
        <div className="modal-overlay" onClick={() => setShowBonusModal(false)}>
          <div className="modal-content bonus-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Gift size={20} />
                Bonus Configuration
              </h2>
              <button onClick={() => setShowBonusModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="bonus-variation-info">
                <strong>Product:</strong> {bonusVariation.productName}<br />
                <strong>Variation:</strong> {bonusVariation.variation.name}
              </p>
              
              {/* Add/Edit Bonus Form */}
              <div className="bonus-form">
                <h3>{editingBonusTier ? 'Edit Bonus Tier' : 'Add Bonus Tier'}</h3>
                <div className="bonus-form-row">
                  <div className="form-group">
                    <label>Min Quantity</label>
                    <Input
                      type="number"
                      value={bonusForm.min_quantity}
                      onChange={(e) => setBonusForm({ ...bonusForm, min_quantity: e.target.value })}
                      placeholder="e.g., 10"
                      min="1"
                    />
                  </div>
                  <div className="form-group">
                    <label>Bonus Quantity</label>
                    <Input
                      type="number"
                      value={bonusForm.bonus_quantity}
                      onChange={(e) => setBonusForm({ ...bonusForm, bonus_quantity: e.target.value })}
                      placeholder="e.g., 2"
                      min="1"
                    />
                  </div>
                  <div className="bonus-form-actions">
                    {editingBonusTier ? (
                      <>
                        <Button onClick={handleUpdateBonusTier} size="small">
                          Update
                        </Button>
                        <Button onClick={handleCancelEditBonusTier} variant="secondary" size="small">
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <Button onClick={handleCreateBonusTier} size="small">
                        <Plus size={14} />
                        Add
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Bonus Tiers List */}
              <div className="bonus-tiers-list">
                <h3>Existing Bonus Tiers</h3>
                {bonusLoading ? (
                  <p className="loading-text">Loading...</p>
                ) : bonusTiers.length === 0 ? (
                  <p className="empty-text">No bonus tiers configured for this variation.</p>
                ) : (
                  <table className="bonus-tiers-table">
                    <thead>
                      <tr>
                        <th>Min Qty</th>
                        <th>Bonus</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bonusTiers.map((tier) => (
                        <tr key={tier.id} className={!tier.is_active ? 'inactive-row' : ''}>
                          <td>{tier.min_quantity}</td>
                          <td>+{tier.bonus_quantity}</td>
                          <td>
                            <span className={`status-badge ${tier.is_active ? 'active' : 'inactive'}`}>
                              {tier.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td>
                            <div className="bonus-tier-actions">
                              <Button
                                onClick={() => handleToggleBonusTierActive(tier)}
                                variant="secondary"
                                size="small"
                                title={tier.is_active ? 'Deactivate' : 'Activate'}
                              >
                                {tier.is_active ? <XCircle size={14} /> : <CheckCircle size={14} />}
                              </Button>
                              <Button
                                onClick={() => handleEditBonusTier(tier)}
                                variant="secondary"
                                size="small"
                                title="Edit"
                              >
                                <Edit size={14} />
                              </Button>
                              <Button
                                onClick={() => handleDeleteBonusTier(tier.id)}
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
                )}
              </div>
            </div>
            <div className="modal-actions">
              <Button type="button" onClick={() => setShowBonusModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

