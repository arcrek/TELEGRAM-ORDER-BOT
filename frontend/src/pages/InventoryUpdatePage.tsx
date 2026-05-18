import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Boxes, RefreshCw, ChevronDown, ChevronRight,
  AlertTriangle, Clock, PackageSearch, Save,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { StatCard } from '../shared/components/StatCard'
import { Badge } from '../shared/components/Badge'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Select } from '../shared/components/Select'
import { Spinner } from '../shared/components/Spinner'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import './InventoryUpdatePage.css'

// ── Types ──────────────────────────────────────────────────────────────

type ThresholdUnit = 'days' | 'months' | 'years'

interface VariantStat {
  variation_id: string
  variation_name: string
  in_stock: number
  aging: number
  expiring_soon: number
  threshold_value: number | null
  threshold_unit: ThresholdUnit | null
}

interface ProductStat {
  product_id: string
  product_name: string
  variants: VariantStat[]
}

interface InventoryResponse {
  products: ProductStat[]
}

// Local threshold edit state for a single variant row
interface ThresholdDraft {
  value: string       // raw string from input
  unit: ThresholdUnit | null
  dirty: boolean      // differs from server state
  saving: boolean
}

// ── ThresholdCell ──────────────────────────────────────────────────────

interface ThresholdCellProps {
  draft: ThresholdDraft
  onValueChange: (v: string) => void
  onUnitChange: (u: ThresholdUnit | null) => void
  onSave: () => void
}

function ThresholdCell({ draft, onValueChange, onUnitChange, onSave }: ThresholdCellProps) {
  const { t } = useTranslation()

  const unitOptions = useMemo(() => [
    { value: 'days' as ThresholdUnit, label: t('inventory.unitDays', 'Ngày') },
    { value: 'months' as ThresholdUnit, label: t('inventory.unitMonths', 'Tháng') },
    { value: 'years' as ThresholdUnit, label: t('inventory.unitYears', 'Năm') },
  ], [t])

  const canSave = draft.dirty && !draft.saving && (
    // Either both are set (save threshold) or both empty (clear threshold)
    (draft.value !== '' && draft.unit !== null) ||
    (draft.value === '' && draft.unit === null)
  )

  return (
    <div className="inv-page__threshold-cell">
      <Input
        type="number"
        min={1}
        size="sm"
        value={draft.value}
        onChange={e => onValueChange(e.target.value)}
        placeholder={t('inventory.thresholdPlaceholder', 'Số')}
        className="inv-page__threshold-input"
        aria-label={t('inventory.colThreshold', 'Ngưỡng cảnh báo')}
      />
      <Select<ThresholdUnit | null>
        options={[
          { value: null, label: t('inventory.noThreshold', '—') },
          ...unitOptions,
        ] as { value: ThresholdUnit | null; label: string }[]}
        value={draft.unit}
        onChange={u => onUnitChange(u as ThresholdUnit | null)}
        size="sm"
        className="inv-page__unit-select"
        placeholder={t('inventory.noThreshold', '—')}
      />
      <Button
        size="sm"
        variant="primary"
        tone="solid"
        iconLeft={draft.saving ? undefined : <Save size={13} />}
        loading={draft.saving}
        disabled={!canSave}
        onClick={onSave}
        aria-label={t('inventory.save', 'Lưu')}
      >
        {draft.saving ? t('inventory.saving', 'Đang lưu...') : t('inventory.save', 'Lưu')}
      </Button>
    </div>
  )
}

// ── ProductCard ────────────────────────────────────────────────────────

interface ProductCardProps {
  product: ProductStat
  drafts: Record<string, ThresholdDraft>
  onDraftChange: (variationId: string, draft: Partial<ThresholdDraft>) => void
  onSave: (variationId: string) => void
}

function ProductCard({ product, drafts, onDraftChange, onSave }: ProductCardProps) {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)

  const totalStock = product.variants.reduce((s, v) => s + v.in_stock, 0)
  const totalAging = product.variants.reduce((s, v) => s + v.aging, 0)
  const totalExpiring = product.variants.reduce((s, v) => s + v.expiring_soon, 0)

  return (
    <div className="inv-page__product-card">
      {/* Card header */}
      <button
        type="button"
        className="inv-page__product-header"
        onClick={() => setCollapsed(c => !c)}
        aria-expanded={!collapsed}
      >
        <span className="inv-page__product-chevron">
          {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
        </span>
        <span className="inv-page__product-name">{product.product_name}</span>
        <span className="inv-page__product-badges">
          <span className="inv-page__stock-count">{totalStock} {t('inventory.totalStockUnit', 'mục')}</span>
          {totalAging > 0 && (
            <Badge variant="danger" size="sm">
              {t('inventory.agingBadge', 'Tồn lâu: {{count}}', { count: totalAging })}
            </Badge>
          )}
          {totalExpiring > 0 && (
            <Badge variant="warning" size="sm">
              {t('inventory.expiringBadge', 'Sắp hết hạn: {{count}}', { count: totalExpiring })}
            </Badge>
          )}
        </span>
      </button>

      {/* Variant table */}
      {!collapsed && (
        <div className="inv-page__variant-table-wrap">
          <table className="inv-page__variant-table">
            <thead>
              <tr>
                <th>{t('inventory.colVariant', 'Phân loại')}</th>
                <th className="inv-page__col-num">{t('inventory.colInStock', 'Tồn kho')}</th>
                <th className="inv-page__col-num">{t('inventory.colAging', 'Hàng tồn lâu')}</th>
                <th className="inv-page__col-num">{t('inventory.colExpiring', 'Hàng sắp hết hạn')}</th>
                <th>{t('inventory.colThreshold', 'Ngưỡng cảnh báo')}</th>
              </tr>
            </thead>
            <tbody>
              {product.variants.map(variant => {
                const draft = drafts[variant.variation_id] ?? {
                  value: variant.threshold_value !== null ? String(variant.threshold_value) : '',
                  unit: variant.threshold_unit,
                  dirty: false,
                  saving: false,
                }
                return (
                  <tr key={variant.variation_id}>
                    <td className="inv-page__variant-name">{variant.variation_name}</td>
                    <td className="inv-page__col-num">
                      <span className="inv-page__stock-num">{variant.in_stock}</span>
                    </td>
                    <td className="inv-page__col-num">
                      {variant.threshold_value !== null ? (
                        <span className={variant.aging > 0 ? 'inv-page__warning-aging' : ''}>
                          {variant.aging > 0 ? (
                            <span className="inv-page__warning-cell">
                              <AlertTriangle size={13} />
                              {variant.aging}
                            </span>
                          ) : (
                            <span className="inv-page__ok-zero">0</span>
                          )}
                        </span>
                      ) : (
                        <span className="inv-page__no-threshold">—</span>
                      )}
                    </td>
                    <td className="inv-page__col-num">
                      {variant.threshold_value !== null ? (
                        <span>
                          {variant.expiring_soon > 0 ? (
                            <span className="inv-page__warning-expiring inv-page__warning-cell">
                              <Clock size={13} />
                              {variant.expiring_soon}
                            </span>
                          ) : (
                            <span className="inv-page__ok-zero">0</span>
                          )}
                        </span>
                      ) : (
                        <span className="inv-page__no-threshold">—</span>
                      )}
                    </td>
                    <td>
                      <ThresholdCell
                        draft={draft}
                        onValueChange={v => onDraftChange(variant.variation_id, { value: v, dirty: true })}
                        onUnitChange={u => onDraftChange(variant.variation_id, { unit: u, dirty: true })}
                        onSave={() => onSave(variant.variation_id)}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── InventoryUpdatePage ────────────────────────────────────────────────

export function InventoryUpdatePage() {
  const { t } = useTranslation()
  const { toast } = useToast()

  const [products, setProducts] = useState<ProductStat[]>([])
  const [loading, setLoading] = useState(true)
  // Map: variation_id → ThresholdDraft
  const [drafts, setDrafts] = useState<Record<string, ThresholdDraft>>({})

  // ── Fetch ──────────────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get<InventoryResponse>('/api/pre-uploaded-products/inventory-stats')
      setProducts(res.data.products)
      // Initialise drafts from server state (preserving in-progress edits only for non-saving rows)
      setDrafts(prev => {
        const next: Record<string, ThresholdDraft> = {}
        for (const product of res.data.products) {
          for (const v of product.variants) {
            const existing = prev[v.variation_id]
            if (existing?.saving) {
              next[v.variation_id] = existing
            } else {
              next[v.variation_id] = {
                value: v.threshold_value !== null ? String(v.threshold_value) : '',
                unit: v.threshold_unit,
                dirty: false,
                saving: false,
              }
            }
          }
        }
        return next
      })
    } catch (err) {
      toast.error(formatApiError(err, t('inventory.loadError', 'Không thể tải dữ liệu kho hàng')))
    } finally {
      setLoading(false)
    }
  }, [t, toast])

  useEffect(() => { fetchData() }, [fetchData])

  // ── Draft management ───────────────────────────────────────────────

  const handleDraftChange = useCallback((variationId: string, patch: Partial<ThresholdDraft>) => {
    setDrafts(prev => ({
      ...prev,
      [variationId]: { ...(prev[variationId] ?? { value: '', unit: null, dirty: false, saving: false }), ...patch },
    }))
  }, [])

  // ── Save threshold ─────────────────────────────────────────────────

  const handleSave = useCallback(async (variationId: string) => {
    const draft = drafts[variationId]
    if (!draft) return

    const valueNum = draft.value !== '' ? parseInt(draft.value, 10) : null
    const unit = draft.unit

    // Validate: if value is set, unit must be set and vice versa
    if ((valueNum !== null) !== (unit !== null)) return
    if (valueNum !== null && (isNaN(valueNum) || valueNum <= 0)) {
      toast.error(t('inventory.saveError', 'Không thể lưu ngưỡng cảnh báo'))
      return
    }

    setDrafts(prev => ({ ...prev, [variationId]: { ...prev[variationId], saving: true } }))
    try {
      await apiClient.put(`/api/variations/${variationId}`, {
        warning_threshold_value: valueNum,
        warning_threshold_unit: unit,
      })
      toast.success(t('inventory.saveSuccess', 'Đã lưu ngưỡng cảnh báo'))
      // Refetch to get updated counts
      await fetchData()
    } catch (err) {
      toast.error(formatApiError(err, t('inventory.saveError', 'Không thể lưu ngưỡng cảnh báo')))
      setDrafts(prev => ({ ...prev, [variationId]: { ...prev[variationId], saving: false } }))
    }
  }, [drafts, fetchData, t, toast])

  // ── Summary stats ──────────────────────────────────────────────────

  const totals = useMemo(() => {
    let stock = 0, aging = 0, expiring = 0
    for (const p of products) {
      for (const v of p.variants) {
        stock += v.in_stock
        aging += v.aging
        expiring += v.expiring_soon
      }
    }
    return { stock, aging, expiring }
  }, [products])

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="inv-page">
      <PageHeader
        title={t('inventory.title', 'Cập nhật kho hàng')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('inventory.refresh', 'Làm mới')}
            variant="ghost"
            size="sm"
            onClick={fetchData}
          />
        }
      />

      {/* KPI row */}
      <div className="inv-page__kpi-row">
        <StatCard
          label={t('inventory.totalStock', 'Tổng tồn kho')}
          value={totals.stock}
          icon={<Boxes size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('inventory.totalAging', 'Tổng tồn lâu')}
          value={totals.aging}
          icon={<AlertTriangle size={16} />}
          loading={loading}
        />
        <StatCard
          label={t('inventory.totalExpiring', 'Tổng sắp hết hạn')}
          value={totals.expiring}
          icon={<Clock size={16} />}
          loading={loading}
        />
      </div>

      {/* Body */}
      {loading && products.length === 0 ? (
        <div className="inv-page__loading-center">
          <Spinner size="md" />
        </div>
      ) : products.length === 0 ? (
        <div className="inv-page__empty">
          <PackageSearch size={48} className="inv-page__empty-icon" />
          <p className="inv-page__empty-title">{t('inventory.emptyTitle', 'Không có sản phẩm pre-uploaded')}</p>
          <p className="inv-page__empty-desc">{t('inventory.emptyDesc', 'Chưa có sản phẩm nào có loại giao hàng pre-uploaded.')}</p>
        </div>
      ) : (
        <div className="inv-page__products">
          {products.map(product => (
            <ProductCard
              key={product.product_id}
              product={product}
              drafts={drafts}
              onDraftChange={handleDraftChange}
              onSave={handleSave}
            />
          ))}
        </div>
      )}
    </div>
  )
}
