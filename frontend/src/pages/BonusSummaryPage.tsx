import { useState, useEffect, useMemo } from 'react'
import { Gift, Tag, Package, RefreshCw, Search, ChevronDown, ChevronUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { StatCard } from '../shared/components/StatCard'
import { Badge } from '../shared/components/Badge'
import { Input } from '../shared/components/Input'
import { Select } from '../shared/components/Select'
import { IconButton } from '../shared/components/IconButton'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './BonusSummaryPage.css'

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
  discount_type: string
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

type FilterType = 'all' | 'bonus' | 'discount'

export function BonusSummaryPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const fmt = useFormat()

  const [loading, setLoading] = useState(true)
  const [variations, setVariations] = useState<Variation[]>([])
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState<FilterType>('all')
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(new Set())

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [variationsResp, productsResp] = await Promise.all([
        apiClient.get<{ items: Array<{ product_id: string; product_name: string; variations: Array<{ id: string; name: string; price: number; stock: number; benefit_mode: string }> }> }>('/api/variations'),
        apiClient.get<{ items: Array<{ id: string; name: string }> }>('/api/products/', { params: { page: 1, per_page: 100 } }),
      ])

      const productNameMap: Record<string, string> = {}
      for (const p of productsResp.data.items) productNameMap[p.id] = p.name

      const allVariations = variationsResp.data.items.flatMap(group =>
        group.variations.map(v => ({
          ...v,
          product_id: group.product_id,
          product_name: group.product_name || productNameMap[group.product_id] || group.product_id,
          bonus_tiers: [] as BonusTier[],
          discount_tiers: [] as DiscountTier[],
        }))
      )

      if (allVariations.length === 0) {
        setVariations([])
        return
      }

      const [bonusResults, discountResults] = await Promise.all([
        Promise.all(allVariations.map(v =>
          apiClient.get<{ items: BonusTier[] }>(`/api/variations/${v.id}/bonus-tiers`, { params: { only_active: false } })
            .then(r => ({ id: v.id, tiers: r.data.items ?? [] }))
            .catch(() => ({ id: v.id, tiers: [] as BonusTier[] }))
        )),
        Promise.all(allVariations.map(v =>
          apiClient.get<{ items: DiscountTier[] }>(`/api/variations/${v.id}/discount-tiers`, { params: { only_active: false } })
            .then(r => ({ id: v.id, tiers: r.data.items ?? [] }))
            .catch(() => ({ id: v.id, tiers: [] as DiscountTier[] }))
        )),
      ])

      const bonusMap = Object.fromEntries(bonusResults.map(r => [r.id, r.tiers]))
      const discountMap = Object.fromEntries(discountResults.map(r => [r.id, r.tiers]))

      const withBenefits = allVariations
        .map(v => ({ ...v, bonus_tiers: bonusMap[v.id] ?? [], discount_tiers: discountMap[v.id] ?? [] }))
        .filter(v => v.bonus_tiers.length > 0 || v.discount_tiers.length > 0)

      setVariations(withBenefits)
      setExpandedProducts(new Set(withBenefits.map(v => v.product_id)))
    } catch (err) {
      setError(formatApiError(err, t('bonusSummary.loadError', 'Không thể tải dữ liệu')))
      toast.error(t('bonusSummary.loadError', 'Không thể tải dữ liệu'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  // ── Stats ──────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const uniqueProducts = new Set(variations.map(v => v.product_id)).size
    const withBonus = variations.filter(v => v.bonus_tiers.length > 0).length
    const withDiscount = variations.filter(v => v.discount_tiers.length > 0).length
    const activeBonusTiers = variations.reduce((s, v) => s + v.bonus_tiers.filter(t => t.is_active).length, 0)
    const activeDiscountTiers = variations.reduce((s, v) => s + v.discount_tiers.filter(t => t.is_active).length, 0)
    return { uniqueProducts, withBonus, withDiscount, activeBonusTiers, activeDiscountTiers }
  }, [variations])

  // ── Filtering + grouping ───────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return variations.filter(v => {
      if (q && !v.name.toLowerCase().includes(q) && !v.product_name.toLowerCase().includes(q)) return false
      if (filterType === 'bonus' && v.bonus_tiers.length === 0) return false
      if (filterType === 'discount' && v.discount_tiers.length === 0) return false
      return true
    })
  }, [variations, search, filterType])

  const grouped = useMemo(() => {
    const map = new Map<string, { productName: string; variations: Variation[] }>()
    for (const v of filtered) {
      if (!map.has(v.product_id)) map.set(v.product_id, { productName: v.product_name, variations: [] })
      map.get(v.product_id)!.variations.push(v)
    }
    return Array.from(map.entries()).map(([productId, { productName, variations }]) => ({
      productId, productName, variations,
    }))
  }, [filtered])

  const toggle = (productId: string) => {
    setExpandedProducts(prev => {
      const next = new Set(prev)
      next.has(productId) ? next.delete(productId) : next.add(productId)
      return next
    })
  }

  const filterTypeOptions = [
    { value: 'all' as FilterType, label: t('bonusSummary.filterAll', 'Tất cả') },
    { value: 'bonus' as FilterType, label: t('bonusSummary.filterBonus', 'Có thưởng') },
    { value: 'discount' as FilterType, label: t('bonusSummary.filterDiscount', 'Có chiết khấu') },
  ]

  return (
    <div className="bonus-summary-page">
      <PageHeader
        title={t('nav.bonusSummary', 'Tổng quan ưu đãi')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Làm mới')}
            variant="ghost"
            size="sm"
            onClick={fetchData}
          />
        }
      />

      {/* ── KPI row ──────────────────────────────────────────────── */}
      <div className="bonus-summary-page__kpi-row">
        <StatCard
          label={t('bonusSummary.products', 'Sản phẩm')}
          value={String(stats.uniqueProducts)}
          icon={<Package size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('bonusSummary.withBonus', 'Có mức thưởng')}
          value={String(stats.withBonus)}
          icon={<Gift size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('bonusSummary.withDiscount', 'Có chiết khấu')}
          value={String(stats.withDiscount)}
          icon={<Tag size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('bonusSummary.activeTiers', 'Mức đang hoạt động')}
          value={String(stats.activeBonusTiers + stats.activeDiscountTiers)}
          icon={<Gift size={16} />}
          loading={loading}
        />
      </div>

      {/* ── Filters ──────────────────────────────────────────────── */}
      <div className="bonus-summary-page__filters">
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('bonusSummary.search', 'Tìm phân loại...')}
          value={search}
          clearable
          size="sm"
          onChange={e => setSearch(e.target.value)}
          className="bonus-summary-page__search"
        />
        <Select<FilterType>
          options={filterTypeOptions}
          value={filterType}
          onChange={v => v && setFilterType(v)}
          size="sm"
          className="bonus-summary-page__type-select"
        />
      </div>

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && (
        <div className="bonus-summary-page__error" role="alert">{error}</div>
      )}

      {/* ── Content ───────────────────────────────────────────────── */}
      {loading ? (
        <div className="bonus-summary-page__skel">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bonus-summary-page__skel-group">
              <Skeleton variant="line" width="40%" height={16} />
              {Array.from({ length: 2 }).map((_, j) => (
                <Skeleton key={j} variant="rect" height={72} radius="8px" />
              ))}
            </div>
          ))}
        </div>
      ) : grouped.length === 0 ? (
        <div className="bonus-summary-page__empty">
          <Gift size={48} className="bonus-summary-page__empty-icon" />
          <p>{t('bonusSummary.empty', 'Không có ưu đãi nào')}</p>
        </div>
      ) : (
        <div className="bonus-summary-page__groups">
          {grouped.map(({ productId, productName, variations }) => {
            const isExpanded = expandedProducts.has(productId)
            return (
              <div key={productId} className="bonus-summary-page__group">
                <button
                  className="bonus-summary-page__group-header"
                  onClick={() => toggle(productId)}
                  aria-expanded={isExpanded}
                >
                  <Package size={14} />
                  <span className="bonus-summary-page__group-name">{productName}</span>
                  <Badge variant="neutral" size="sm">{variations.length}</Badge>
                  {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>

                {isExpanded && (
                  <div className="bonus-summary-page__variations">
                    {variations.map(v => (
                      <div key={v.id} className="bonus-summary-page__variation">
                        <div className="bonus-summary-page__variation-header">
                          <div className="bonus-summary-page__variation-info">
                            <span className="bonus-summary-page__variation-name">{v.name}</span>
                            <span className="bonus-summary-page__variation-price num">{fmt.currency(v.price)}</span>
                          </div>
                          <Badge
                            variant={v.benefit_mode === 'both' ? 'success' : v.benefit_mode === 'bonus' ? 'success' : 'info'}
                            size="sm"
                          >
                            {t(`variations.mode.${v.benefit_mode}`, v.benefit_mode)}
                          </Badge>
                        </div>

                        <div className="bonus-summary-page__tiers">
                          {v.bonus_tiers.length > 0 && (
                            <div className="bonus-summary-page__tier-group">
                              <span className="bonus-summary-page__tier-label">
                                <Gift size={11} />
                                {t('bonusSummary.bonusTiers', 'Mức thưởng')}
                              </span>
                              <div className="bonus-summary-page__tier-chips">
                                {v.bonus_tiers.map(tier => (
                                  <span
                                    key={tier.id}
                                    className={`bonus-summary-page__tier-chip ${tier.is_active ? 'bonus-summary-page__tier-chip--active' : 'bonus-summary-page__tier-chip--inactive'}`}
                                  >
                                    ≥{tier.min_quantity} → +{tier.bonus_quantity}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {v.discount_tiers.length > 0 && (
                            <div className="bonus-summary-page__tier-group">
                              <span className="bonus-summary-page__tier-label">
                                <Tag size={11} />
                                {t('bonusSummary.discountTiers', 'Chiết khấu')}
                              </span>
                              <div className="bonus-summary-page__tier-chips">
                                {v.discount_tiers.map(tier => (
                                  <span
                                    key={tier.id}
                                    className={`bonus-summary-page__tier-chip ${tier.is_active ? 'bonus-summary-page__tier-chip--active' : 'bonus-summary-page__tier-chip--inactive'}`}
                                  >
                                    ≥{tier.min_quantity} →{' '}
                                    {tier.discount_type === 'percentage'
                                      ? `-${tier.discount_value}%`
                                      : `-${fmt.currency(tier.discount_value)}`}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
