import { useState, useEffect, useMemo, useCallback, useId } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Plus, Edit, Trash2, Eye, Package, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef, type SortState } from '../shared/components/Table'
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
import { EmojiAutocompleteTextarea } from '../shared/components/EmojiAutocompleteTextarea'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'
import './ProductsPage.css'

type DeliveryType = 'pre_uploaded' | 'supplier_based' | 'upgrade' | 'virtual_order'

interface Product {
  id: string
  name: string
  description: string | null
  delivery_type: DeliveryType
  upgrade_request_text: string | null
  is_active: boolean
  variations_count?: number
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

type FormData = {
  name: string
  description: string
  delivery_type: DeliveryType
  upgrade_request_text: string
  is_active: boolean
}

const EMPTY_FORM: FormData = {
  name: '',
  description: '',
  delivery_type: 'pre_uploaded',
  upgrade_request_text: '',
  is_active: true,
}

const DELIVERY_TYPE_VARIANT: Record<DeliveryType, 'info' | 'success' | 'neutral'> = {
  pre_uploaded: 'info',
  supplier_based: 'success',
  upgrade: 'neutral',
  virtual_order: 'success',
}

export function ProductsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()
  const fmt = useFormat()
  const formId = useId()

  // ── URL-synced filters ─────────────────────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSearch = searchParams.get('q') ?? ''
  const urlActive = searchParams.get('active') ?? null
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))
  const urlSortId = searchParams.get('sort') ?? 'name'
  const urlSortDir = (searchParams.get('dir') ?? 'asc') as 'asc' | 'desc'

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

  // ── Data state ─────────────────────────────────────────────────────
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [perPage, setPerPage] = useState(15)

  // ── Modals ─────────────────────────────────────────────────────────
  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Product | null>(null)
  const [formData, setFormData] = useState<FormData>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [formSaving, setFormSaving] = useState(false)

  const [detailOpen, setDetailOpen] = useState(false)
  const [detailProduct, setDetailProduct] = useState<Product | null>(null)

  // ── Sort ───────────────────────────────────────────────────────────
  const sortState: SortState = { id: urlSortId, direction: urlSortDir }

  const handleSortChange = (sort: SortState) => {
    setParam({ sort: sort.id, dir: sort.direction ?? 'asc', page: null })
  }

  // ── Fetch ──────────────────────────────────────────────────────────
  const fetchProducts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {
        page: String(urlPage),
        per_page: String(perPage),
        sort_by: urlSortId,
        sort_order: urlSortDir,
      }
      if (urlSearch) params.search = urlSearch
      if (urlActive !== null) params.only_active = urlActive

      const res = await apiClient.get<ProductsResponse>('/api/products/', { params })
      setProducts(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      setError(formatApiError(err, t('products.loadError', 'Không thể tải sản phẩm')))
    } finally {
      setLoading(false)
    }
  }, [urlPage, perPage, urlSortId, urlSortDir, urlSearch, urlActive, t])

  useEffect(() => { fetchProducts() }, [fetchProducts])

  // ── Toggle is_active optimistically ───────────────────────────────
  const handleToggleActive = async (product: Product, checked: boolean) => {
    setProducts(prev =>
      prev.map(p => p.id === product.id ? { ...p, is_active: checked } : p),
    )
    try {
      await apiClient.put(`/api/products/${product.id}`, {
        name: product.name,
        description: product.description,
        delivery_type: product.delivery_type,
        upgrade_request_text: product.upgrade_request_text,
        is_active: checked,
      })
      toast.success(
        checked
          ? t('products.activated', 'Đã kích hoạt sản phẩm')
          : t('products.deactivated', 'Đã tắt sản phẩm'),
      )
    } catch (err) {
      // Rollback
      setProducts(prev =>
        prev.map(p => p.id === product.id ? { ...p, is_active: !checked } : p),
      )
      toast.error(formatApiError(err, t('products.toggleError', 'Không thể thay đổi trạng thái')))
    }
  }

  // ── Open create/edit form ──────────────────────────────────────────
  const handleCreate = () => {
    setEditTarget(null)
    setFormData(EMPTY_FORM)
    setFormError(null)
    setFormOpen(true)
  }

  const handleEdit = (product: Product) => {
    setEditTarget(product)
    setFormData({
      name: product.name,
      description: product.description ?? '',
      delivery_type: product.delivery_type,
      upgrade_request_text: product.upgrade_request_text ?? '',
      is_active: product.is_active,
    })
    setFormError(null)
    setFormOpen(true)
  }

  // ── Save form ──────────────────────────────────────────────────────
  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setFormError(t('products.nameRequired', 'Tên sản phẩm là bắt buộc'))
      return
    }
    setFormSaving(true)
    setFormError(null)
    const payload = {
      ...formData,
      description: formData.description || null,
      upgrade_request_text: ['upgrade', 'virtual_order'].includes(formData.delivery_type)
        ? formData.upgrade_request_text || null
        : null,
    }
    try {
      if (editTarget) {
        await apiClient.put(`/api/products/${editTarget.id}`, payload)
        toast.success(t('products.updated', 'Đã cập nhật sản phẩm'))
      } else {
        await apiClient.post('/api/products/', payload)
        toast.success(t('products.created', 'Đã tạo sản phẩm'))
      }
      setFormOpen(false)
      fetchProducts()
    } catch (err) {
      setFormError(formatApiError(err, t('products.saveError', 'Không thể lưu sản phẩm')))
    } finally {
      setFormSaving(false)
    }
  }

  // ── Delete ─────────────────────────────────────────────────────────
  const handleDelete = async (product: Product) => {
    const ok = await confirm({
      title: t('products.deleteTitle', 'Xoá sản phẩm?'),
      description: t('products.deleteDesc', `Sản phẩm "${product.name}" sẽ bị xoá vĩnh viễn.`),
      confirmLabel: t('common.delete', 'Xoá'),
      variant: 'destructive',
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/products/${product.id}`)
      toast.success(t('products.deleted', 'Đã xoá sản phẩm'))
      fetchProducts()
    } catch (err) {
      toast.error(formatApiError(err, t('products.deleteError', 'Không thể xoá sản phẩm')))
    }
  }

  // ── Active filter options ──────────────────────────────────────────
  const activeOptions = useMemo(() => [
    { value: 'true', label: t('products.active', 'Đang hoạt động') },
    { value: 'false', label: t('products.inactive', 'Tắt') },
  ], [t])

  const deliveryTypeOptions = useMemo(() => [
    { value: 'pre_uploaded' as DeliveryType, label: t('products.type.pre_uploaded', 'Kho hàng') },
    { value: 'supplier_based' as DeliveryType, label: t('products.type.supplier_based', 'Nhà cung cấp') },
    { value: 'upgrade' as DeliveryType, label: t('products.type.upgrade', 'Nâng cấp') },
    { value: 'virtual_order' as DeliveryType, label: t('products.type.virtual_order', 'Đơn ảo') },
  ], [t])

  // ── Column definitions ─────────────────────────────────────────────
  const columns = useMemo<ColumnDef<Product>[]>(() => [
    {
      id: 'name',
      header: t('products.colName', 'Sản phẩm'),
      sortable: true,
      cell: row => (
        <div className="products-page__name-cell">
          <span className="products-page__name">{row.name}</span>
          {row.description && (
            <span className="products-page__desc">{row.description}</span>
          )}
        </div>
      ),
    },
    {
      id: 'delivery_type',
      header: t('products.colType', 'Loại'),
      width: 160,
      cell: row => (
        <Badge variant={DELIVERY_TYPE_VARIANT[row.delivery_type]} size="sm">
          {t(`products.type.${row.delivery_type}`, row.delivery_type)}
        </Badge>
      ),
    },
    {
      id: 'variations_count',
      header: t('products.colVariations', 'Phân loại'),
      align: 'right',
      mono: true,
      width: 100,
      cell: row => row.variations_count ?? '—',
    },
    {
      id: 'is_active',
      header: t('products.colActive', 'Hoạt động'),
      width: 100,
      align: 'center',
      cell: row => (
        <span onClick={e => e.stopPropagation()}>
          <Switch
            checked={row.is_active}
            onChange={checked => handleToggleActive(row, checked)}
            aria-label={t('products.toggleActive', 'Bật/tắt sản phẩm')}
          />
        </span>
      ),
    },
    {
      id: 'created_at',
      header: t('products.colCreated', 'Tạo lúc'),
      sortable: true,
      width: 120,
      cell: row => (
        <Tooltip content={fmt.dateTime(row.created_at)} placement="top">
          <span className="products-page__rel-time">{fmt.relative(row.created_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 100,
      align: 'right',
      cell: row => (
        <div className="products-page__actions">
          <Tooltip content={t('common.view', 'Xem')}>
            <IconButton
              icon={<Eye size={14} />}
              aria-label={t('common.view', 'Xem')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); setDetailProduct(row); setDetailOpen(true) }}
            />
          </Tooltip>
          <Tooltip content={t('common.edit', 'Sửa')}>
            <IconButton
              icon={<Edit size={14} />}
              aria-label={t('common.edit', 'Sửa')}
              size="sm"
              variant="ghost"
              onClick={e => { e.stopPropagation(); handleEdit(row) }}
            />
          </Tooltip>
          <Tooltip content={t('common.delete', 'Xoá')}>
            <IconButton
              icon={<Trash2 size={14} />}
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
    <div className="products-page">
      <PageHeader
        title={t('nav.products', 'Sản phẩm')}
        actions={
          <div className="products-page__header-actions">
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={fetchProducts}
            />
            <Button
              variant="primary"
              size="sm"
              iconLeft={<Plus size={14} />}
              onClick={handleCreate}
            >
              {t('products.create', 'Tạo sản phẩm')}
            </Button>
          </div>
        }
      />

      {/* ── Filters ──────────────────────────────────────────────── */}
      <div className="products-page__filters">
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('products.searchPlaceholder', 'Tìm sản phẩm...')}
          value={searchInput}
          clearable
          size="sm"
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') setParam({ q: searchInput, page: null })
          }}
          onBlur={() => { if (searchInput !== urlSearch) setParam({ q: searchInput, page: null }) }}
          className="products-page__search"
        />
        <Select
          options={activeOptions}
          value={urlActive}
          onChange={v => setParam({ active: v, page: null })}
          placeholder={t('products.allStatus', 'Tất cả trạng thái')}
          clearable
          size="sm"
          className="products-page__active-select"
        />
      </div>

      {/* ── Error banner ─────────────────────────────────────────── */}
      {error && (
        <div className="products-page__error" role="alert">
          <span>{error}</span>
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.retry', 'Thử lại')}
            size="sm"
            variant="ghost"
            onClick={fetchProducts}
          />
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────── */}
      <div className="products-page__table-card">
        <Table<Product>
          columns={columns}
          data={products}
          keyFn={row => row.id}
          loading={loading}
          skeletonRows={perPage}
          sortState={sortState}
          onSortChange={handleSortChange}
          stickyHeader
          emptyIcon={<Package size={40} />}
          emptyTitle={t('products.empty', 'Chưa có sản phẩm')}
          emptyDescription={t('products.emptyDesc', 'Tạo sản phẩm đầu tiên để bắt đầu')}
          emptyAction={
            <Button variant="primary" size="sm" iconLeft={<Plus size={14} />} onClick={handleCreate}>
              {t('products.create', 'Tạo sản phẩm')}
            </Button>
          }
          onRowClick={row => { setDetailProduct(row); setDetailOpen(true) }}
        />

        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
          className="products-page__pagination"
        />
      </div>

      {/* ── Detail modal ─────────────────────────────────────────── */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        size="md"
        title={detailProduct?.name ?? t('products.detailTitle', 'Chi tiết sản phẩm')}
        footer={
          <div className="products-page__modal-footer">
            {detailProduct && (
              <>
                <Button
                  variant="secondary"
                  tone="subtle"
                  size="sm"
                  iconLeft={<Edit size={14} />}
                  onClick={() => { setDetailOpen(false); handleEdit(detailProduct) }}
                >
                  {t('common.edit', 'Sửa')}
                </Button>
                <Button
                  variant="destructive"
                  tone="subtle"
                  size="sm"
                  iconLeft={<Trash2 size={14} />}
                  onClick={() => { setDetailOpen(false); handleDelete(detailProduct) }}
                >
                  {t('common.delete', 'Xoá')}
                </Button>
              </>
            )}
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setDetailOpen(false)}>
              {t('common.close', 'Đóng')}
            </Button>
          </div>
        }
      >
        {detailProduct && (
          <dl className="products-page__detail-grid">
            <dt>{t('products.colName', 'Tên')}</dt>
            <dd>{detailProduct.name}</dd>

            <dt>{t('products.colType', 'Loại')}</dt>
            <dd>
              <Badge variant={DELIVERY_TYPE_VARIANT[detailProduct.delivery_type]} size="sm">
                {t(`products.type.${detailProduct.delivery_type}`, detailProduct.delivery_type)}
              </Badge>
            </dd>

            <dt>{t('products.colActive', 'Trạng thái')}</dt>
            <dd>
              <Badge variant={detailProduct.is_active ? 'success' : 'neutral'} size="sm">
                {detailProduct.is_active ? t('products.active', 'Hoạt động') : t('products.inactive', 'Tắt')}
              </Badge>
            </dd>

            {detailProduct.description && (
              <>
                <dt>{t('products.description', 'Mô tả')}</dt>
                <dd>{detailProduct.description}</dd>
              </>
            )}

            {['upgrade', 'virtual_order'].includes(detailProduct.delivery_type) && detailProduct.upgrade_request_text && (
              <>
                <dt>{detailProduct.delivery_type === 'virtual_order'
                  ? t('products.virtualDeliveryText', 'Nội dung giao hàng')
                  : t('products.upgradeText', 'Nội dung yêu cầu')}</dt>
                <dd>{detailProduct.upgrade_request_text}</dd>
              </>
            )}

            <dt>{t('products.colCreated', 'Tạo lúc')}</dt>
            <dd>{fmt.dateTime(detailProduct.created_at)}</dd>

            <dt>{t('products.updatedAt', 'Cập nhật')}</dt>
            <dd>{fmt.dateTime(detailProduct.updated_at)}</dd>
          </dl>
        )}
      </Modal>

      {/* ── Create / Edit modal ───────────────────────────────────── */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editTarget ? t('products.editTitle', 'Sửa sản phẩm') : t('products.createTitle', 'Tạo sản phẩm')}
        footer={
          <div className="products-page__modal-footer">
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setFormOpen(false)}>
              {t('common.cancel', 'Huỷ')}
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              form={formId}
              loading={formSaving}
            >
              {editTarget ? t('common.save', 'Lưu') : t('products.create', 'Tạo')}
            </Button>
          </div>
        }
      >
        <form id={formId} onSubmit={handleSave} className="products-page__form">
          {formError && (
            <div className="products-page__form-error" role="alert">{formError}</div>
          )}

          <FormField label={t('products.fieldName', 'Tên sản phẩm')} htmlFor={`${formId}-name`}>
            <Input
              id={`${formId}-name`}
              value={formData.name}
              onChange={e => setFormData(d => ({ ...d, name: e.target.value }))}
              placeholder={t('products.namePlaceholder', 'Nhập tên sản phẩm')}
              required
            />
          </FormField>

          <FormField label={t('products.fieldDesc', 'Mô tả')} htmlFor={`${formId}-desc`}>
            <EmojiAutocompleteTextarea
              id={`${formId}-desc`}
              value={formData.description}
              onChange={e => setFormData(d => ({ ...d, description: e.target.value }))}
              placeholder={t('products.descPlaceholder', 'Mô tả sản phẩm (tuỳ chọn)')}
              rows={3}
            />
          </FormField>

          <FormField label={t('products.fieldType', 'Loại giao hàng')} htmlFor={`${formId}-type`}>
            <Select<DeliveryType>
              options={deliveryTypeOptions}
              value={formData.delivery_type}
              onChange={v => v && setFormData(d => ({ ...d, delivery_type: v }))}
            />
          </FormField>

          {['upgrade', 'virtual_order'].includes(formData.delivery_type) && (
            <FormField
              label={formData.delivery_type === 'virtual_order'
                ? t('products.fieldVirtualDeliveryText', 'Nội dung giao hàng cố định')
                : t('products.fieldUpgradeText', 'Nội dung yêu cầu nâng cấp')}
              htmlFor={`${formId}-upgrade`}
            >
              <EmojiAutocompleteTextarea
                id={`${formId}-upgrade`}
                value={formData.upgrade_request_text}
                onChange={e => setFormData(d => ({ ...d, upgrade_request_text: e.target.value }))}
                placeholder={formData.delivery_type === 'virtual_order'
                  ? t('products.virtualDeliveryPlaceholder', 'Ví dụ: Liên hệ hỗ trợ để nhận tài khoản...')
                  : t('products.upgradePlaceholder', 'Nội dung gửi đến nhà cung cấp')}
                rows={3}
                required={formData.delivery_type === 'virtual_order'}
              />
            </FormField>
          )}

          <div className="products-page__form-switch">
            <Switch
              checked={formData.is_active}
              onChange={checked => setFormData(d => ({ ...d, is_active: checked }))}
              label={t('products.fieldActive', 'Kích hoạt sản phẩm')}
            />
          </div>
        </form>
      </Modal>
    </div>
  )
}
