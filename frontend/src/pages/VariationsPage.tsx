import { useState, useEffect, useMemo, useCallback, useId } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Search, Plus, Edit, Trash2, RefreshCw, Gift, Tag, Package, AlertTriangle,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { Badge } from '../shared/components/Badge'
import { Modal } from '../shared/components/Modal'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Select } from '../shared/components/Select'
import { Switch } from '../shared/components/Switch'
import { Tooltip } from '../shared/components/Tooltip'
import { FormField } from '../shared/components/FormField'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './VariationsPage.css'

interface Variation {
  id: string
  name: string
  price: number
  stock: number
  is_active: boolean
  benefit_mode: string
  product_id?: string
  product_name?: string
  created_at: string
  updated_at: string
}

interface ProductGroup {
  product_id: string
  product_name: string
  variations: Variation[]
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
}

interface DiscountTier {
  id: string
  variation_id: string
  min_quantity: number
  discount_type: string
  discount_value: number
  is_active: boolean
}

const LOW_STOCK_THRESHOLD = 5

const BENEFIT_MODE_VARIANT: Record<string, 'success' | 'info' | 'neutral'> = {
  bonus: 'success',
  discount: 'info',
  both: 'success',
  none: 'neutral',
}

export function VariationsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()
  const formId = useId()

  // ── URL-synced filters ─────────────────────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSearch = searchParams.get('q') ?? ''
  const urlProductId = searchParams.get('product') ?? null
  const urlActive = searchParams.get('active') ?? null
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))

  const setParam = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === '') next.delete(k)
          else next.set(k, v)
        }
        return next
      }, { replace: true })
    },
    [setSearchParams],
  )

  const [searchInput, setSearchInput] = useState(urlSearch)
  useEffect(() => { setSearchInput(urlSearch) }, [urlSearch])

  // ── Data ───────────────────────────────────────────────────────────
  const [allVariations, setAllVariations] = useState<Variation[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [perPage, setPerPage] = useState(20)

  // ── Selection ──────────────────────────────────────────────────────
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())

  // ── Form modal ─────────────────────────────────────────────────────
  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Variation | null>(null)
  const [formData, setFormData] = useState({
    product_id: '',
    name: '',
    price: '',
    is_active: true,
    benefit_mode: 'both',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [formSaving, setFormSaving] = useState(false)

  // ── Bonus tier modal ───────────────────────────────────────────────
  const [bonusOpen, setBonusOpen] = useState(false)
  const [bonusVariation, setBonusVariation] = useState<Variation | null>(null)
  const [bonusTiers, setBonusTiers] = useState<BonusTier[]>([])
  const [bonusLoading, setBonusLoading] = useState(false)
  const [bonusForm, setBonusForm] = useState({ min_quantity: '', bonus_quantity: '' })
  const [editingBonus, setEditingBonus] = useState<BonusTier | null>(null)

  // ── Discount tier modal ────────────────────────────────────────────
  const [discountOpen, setDiscountOpen] = useState(false)
  const [discountVariation, setDiscountVariation] = useState<Variation | null>(null)
  const [discountTiers, setDiscountTiers] = useState<DiscountTier[]>([])
  const [discountLoading, setDiscountLoading] = useState(false)
  const [discountForm, setDiscountForm] = useState({
    min_quantity: '',
    discount_type: 'percentage',
    discount_value: '',
  })
  const [editingDiscount, setEditingDiscount] = useState<DiscountTier | null>(null)

  // ── Fetch variations ───────────────────────────────────────────────
  const fetchVariations = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (urlProductId) params.product_id = urlProductId
      if (urlActive !== null) params.only_active = urlActive

      const res = await apiClient.get<{ items: ProductGroup[] }>('/api/variations', { params })
      const flat: Variation[] = []
      for (const group of res.data.items) {
        for (const v of group.variations) {
          flat.push({ ...v, product_id: group.product_id, product_name: group.product_name })
        }
      }
      setAllVariations(flat)
    } catch (err) {
      setError(formatApiError(err, t('variations.loadError', 'Không thể tải phân loại')))
    } finally {
      setLoading(false)
    }
  }, [urlProductId, urlActive, t])

  const fetchProducts = useCallback(async () => {
    try {
      const res = await apiClient.get<{ items: Product[] }>('/api/products/', {
        params: { page: 1, per_page: 100 },
      })
      setProducts(res.data.items)
    } catch {
      // silent — products are used for the filter dropdown
    }
  }, [])

  useEffect(() => {
    fetchVariations()
    fetchProducts()
  }, [fetchVariations, fetchProducts])

  // ── Client-side search + pagination ───────────────────────────────
  const filtered = useMemo(() => {
    if (!urlSearch) return allVariations
    const q = urlSearch.toLowerCase()
    return allVariations.filter(v =>
      v.name.toLowerCase().includes(q) ||
      (v.product_name ?? '').toLowerCase().includes(q) ||
      v.id.toLowerCase().includes(q),
    )
  }, [allVariations, urlSearch])

  const total = filtered.length
  const paginated = useMemo(() => {
    const start = (urlPage - 1) * perPage
    return filtered.slice(start, start + perPage)
  }, [filtered, urlPage, perPage])

  // ── Toggle is_active optimistically ───────────────────────────────
  const handleToggleActive = async (v: Variation, checked: boolean) => {
    setAllVariations(prev => prev.map(x => x.id === v.id ? { ...x, is_active: checked } : x))
    try {
      await apiClient.put(`/api/variations/${v.id}`, {
        name: v.name,
        price: v.price,
        is_active: checked,
        benefit_mode: v.benefit_mode,
      })
    } catch (err) {
      setAllVariations(prev => prev.map(x => x.id === v.id ? { ...x, is_active: !checked } : x))
      toast.error(formatApiError(err, t('variations.toggleError', 'Không thể thay đổi trạng thái')))
    }
  }

  // ── Form open/save ─────────────────────────────────────────────────
  const handleCreate = () => {
    setEditTarget(null)
    setFormData({ product_id: urlProductId ?? '', name: '', price: '', is_active: true, benefit_mode: 'both' })
    setFormError(null)
    setFormOpen(true)
  }

  const handleEdit = (v: Variation) => {
    setEditTarget(v)
    setFormData({
      product_id: v.product_id ?? '',
      name: v.name,
      price: String(v.price),
      is_active: v.is_active,
      benefit_mode: v.benefit_mode ?? 'both',
    })
    setFormError(null)
    setFormOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) { setFormError(t('variations.nameRequired', 'Tên là bắt buộc')); return }
    const price = parseInt(formData.price)
    if (isNaN(price) || price < 0) { setFormError(t('variations.priceInvalid', 'Giá không hợp lệ')); return }
    setFormSaving(true)
    setFormError(null)
    try {
      if (editTarget) {
        await apiClient.put(`/api/variations/${editTarget.id}`, {
          name: formData.name,
          price,
          is_active: formData.is_active,
          benefit_mode: formData.benefit_mode,
        })
        toast.success(t('variations.updated', 'Đã cập nhật'))
      } else {
        await apiClient.post('/api/variations', {
          product_id: formData.product_id,
          name: formData.name,
          price,
          is_active: formData.is_active,
        })
        toast.success(t('variations.created', 'Đã tạo phân loại'))
      }
      setFormOpen(false)
      fetchVariations()
    } catch (err) {
      setFormError(formatApiError(err, t('variations.saveError', 'Không thể lưu')))
    } finally {
      setFormSaving(false)
    }
  }

  // ── Delete ─────────────────────────────────────────────────────────
  const handleDelete = async (v: Variation) => {
    const ok = await confirm({
      title: t('variations.deleteTitle', 'Xoá phân loại?'),
      description: `"${v.name}" ${t('variations.deleteDesc', 'sẽ bị xoá vĩnh viễn.')}`,
      confirmLabel: t('common.delete', 'Xoá'),
      variant: 'destructive',
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/variations/${v.id}`)
      toast.success(t('variations.deleted', 'Đã xoá'))
      fetchVariations()
    } catch (err) {
      toast.error(formatApiError(err, t('variations.deleteError', 'Không thể xoá')))
    }
  }

  // ── Bulk delete ────────────────────────────────────────────────────
  const handleBulkDelete = async () => {
    if (selectedKeys.size === 0) return
    const ok = await confirm({
      title: t('variations.bulkDeleteTitle', `Xoá ${selectedKeys.size} phân loại?`),
      description: t('variations.bulkDeleteDesc', 'Hành động này không thể hoàn tác.'),
      confirmLabel: t('common.delete', 'Xoá'),
      variant: 'destructive',
    })
    if (!ok) return
    try {
      await apiClient.post('/api/variations/bulk/delete', { variation_ids: Array.from(selectedKeys) })
      toast.success(t('variations.bulkDeleted', 'Đã xoá các phân loại đã chọn'))
      setSelectedKeys(new Set())
      fetchVariations()
    } catch (err) {
      toast.error(formatApiError(err, t('variations.bulkDeleteError', 'Không thể xoá')))
    }
  }

  // ── Bonus tiers ────────────────────────────────────────────────────
  const openBonusModal = async (v: Variation) => {
    setBonusVariation(v)
    setBonusOpen(true)
    setBonusForm({ min_quantity: '', bonus_quantity: '' })
    setEditingBonus(null)
    setBonusLoading(true)
    try {
      const res = await apiClient.get<{ items: BonusTier[] }>(
        `/api/variations/${v.id}/bonus-tiers?only_active=false`,
      )
      setBonusTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.bonusLoadError', 'Không thể tải mức thưởng')))
    } finally {
      setBonusLoading(false)
    }
  }

  const saveBonusTier = async () => {
    if (!bonusVariation) return
    const minQty = parseInt(bonusForm.min_quantity)
    const bonusQty = parseInt(bonusForm.bonus_quantity)
    if (isNaN(minQty) || minQty < 1 || isNaN(bonusQty) || bonusQty < 1) {
      toast.warning(t('variations.bonusInvalid', 'Số lượng không hợp lệ'))
      return
    }
    try {
      if (editingBonus) {
        await apiClient.put(`/api/bonus-tiers/${editingBonus.id}`, { min_quantity: minQty, bonus_quantity: bonusQty })
      } else {
        await apiClient.post(`/api/variations/${bonusVariation.id}/bonus-tiers`, {
          min_quantity: minQty, bonus_quantity: bonusQty, is_active: true,
        })
      }
      setBonusForm({ min_quantity: '', bonus_quantity: '' })
      setEditingBonus(null)
      const res = await apiClient.get<{ items: BonusTier[] }>(
        `/api/variations/${bonusVariation.id}/bonus-tiers?only_active=false`,
      )
      setBonusTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.bonusSaveError', 'Không thể lưu mức thưởng')))
    }
  }

  const deleteBonusTier = async (tierId: string) => {
    if (!bonusVariation) return
    const ok = await confirm({ title: t('variations.bonusDeleteTitle', 'Xoá mức thưởng?'), variant: 'destructive', confirmLabel: t('common.delete', 'Xoá') })
    if (!ok) return
    try {
      await apiClient.delete(`/api/bonus-tiers/${tierId}`)
      const res = await apiClient.get<{ items: BonusTier[] }>(`/api/variations/${bonusVariation.id}/bonus-tiers?only_active=false`)
      setBonusTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.bonusDeleteError', 'Không thể xoá')))
    }
  }

  const toggleBonusTierActive = async (tier: BonusTier) => {
    if (!bonusVariation) return
    try {
      await apiClient.put(`/api/bonus-tiers/${tier.id}`, { is_active: !tier.is_active })
      const res = await apiClient.get<{ items: BonusTier[] }>(`/api/variations/${bonusVariation.id}/bonus-tiers?only_active=false`)
      setBonusTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.bonusToggleError', 'Không thể cập nhật')))
    }
  }

  // ── Discount tiers ─────────────────────────────────────────────────
  const openDiscountModal = async (v: Variation) => {
    setDiscountVariation(v)
    setDiscountOpen(true)
    setDiscountForm({ min_quantity: '', discount_type: 'percentage', discount_value: '' })
    setEditingDiscount(null)
    setDiscountLoading(true)
    try {
      const res = await apiClient.get<{ items: DiscountTier[] }>(
        `/api/variations/${v.id}/discount-tiers?only_active=false`,
      )
      setDiscountTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.discountLoadError', 'Không thể tải chiết khấu')))
    } finally {
      setDiscountLoading(false)
    }
  }

  const saveDiscountTier = async () => {
    if (!discountVariation) return
    const minQty = parseInt(discountForm.min_quantity)
    const val = parseInt(discountForm.discount_value)
    if (isNaN(minQty) || minQty < 1 || isNaN(val) || val < 1) {
      toast.warning(t('variations.discountInvalid', 'Giá trị không hợp lệ'))
      return
    }
    if (discountForm.discount_type === 'percentage' && val > 100) {
      toast.warning(t('variations.discountPercentMax', 'Phần trăm tối đa là 100'))
      return
    }
    try {
      if (editingDiscount) {
        await apiClient.put(`/api/discount-tiers/${editingDiscount.id}`, {
          min_quantity: minQty, discount_type: discountForm.discount_type, discount_value: val,
        })
      } else {
        await apiClient.post(`/api/variations/${discountVariation.id}/discount-tiers`, {
          min_quantity: minQty, discount_type: discountForm.discount_type, discount_value: val, is_active: true,
        })
      }
      setDiscountForm({ min_quantity: '', discount_type: 'percentage', discount_value: '' })
      setEditingDiscount(null)
      const res = await apiClient.get<{ items: DiscountTier[] }>(`/api/variations/${discountVariation.id}/discount-tiers?only_active=false`)
      setDiscountTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.discountSaveError', 'Không thể lưu chiết khấu')))
    }
  }

  const deleteDiscountTier = async (tierId: string) => {
    if (!discountVariation) return
    const ok = await confirm({ title: t('variations.discountDeleteTitle', 'Xoá mức chiết khấu?'), variant: 'destructive', confirmLabel: t('common.delete', 'Xoá') })
    if (!ok) return
    try {
      await apiClient.delete(`/api/discount-tiers/${tierId}`)
      const res = await apiClient.get<{ items: DiscountTier[] }>(`/api/variations/${discountVariation.id}/discount-tiers?only_active=false`)
      setDiscountTiers(res.data.items)
    } catch (err) {
      toast.error(formatApiError(err, t('variations.discountDeleteError', 'Không thể xoá')))
    }
  }

  // ── Column definitions ─────────────────────────────────────────────
  const productOptions = useMemo(() =>
    products.map(p => ({ value: p.id, label: p.name })),
    [products],
  )

  const benefitModeOptions = useMemo(() => [
    { value: 'both', label: t('variations.mode.both', 'Thưởng + Giảm giá') },
    { value: 'bonus', label: t('variations.mode.bonus', 'Chỉ thưởng') },
    { value: 'discount', label: t('variations.mode.discount', 'Chỉ giảm giá') },
    { value: 'none', label: t('variations.mode.none', 'Không') },
  ], [t])

  const columns = useMemo<ColumnDef<Variation>[]>(() => [
    {
      id: 'product',
      header: t('variations.colProduct', 'Sản phẩm'),
      width: 180,
      cell: row => (
        <span className="variations-page__product-name">{row.product_name ?? '—'}</span>
      ),
    },
    {
      id: 'name',
      header: t('variations.colName', 'Tên phân loại'),
      cell: row => (
        <div className="variations-page__name-cell">
          <span>{row.name}</span>
          <span className="variations-page__id num">#{row.id.slice(0, 8)}</span>
        </div>
      ),
    },
    {
      id: 'price',
      header: t('variations.colPrice', 'Giá'),
      mono: true,
      align: 'right',
      sortable: false,
      width: 130,
      cell: row => fmt.currency(row.price),
    },
    {
      id: 'stock',
      header: t('variations.colStock', 'Tồn kho'),
      mono: true,
      align: 'right',
      width: 100,
      cell: row => (
        <span className="variations-page__stock">
          {row.stock}
          {row.stock <= LOW_STOCK_THRESHOLD && (
            <Tooltip content={t('variations.lowStock', 'Sắp hết hàng')}>
              <AlertTriangle size={12} className="variations-page__low-stock-icon" />
            </Tooltip>
          )}
        </span>
      ),
    },
    {
      id: 'benefit_mode',
      header: t('variations.colMode', 'Chế độ'),
      width: 140,
      cell: row => (
        <Badge variant={BENEFIT_MODE_VARIANT[row.benefit_mode] ?? 'neutral'} size="sm">
          {t(`variations.mode.${row.benefit_mode}`, row.benefit_mode)}
        </Badge>
      ),
    },
    {
      id: 'is_active',
      header: t('variations.colActive', 'Hoạt động'),
      width: 90,
      align: 'center',
      cell: row => (
        <span onClick={e => e.stopPropagation()}>
          <Switch
            checked={row.is_active}
            onChange={checked => handleToggleActive(row, checked)}
            aria-label={t('variations.toggleActive', 'Bật/tắt')}
          />
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 140,
      align: 'right',
      cell: row => (
        <div className="variations-page__actions">
          <Tooltip content={t('variations.bonusTiers', 'Mức thưởng')}>
            <IconButton
              icon={<Gift size={13} />}
              aria-label={t('variations.bonusTiers', 'Mức thưởng')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); openBonusModal(row) }}
            />
          </Tooltip>
          <Tooltip content={t('variations.discountTiers', 'Chiết khấu')}>
            <IconButton
              icon={<Tag size={13} />}
              aria-label={t('variations.discountTiers', 'Chiết khấu')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); openDiscountModal(row) }}
            />
          </Tooltip>
          <Tooltip content={t('common.edit', 'Sửa')}>
            <IconButton
              icon={<Edit size={13} />}
              aria-label={t('common.edit', 'Sửa')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleEdit(row) }}
            />
          </Tooltip>
          <Tooltip content={t('common.delete', 'Xoá')}>
            <IconButton
              icon={<Trash2 size={13} />}
              aria-label={t('common.delete', 'Xoá')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleDelete(row) }}
            />
          </Tooltip>
        </div>
      ),
    },
  ], [t, fmt])

  return (
    <div className="variations-page">
      <PageHeader
        title={t('nav.variations', 'Phân loại sản phẩm')}
        actions={
          <div className="variations-page__header-actions">
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={fetchVariations}
            />
            <Button
              variant="primary"
              size="sm"
              iconLeft={<Plus size={14} />}
              onClick={handleCreate}
            >
              {t('variations.create', 'Tạo phân loại')}
            </Button>
          </div>
        }
      />

      {/* ── Filters ──────────────────────────────────────────────── */}
      <div className="variations-page__filters">
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('variations.searchPlaceholder', 'Tìm phân loại...')}
          value={searchInput}
          clearable
          size="sm"
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') setParam({ q: searchInput, page: null }) }}
          onBlur={() => { if (searchInput !== urlSearch) setParam({ q: searchInput, page: null }) }}
          className="variations-page__search"
        />
        <Select
          options={productOptions}
          value={urlProductId}
          onChange={v => setParam({ product: v, page: null })}
          placeholder={t('variations.allProducts', 'Tất cả sản phẩm')}
          clearable
          searchable
          size="sm"
          className="variations-page__product-select"
        />
        <Select
          options={[
            { value: 'true', label: t('products.active', 'Hoạt động') },
            { value: 'false', label: t('products.inactive', 'Tắt') },
          ]}
          value={urlActive}
          onChange={v => setParam({ active: v, page: null })}
          placeholder={t('variations.allStatus', 'Tất cả trạng thái')}
          clearable
          size="sm"
          className="variations-page__active-select"
        />
      </div>

      {/* ── Bulk action bar ───────────────────────────────────────── */}
      {selectedKeys.size > 0 && (
        <div className="variations-page__bulk-bar">
          <span className="variations-page__bulk-count">
            {t('variations.selected', `Đã chọn ${selectedKeys.size}`)}
          </span>
          <Button variant="destructive" tone="subtle" size="sm" iconLeft={<Trash2 size={13} />} onClick={handleBulkDelete}>
            {t('variations.bulkDelete', 'Xoá đã chọn')}
          </Button>
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && (
        <div className="variations-page__error" role="alert">
          <span>{error}</span>
          <IconButton icon={<RefreshCw size={14} />} aria-label={t('common.retry', 'Thử lại')} size="sm" variant="ghost" onClick={fetchVariations} />
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────── */}
      <div className="variations-page__table-card">
        <Table<Variation>
          columns={columns}
          data={paginated}
          keyFn={row => row.id}
          loading={loading}
          skeletonRows={10}
          selectable
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          stickyHeader
          emptyIcon={<Package size={40} />}
          emptyTitle={t('variations.empty', 'Chưa có phân loại')}
          emptyDescription={t('variations.emptyDesc', 'Tạo phân loại đầu tiên cho sản phẩm')}
        />
        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
          className="variations-page__pagination"
        />
      </div>

      {/* ── Create / Edit Modal ───────────────────────────────────── */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editTarget ? t('variations.editTitle', 'Sửa phân loại') : t('variations.createTitle', 'Tạo phân loại')}
        footer={
          <div className="variations-page__modal-footer">
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setFormOpen(false)}>{t('common.cancel', 'Huỷ')}</Button>
            <Button variant="primary" size="sm" type="submit" form={formId} loading={formSaving}>
              {editTarget ? t('common.save', 'Lưu') : t('variations.create', 'Tạo')}
            </Button>
          </div>
        }
      >
        <form id={formId} onSubmit={handleSave} className="variations-page__form">
          {formError && <div className="variations-page__form-error" role="alert">{formError}</div>}

          {!editTarget && (
            <FormField label={t('variations.fieldProduct', 'Sản phẩm')} htmlFor={`${formId}-product`}>
              <Select
                options={productOptions}
                value={formData.product_id || null}
                onChange={v => setFormData(d => ({ ...d, product_id: v ?? '' }))}
                placeholder={t('variations.selectProduct', 'Chọn sản phẩm')}
                searchable
              />
            </FormField>
          )}

          <FormField label={t('variations.fieldName', 'Tên phân loại')} htmlFor={`${formId}-name`}>
            <Input
              id={`${formId}-name`}
              value={formData.name}
              onChange={e => setFormData(d => ({ ...d, name: e.target.value }))}
              placeholder={t('variations.namePlaceholder', 'Ví dụ: 100 follow')}
              required
            />
          </FormField>

          <FormField label={t('variations.fieldPrice', 'Giá (VND)')} htmlFor={`${formId}-price`}>
            <Input
              id={`${formId}-price`}
              type="number"
              min="0"
              value={formData.price}
              onChange={e => setFormData(d => ({ ...d, price: e.target.value }))}
              placeholder="0"
              required
            />
          </FormField>

          {editTarget && (
            <FormField label={t('variations.fieldMode', 'Chế độ ưu đãi')} htmlFor={`${formId}-mode`}>
              <Select
                options={benefitModeOptions}
                value={formData.benefit_mode}
                onChange={v => v && setFormData(d => ({ ...d, benefit_mode: v }))}
              />
            </FormField>
          )}

          <div className="variations-page__form-switch">
            <Switch
              checked={formData.is_active}
              onChange={checked => setFormData(d => ({ ...d, is_active: checked }))}
              label={t('variations.fieldActive', 'Kích hoạt')}
            />
          </div>
        </form>
      </Modal>

      {/* ── Bonus Tiers Modal ─────────────────────────────────────── */}
      <Modal
        open={bonusOpen}
        onClose={() => setBonusOpen(false)}
        size="lg"
        title={`${t('variations.bonusTiers', 'Mức thưởng')} — ${bonusVariation?.name ?? ''}`}
        footer={
          <Button variant="secondary" tone="ghost" size="sm" onClick={() => setBonusOpen(false)}>{t('common.close', 'Đóng')}</Button>
        }
      >
        <div className="variations-page__tier-body">
          {/* Add / Edit form */}
          <div className="variations-page__tier-form">
            <Input
              type="number"
              min="1"
              placeholder={t('variations.minQty', 'SL tối thiểu')}
              value={bonusForm.min_quantity}
              onChange={e => setBonusForm(f => ({ ...f, min_quantity: e.target.value }))}
              size="sm"
            />
            <Input
              type="number"
              min="1"
              placeholder={t('variations.bonusQty', 'SL thưởng')}
              value={bonusForm.bonus_quantity}
              onChange={e => setBonusForm(f => ({ ...f, bonus_quantity: e.target.value }))}
              size="sm"
            />
            <Button variant="primary" size="sm" onClick={saveBonusTier}>
              {editingBonus ? t('common.save', 'Lưu') : t('common.add', 'Thêm')}
            </Button>
            {editingBonus && (
              <Button variant="secondary" tone="ghost" size="sm" onClick={() => { setEditingBonus(null); setBonusForm({ min_quantity: '', bonus_quantity: '' }) }}>
                {t('common.cancel', 'Huỷ')}
              </Button>
            )}
          </div>

          {/* Tiers table */}
          {bonusLoading ? (
            <div className="variations-page__tier-skel">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} variant="line" height={36} />)}
            </div>
          ) : bonusTiers.length === 0 ? (
            <p className="variations-page__tier-empty">{t('variations.noBonusTiers', 'Chưa có mức thưởng')}</p>
          ) : (
            <div className="variations-page__tier-table-wrap">
              <table className="variations-page__tier-table">
                <thead>
                  <tr>
                    <th className="num">{t('variations.minQty', 'SL tối thiểu')}</th>
                    <th className="num">{t('variations.bonusQty', 'SL thưởng')}</th>
                    <th>{t('variations.colActive', 'Hoạt động')}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {bonusTiers.map(tier => (
                    <tr key={tier.id}>
                      <td className="num">{tier.min_quantity}</td>
                      <td className="num">{tier.bonus_quantity}</td>
                      <td>
                        <Switch
                          checked={tier.is_active}
                          onChange={() => toggleBonusTierActive(tier)}
                          aria-label={t('variations.toggleActive', 'Bật/tắt')}
                        />
                      </td>
                      <td>
                        <div className="variations-page__tier-actions">
                          <IconButton
                            icon={<Edit size={13} />}
                            aria-label={t('common.edit', 'Sửa')}
                            size="sm"
                            variant="ghost"
                            onClick={() => { setEditingBonus(tier); setBonusForm({ min_quantity: String(tier.min_quantity), bonus_quantity: String(tier.bonus_quantity) }) }}
                          />
                          <IconButton
                            icon={<Trash2 size={13} />}
                            aria-label={t('common.delete', 'Xoá')}
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteBonusTier(tier.id)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>

      {/* ── Discount Tiers Modal ──────────────────────────────────── */}
      <Modal
        open={discountOpen}
        onClose={() => setDiscountOpen(false)}
        size="lg"
        title={`${t('variations.discountTiers', 'Chiết khấu')} — ${discountVariation?.name ?? ''}`}
        footer={
          <Button variant="secondary" tone="ghost" size="sm" onClick={() => setDiscountOpen(false)}>{t('common.close', 'Đóng')}</Button>
        }
      >
        <div className="variations-page__tier-body">
          <div className="variations-page__tier-form variations-page__tier-form--discount">
            <Input
              type="number"
              min="1"
              placeholder={t('variations.minQty', 'SL tối thiểu')}
              value={discountForm.min_quantity}
              onChange={e => setDiscountForm(f => ({ ...f, min_quantity: e.target.value }))}
              size="sm"
            />
            <Select
              options={[
                { value: 'percentage', label: '%' },
                { value: 'fixed', label: 'VND' },
              ]}
              value={discountForm.discount_type}
              onChange={v => v && setDiscountForm(f => ({ ...f, discount_type: v }))}
              size="sm"
            />
            <Input
              type="number"
              min="1"
              placeholder={t('variations.discountValue', 'Giá trị')}
              value={discountForm.discount_value}
              onChange={e => setDiscountForm(f => ({ ...f, discount_value: e.target.value }))}
              size="sm"
            />
            <Button variant="primary" size="sm" onClick={saveDiscountTier}>
              {editingDiscount ? t('common.save', 'Lưu') : t('common.add', 'Thêm')}
            </Button>
            {editingDiscount && (
              <Button variant="secondary" tone="ghost" size="sm" onClick={() => { setEditingDiscount(null); setDiscountForm({ min_quantity: '', discount_type: 'percentage', discount_value: '' }) }}>
                {t('common.cancel', 'Huỷ')}
              </Button>
            )}
          </div>

          {discountLoading ? (
            <div className="variations-page__tier-skel">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} variant="line" height={36} />)}
            </div>
          ) : discountTiers.length === 0 ? (
            <p className="variations-page__tier-empty">{t('variations.noDiscountTiers', 'Chưa có mức chiết khấu')}</p>
          ) : (
            <div className="variations-page__tier-table-wrap">
              <table className="variations-page__tier-table">
                <thead>
                  <tr>
                    <th className="num">{t('variations.minQty', 'SL tối thiểu')}</th>
                    <th>{t('variations.discountType', 'Loại')}</th>
                    <th className="num">{t('variations.discountValue', 'Giá trị')}</th>
                    <th>{t('variations.colActive', 'HĐ')}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {discountTiers.map(tier => (
                    <tr key={tier.id}>
                      <td className="num">{tier.min_quantity}</td>
                      <td>
                        <Badge variant="info" size="sm">
                          {tier.discount_type === 'percentage' ? '%' : 'VND'}
                        </Badge>
                      </td>
                      <td className="num">
                        {tier.discount_type === 'percentage'
                          ? `${tier.discount_value}%`
                          : fmt.currency(tier.discount_value)}
                      </td>
                      <td>
                        <Switch
                          checked={tier.is_active}
                          onChange={() => {
                            apiClient.put(`/api/discount-tiers/${tier.id}`, { is_active: !tier.is_active })
                              .then(() => apiClient.get<{ items: DiscountTier[] }>(`/api/variations/${discountVariation!.id}/discount-tiers?only_active=false`))
                              .then(res => setDiscountTiers(res.data.items))
                              .catch(err => toast.error(formatApiError(err, '')))
                          }}
                          aria-label={t('variations.toggleActive', 'Bật/tắt')}
                        />
                      </td>
                      <td>
                        <div className="variations-page__tier-actions">
                          <IconButton
                            icon={<Edit size={13} />}
                            aria-label={t('common.edit', 'Sửa')}
                            size="sm"
                            variant="ghost"
                            onClick={() => { setEditingDiscount(tier); setDiscountForm({ min_quantity: String(tier.min_quantity), discount_type: tier.discount_type, discount_value: String(tier.discount_value) }) }}
                          />
                          <IconButton
                            icon={<Trash2 size={13} />}
                            aria-label={t('common.delete', 'Xoá')}
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteDiscountTier(tier.id)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
