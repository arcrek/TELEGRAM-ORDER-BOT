/**
 * Benefits Summary page — shows bonus and discount tier configurations across all variations.
 * Fetches all tier data in parallel to minimize load time.
 */
import { useState, useEffect, useMemo } from 'react'
import { Card } from '../components/Card'
import { Gift, Tag, Package, RefreshCw, Search, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
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
}

interface DiscountTier {
  id: string
  variation_id: string
  min_quantity: number
  discount_type: string   // 'percentage' | 'fixed_price'
  discount_value: number
  is_active: boolean
}

interface Variation {
  id: string
  name: string
  price: number
  stock: number
  product_id: string
  product_name: string
  benefit_mode: string
  bonus_tiers: BonusTier[]
  discount_tiers: DiscountTier[]
}

export function BonusSummaryPage() {
  const [loading, setLoading] = useState(true)
  const [variations, setVariations] = useState<Variation[]>([])
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(new Set())
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [filterType, setFilterType] = useState<'all' | 'bonus' | 'discount'>('all')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const token = localStorage.getItem('token')
      const headers = { Authorization: `Bearer ${token}` }

      // ── Step 1: fetch products + variations concurrently ──────────────────
      const [variationsResp, firstProductsResp] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/variations`, { headers }),
        axios.get(`${API_BASE_URL}/api/products`, { params: { page: 1, per_page: 100 }, headers }),
      ])

      // Collect remaining product pages if any
      const totalPages: number = firstProductsResp.data.total_pages ?? firstProductsResp.data.pages ?? 1
      let productsMap: Record<string, string> = {}
      ;(firstProductsResp.data.items || []).forEach((p: { id: string; name: string }) => {
        productsMap[p.id] = p.name
      })

      if (totalPages > 1) {
        const extraPages = await Promise.all(
          Array.from({ length: totalPages - 1 }, (_, i) =>
            axios.get(`${API_BASE_URL}/api/products`, { params: { page: i + 2, per_page: 100 }, headers })
          )
        )
        extraPages.forEach(r => {
          ;(r.data.items || []).forEach((p: { id: string; name: string }) => {
            productsMap[p.id] = p.name
          })
        })
      }

      // Flatten variations from grouped response
      const groupedData: Array<{ product_id: string; product_name?: string; variations: Variation[] }> =
        variationsResp.data.items || []

      const allVariations: Array<Omit<Variation, 'bonus_tiers' | 'discount_tiers'>> = []
      for (const group of groupedData) {
        const productName = group.product_name || productsMap[group.product_id] || 'Unknown'
        for (const v of group.variations || []) {
          allVariations.push({
            ...v,
            product_id: group.product_id,
            product_name: productName,
            benefit_mode: v.benefit_mode || 'bonus',
          })
        }
      }

      if (allVariations.length === 0) {
        setVariations([])
        return
      }

      // ── Step 2: fetch all bonus + discount tiers in parallel ──────────────
      const [bonusResults, discountResults] = await Promise.all([
        Promise.all(
          allVariations.map(v =>
            axios
              .get(`${API_BASE_URL}/api/variations/${v.id}/bonus-tiers`, {
                params: { only_active: false },
                headers,
              })
              .then(r => ({ id: v.id, tiers: (r.data.items || []) as BonusTier[] }))
              .catch(() => ({ id: v.id, tiers: [] as BonusTier[] }))
          )
        ),
        Promise.all(
          allVariations.map(v =>
            axios
              .get(`${API_BASE_URL}/api/variations/${v.id}/discount-tiers`, {
                params: { only_active: false },
                headers,
              })
              .then(r => ({ id: v.id, tiers: (r.data.items || []) as DiscountTier[] }))
              .catch(() => ({ id: v.id, tiers: [] as DiscountTier[] }))
          )
        ),
      ])

      const bonusMap = Object.fromEntries(bonusResults.map(r => [r.id, r.tiers]))
      const discountMap = Object.fromEntries(discountResults.map(r => [r.id, r.tiers]))

      // Keep only variations that have at least one tier configured
      const withBenefits: Variation[] = allVariations
        .map(v => ({
          ...v,
          bonus_tiers: bonusMap[v.id] ?? [],
          discount_tiers: discountMap[v.id] ?? [],
        }))
        .filter(v => v.bonus_tiers.length > 0 || v.discount_tiers.length > 0)

      setVariations(withBenefits)

      // Expand all products by default
      setExpandedProducts(new Set(withBenefits.map(v => v.product_id)))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu')
    } finally {
      setLoading(false)
    }
  }

  const toggleProduct = (productId: string) => {
    setExpandedProducts(prev => {
      const next = new Set(prev)
      next.has(productId) ? next.delete(productId) : next.add(productId)
      return next
    })
  }

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount)

  const formatDiscount = (tier: DiscountTier) =>
    tier.discount_type === 'percentage'
      ? `${tier.discount_value}% off`
      : `${tier.discount_value.toLocaleString('vi-VN')}đ/cái`

  // ── Derived stats ─────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const uniqueProducts = new Set(variations.map(v => v.product_id)).size
    const withBonus = variations.filter(v => v.bonus_tiers.length > 0).length
    const withDiscount = variations.filter(v => v.discount_tiers.length > 0).length
    const activeBonusTiers = variations.reduce((s, v) => s + v.bonus_tiers.filter(t => t.is_active).length, 0)
    const activeDiscountTiers = variations.reduce((s, v) => s + v.discount_tiers.filter(t => t.is_active).length, 0)
    const inactiveTiers = variations.reduce(
      (s, v) =>
        s +
        v.bonus_tiers.filter(t => !t.is_active).length +
        v.discount_tiers.filter(t => !t.is_active).length,
      0
    )
    return { uniqueProducts, withBonus, withDiscount, activeBonusTiers, activeDiscountTiers, inactiveTiers }
  }, [variations])

  // ── Filtered + grouped ────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    return variations.filter(v => {
      const term = searchTerm.toLowerCase()
      if (term && !v.name.toLowerCase().includes(term) && !v.product_name.toLowerCase().includes(term))
        return false

      if (filterType === 'bonus' && v.bonus_tiers.length === 0) return false
      if (filterType === 'discount' && v.discount_tiers.length === 0) return false

      if (filterActive === 'active') {
        const hasActive =
          v.bonus_tiers.some(t => t.is_active) || v.discount_tiers.some(t => t.is_active)
        return hasActive
      }
      if (filterActive === 'inactive') {
        const allInactive =
          v.bonus_tiers.every(t => !t.is_active) && v.discount_tiers.every(t => !t.is_active)
        return allInactive
      }
      return true
    })
  }, [variations, searchTerm, filterType, filterActive])

  const groupedByProduct = useMemo(() => {
    const groups: Record<string, Variation[]> = {}
    filtered.forEach(v => {
      if (!groups[v.product_id]) groups[v.product_id] = []
      groups[v.product_id].push(v)
    })
    return groups
  }, [filtered])

  // ── Render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="bonus-summary-page">
        <div className="bonus-loading">
          <RefreshCw className="spinning" size={24} />
          <p>Đang tải dữ liệu ưu đãi...</p>
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
            <Button onClick={fetchData} variant="primary" size="small">Thử lại</Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="bonus-summary-page">
      <div className="bonus-header">
        <h1>
          <Sparkles size={28} />
          Tổng hợp Ưu đãi
        </h1>
        <Button onClick={fetchData} variant="secondary" size="small" title="Tải lại">
          <RefreshCw size={16} />
          <span>Làm mới</span>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="bonus-summary-cards">
        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon products"><Package size={24} /></div>
            <div className="summary-card-info">
              <h3>Sản phẩm có ưu đãi</h3>
              <p className="summary-value">{stats.uniqueProducts}</p>
            </div>
          </div>
        </Card>

        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon bonus"><Gift size={24} /></div>
            <div className="summary-card-info">
              <h3>Biến thể có Bonus</h3>
              <p className="summary-value">{stats.withBonus}</p>
              <p className="summary-sub">{stats.activeBonusTiers} tầng đang bật</p>
            </div>
          </div>
        </Card>

        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon discount"><Tag size={24} /></div>
            <div className="summary-card-info">
              <h3>Biến thể có Giảm giá</h3>
              <p className="summary-value">{stats.withDiscount}</p>
              <p className="summary-sub">{stats.activeDiscountTiers} tầng đang bật</p>
            </div>
          </div>
        </Card>

        <Card className="summary-card">
          <div className="summary-card-content">
            <div className="summary-card-icon inactive"><Sparkles size={24} /></div>
            <div className="summary-card-info">
              <h3>Tầng tạm dừng</h3>
              <p className="summary-value">{stats.inactiveTiers}</p>
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
            <Button variant={filterType === 'all' ? 'primary' : 'outline'} size="small" onClick={() => setFilterType('all')}>Tất cả</Button>
            <Button variant={filterType === 'bonus' ? 'primary' : 'outline'} size="small" onClick={() => setFilterType('bonus')}>
              <Gift size={13} /> Bonus
            </Button>
            <Button variant={filterType === 'discount' ? 'primary' : 'outline'} size="small" onClick={() => setFilterType('discount')}>
              <Tag size={13} /> Giảm giá
            </Button>
          </div>
          <div className="filter-buttons">
            <Button variant={filterActive === 'all' ? 'primary' : 'outline'} size="small" onClick={() => setFilterActive('all')}>Tất cả</Button>
            <Button variant={filterActive === 'active' ? 'primary' : 'outline'} size="small" onClick={() => setFilterActive('active')}>Đang bật</Button>
            <Button variant={filterActive === 'inactive' ? 'primary' : 'outline'} size="small" onClick={() => setFilterActive('inactive')}>Tạm dừng</Button>
          </div>
        </div>
      </Card>

      {/* Benefits List */}
      {Object.keys(groupedByProduct).length === 0 ? (
        <Card className="bonus-empty">
          <Sparkles size={48} />
          <h3>Chưa có cấu hình ưu đãi</h3>
          <p>Vào trang Phân loại để thiết lập bonus hoặc giảm giá cho từng loại sản phẩm.</p>
        </Card>
      ) : (
        <div className="bonus-products-list">
          {Object.entries(groupedByProduct).map(([productId, productVariations]) => (
            <Card key={productId} className="product-bonus-card">
              <div className="product-header" onClick={() => toggleProduct(productId)}>
                <div className="product-info">
                  <h2>{productVariations[0]?.product_name || 'Unknown Product'}</h2>
                  <span className="variation-count">{productVariations.length} phân loại</span>
                </div>
                <Button variant="outline" size="small">
                  {expandedProducts.has(productId) ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </Button>
              </div>

              {expandedProducts.has(productId) && (
                <div className="product-variations">
                  {productVariations.map(variation => (
                    <div key={variation.id} className="variation-bonus-item">
                      <div className="variation-info">
                        <div className="variation-name-row">
                          <h3>{variation.name}</h3>
                          <span className={`benefit-mode-badge mode-${variation.benefit_mode}`}>
                            {variation.benefit_mode === 'bonus'
                              ? '🎁 Bonus'
                              : variation.benefit_mode === 'discount'
                              ? '🏷️ Giảm giá'
                              : '✨ Cả hai'}
                          </span>
                        </div>
                        <div className="variation-details">
                          <span className="price">{formatCurrency(variation.price)}</span>
                          <span className="stock">Kho: {variation.stock}</span>
                        </div>
                      </div>

                      <div className="tiers-columns">
                        {/* Bonus tiers */}
                        {variation.bonus_tiers.length > 0 && (
                          <div className="tiers-group">
                            <span className="tiers-group-label">
                              <Gift size={12} /> Bonus
                            </span>
                            <div className="bonus-tiers-list">
                              {variation.bonus_tiers
                                .slice()
                                .sort((a, b) => a.min_quantity - b.min_quantity)
                                .map(tier => (
                                  <div
                                    key={tier.id}
                                    className={`bonus-tier-badge ${tier.is_active ? 'active' : 'inactive'}`}
                                  >
                                    <span className="tier-rule">
                                      Mua {tier.min_quantity} → +{tier.bonus_quantity}
                                    </span>
                                    <span className={`tier-status ${tier.is_active ? 'active' : 'inactive'}`}>
                                      {tier.is_active ? '✓' : '✗'}
                                    </span>
                                  </div>
                                ))}
                            </div>
                          </div>
                        )}

                        {/* Discount tiers */}
                        {variation.discount_tiers.length > 0 && (
                          <div className="tiers-group">
                            <span className="tiers-group-label">
                              <Tag size={12} /> Giảm giá
                            </span>
                            <div className="bonus-tiers-list">
                              {variation.discount_tiers
                                .slice()
                                .sort((a, b) => a.min_quantity - b.min_quantity)
                                .map(tier => (
                                  <div
                                    key={tier.id}
                                    className={`bonus-tier-badge discount-badge ${tier.is_active ? 'active' : 'inactive'}`}
                                  >
                                    <span className="tier-rule">
                                      Mua {tier.min_quantity}+ → {formatDiscount(tier)}
                                    </span>
                                    <span className={`tier-status ${tier.is_active ? 'active' : 'inactive'}`}>
                                      {tier.is_active ? '✓' : '✗'}
                                    </span>
                                  </div>
                                ))}
                            </div>
                          </div>
                        )}
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
