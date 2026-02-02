/**
 * Bonus Summary page showing bonus tier configurations across all variations.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Gift, Package, RefreshCw, Search, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import axios from 'axios'
import './BonusSummaryPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface BonusTier {
  id: string
  variation_id: string
  min_quantity: number
  bonus_quantity: number
  is_active: boolean
  created_at: string
  updated_at: string
}

interface Variation {
  id: string
  name: string
  price: number
  stock: number
  product_id: string
  product_name?: string
  bonus_tiers: BonusTier[]
}

interface Product {
  id: string
  name: string
}

export function BonusSummaryPage() {
  const [loading, setLoading] = useState(true)
  const [variations, setVariations] = useState<Variation[]>([])
  const [products, setProducts] = useState<Record<string, Product>>({})
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(new Set())
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      
      // Fetch all products with pagination (max 100 per page)
      const productsMap: Record<string, Product> = {}
      let page = 1
      let hasMore = true
      
      while (hasMore) {
        const productsResponse = await axios.get(`${API_BASE_URL}/api/products`, {
          params: { page, per_page: 100 },
          headers: { Authorization: `Bearer ${token}` },
        })
        
        const productItems = productsResponse.data.items || []
        productItems.forEach((p: Product) => {
          productsMap[p.id] = p
        })
        
        // Check if there are more pages
        const total = productsResponse.data.total || 0
        const totalPages = productsResponse.data.pages || Math.ceil(total / 100)
        hasMore = page < totalPages
        page++
      }
      
      setProducts(productsMap)
      
      // Fetch all variations (returns grouped by product)
      const variationsResponse = await axios.get(`${API_BASE_URL}/api/variations`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      
      // Extract all variations from the grouped response
      const groupedData = variationsResponse.data.items || variationsResponse.data || []
      const allVariations: Array<{id: string, name: string, price: number, stock: number, product_id: string, product_name: string}> = []
      
      for (const group of groupedData) {
        const productId = group.product_id
        const productName = group.product_name || productsMap[productId]?.name || 'Unknown'
        
        for (const v of (group.variations || [])) {
          allVariations.push({
            ...v,
            product_id: productId,
            product_name: productName,
          })
        }
      }
      
      // Fetch bonus tiers for each variation that has them
      const variationsWithBonus: Variation[] = []
      
      for (const variation of allVariations) {
        try {
          const bonusResponse = await axios.get(
            `${API_BASE_URL}/api/variations/${variation.id}/bonus-tiers`,
            { headers: { Authorization: `Bearer ${token}` } }
          )
          
          if (bonusResponse.data && bonusResponse.data.length > 0) {
            variationsWithBonus.push({
              ...variation,
              product_name: variation.product_name || productsMap[variation.product_id]?.name || 'Unknown',
              bonus_tiers: bonusResponse.data,
            })
          }
        } catch {
          // No bonus tiers for this variation, skip
        }
      }
      
      setVariations(variationsWithBonus)
      setError(null)
      
      // Expand all products by default
      const productIds = new Set(variationsWithBonus.map(v => v.product_id))
      setExpandedProducts(productIds)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu bonus')
      console.error('Error fetching bonus data:', err)
    } finally {
      setLoading(false)
    }
  }

  const toggleProduct = (productId: string) => {
    setExpandedProducts(prev => {
      const newSet = new Set(prev)
      if (newSet.has(productId)) {
        newSet.delete(productId)
      } else {
        newSet.add(productId)
      }
      return newSet
    })
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: 'VND',
    }).format(amount)
  }

  // Filter variations
  const filteredVariations = variations.filter(v => {
    const matchesSearch = 
      v.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      v.product_name?.toLowerCase().includes(searchTerm.toLowerCase())
    
    if (!matchesSearch) return false
    
    if (filterActive === 'active') {
      return v.bonus_tiers.some(t => t.is_active)
    } else if (filterActive === 'inactive') {
      return v.bonus_tiers.every(t => !t.is_active)
    }
    
    return true
  })

  // Group by product
  const groupedByProduct: Record<string, Variation[]> = {}
  filteredVariations.forEach(v => {
    if (!groupedByProduct[v.product_id]) {
      groupedByProduct[v.product_id] = []
    }
    groupedByProduct[v.product_id].push(v)
  })

  // Calculate summary stats
  const totalVariationsWithBonus = variations.length
  const totalActiveTiers = variations.reduce(
    (sum, v) => sum + v.bonus_tiers.filter(t => t.is_active).length, 
    0
  )
  const totalInactiveTiers = variations.reduce(
    (sum, v) => sum + v.bonus_tiers.filter(t => !t.is_active).length, 
    0
  )
  const uniqueProducts = new Set(variations.map(v => v.product_id)).size

  if (loading) {
    return (
      <div className="bonus-summary-page">
        <div className="bonus-loading">
          <p>Đang tải dữ liệu bonus...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bonus-summary-page">
        <Card>
          <div className="bonus-error">
            <p>Lỗi: {error}</p>
            <Button onClick={fetchData} variant="primary" size="small">
              Thử lại
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="bonus-summary-page">
      <div className="bonus-header">
        <h1>
          <Gift size={28} />
          Tổng hợp Bonus
        </h1>
        <Button
          onClick={fetchData}
          variant="secondary"
          size="small"
          className="refresh-button"
          title="Tải lại dữ liệu"
        >
          <RefreshCw size={16} />
          <span>Làm mới</span>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="bonus-summary-cards">
        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon products">
              <Package size={24} />
            </div>
            <div className="summary-card-info">
              <h3>Sản phẩm có Bonus</h3>
              <p className="summary-value">{uniqueProducts}</p>
            </div>
          </div>
        </Card>

        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon variations">
              <Gift size={24} />
            </div>
            <div className="summary-card-info">
              <h3>Phân loại có Bonus</h3>
              <p className="summary-value">{totalVariationsWithBonus}</p>
            </div>
          </div>
        </Card>

        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon active">
              <Gift size={24} />
            </div>
            <div className="summary-card-info">
              <h3>Tầng Bonus hoạt động</h3>
              <p className="summary-value">{totalActiveTiers}</p>
            </div>
          </div>
        </Card>

        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon inactive">
              <Gift size={24} />
            </div>
            <div className="summary-card-info">
              <h3>Tầng Bonus tạm dừng</h3>
              <p className="summary-value">{totalInactiveTiers}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bonus-filters">
        <div className="filters-row">
          <div className="search-box">
            <Search size={18} />
            <Input
              type="text"
              placeholder="Tìm theo tên sản phẩm hoặc phân loại..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="filter-buttons">
            <Button
              variant={filterActive === 'all' ? 'primary' : 'outline'}
              size="small"
              onClick={() => setFilterActive('all')}
            >
              Tất cả
            </Button>
            <Button
              variant={filterActive === 'active' ? 'primary' : 'outline'}
              size="small"
              onClick={() => setFilterActive('active')}
            >
              Đang hoạt động
            </Button>
            <Button
              variant={filterActive === 'inactive' ? 'primary' : 'outline'}
              size="small"
              onClick={() => setFilterActive('inactive')}
            >
              Tạm dừng
            </Button>
          </div>
        </div>
      </Card>

      {/* Bonus List by Product */}
      {Object.keys(groupedByProduct).length === 0 ? (
        <Card className="bonus-empty">
          <Gift size={48} />
          <h3>Chưa có cấu hình Bonus</h3>
          <p>Vào trang Phân loại để thiết lập bonus cho từng loại sản phẩm.</p>
        </Card>
      ) : (
        <div className="bonus-products-list">
          {Object.entries(groupedByProduct).map(([productId, productVariations]) => (
            <Card key={productId} className="product-bonus-card">
              <div 
                className="product-header"
                onClick={() => toggleProduct(productId)}
              >
                <div className="product-info">
                  <Package size={20} />
                  <h2>{products[productId]?.name || 'Unknown Product'}</h2>
                  <span className="variation-count">
                    {productVariations.length} phân loại
                  </span>
                </div>
                <Button variant="outline" size="small">
                  {expandedProducts.has(productId) ? (
                    <ChevronUp size={20} />
                  ) : (
                    <ChevronDown size={20} />
                  )}
                </Button>
              </div>
              
              {expandedProducts.has(productId) && (
                <div className="product-variations">
                  {productVariations.map(variation => (
                    <div key={variation.id} className="variation-bonus-item">
                      <div className="variation-info">
                        <h3>{variation.name}</h3>
                        <div className="variation-details">
                          <span className="price">{formatCurrency(variation.price)}</span>
                          <span className="stock">Kho: {variation.stock}</span>
                        </div>
                      </div>
                      <div className="bonus-tiers-list">
                        {variation.bonus_tiers
                          .sort((a, b) => a.min_quantity - b.min_quantity)
                          .map(tier => (
                            <div 
                              key={tier.id} 
                              className={`bonus-tier-badge ${tier.is_active ? 'active' : 'inactive'}`}
                            >
                              <span className="tier-rule">
                                Mua {tier.min_quantity} → Tặng {tier.bonus_quantity}
                              </span>
                              <span className={`tier-status ${tier.is_active ? 'active' : 'inactive'}`}>
                                {tier.is_active ? '✓' : '✗'}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
