import { useState, useEffect, useCallback, useMemo } from 'react'
import { Plus, Edit, Trash2, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Badge } from '../shared/components/Badge'
import { Modal } from '../shared/components/Modal'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Switch } from '../shared/components/Switch'
import { FormField } from '../shared/components/FormField'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'

interface Manual {
  id: string
  title: string
  content: string
  is_active: boolean
  sort_order: number
  assigned_product_ids: string[]
  assigned_product_names: string[]
  created_at: string
  updated_at: string
}

interface Product {
  id: string
  name: string
}

const CONTENT_MAX = 4000

export function ManualsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [manuals, setManuals] = useState<Manual[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal state
  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Manual | null>(null)
  const [formTitle, setFormTitle] = useState('')
  const [formContent, setFormContent] = useState('')
  const [formActive, setFormActive] = useState(true)
  const [formSortOrder, setFormSortOrder] = useState(0)
  const [formProductIds, setFormProductIds] = useState<string[]>([])
  const [formError, setFormError] = useState<string | null>(null)
  const [formSaving, setFormSaving] = useState(false)

  const fetchManuals = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<Manual[]>('/api/manuals')
      setManuals(res.data)
    } catch (err) {
      setError(formatApiError(err, t('manuals.loadError', 'Không thể tải hướng dẫn')))
    } finally {
      setLoading(false)
    }
  }, [t])

  const fetchProducts = useCallback(async () => {
    try {
      const res = await apiClient.get<{ items: Product[] }>('/api/products/', {
        params: { page: 1, per_page: 100 },
      })
      setProducts(res.data.items)
    } catch {
      // silent — products list is optional for the filter
    }
  }, [])

  useEffect(() => {
    fetchManuals()
    fetchProducts()
  }, [fetchManuals, fetchProducts])

  const openCreate = () => {
    setEditTarget(null)
    setFormTitle('')
    setFormContent('')
    setFormActive(true)
    setFormSortOrder(0)
    setFormProductIds([])
    setFormError(null)
    setFormOpen(true)
  }

  const openEdit = (m: Manual) => {
    setEditTarget(m)
    setFormTitle(m.title)
    setFormContent(m.content)
    setFormActive(m.is_active)
    setFormSortOrder(m.sort_order)
    setFormProductIds([...m.assigned_product_ids])
    setFormError(null)
    setFormOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formTitle.trim()) {
      setFormError(t('manuals.titleRequired', 'Tiêu đề là bắt buộc'))
      return
    }
    if (formContent.length > CONTENT_MAX) {
      setFormError(t('manuals.contentTooLong', `Nội dung tối đa ${CONTENT_MAX} ký tự`))
      return
    }
    setFormSaving(true)
    setFormError(null)
    try {
      const payload = {
        title: formTitle.trim(),
        content: formContent,
        is_active: formActive,
        sort_order: formSortOrder,
        product_ids: formProductIds,
      }
      if (editTarget) {
        await apiClient.put(`/api/manuals/${editTarget.id}`, payload)
        toast.success(t('manuals.updated', 'Đã cập nhật hướng dẫn'))
      } else {
        await apiClient.post('/api/manuals/', payload)
        toast.success(t('manuals.created', 'Đã tạo hướng dẫn mới'))
      }
      setFormOpen(false)
      fetchManuals()
    } catch (err) {
      setFormError(formatApiError(err, t('manuals.saveError', 'Lưu thất bại')))
    } finally {
      setFormSaving(false)
    }
  }

  const handleDelete = async (m: Manual) => {
    const ok = await confirm({
      title: t('manuals.deleteTitle', 'Xóa hướng dẫn'),
      description: t('manuals.deleteConfirm', `Xóa "${m.title}"?`),
      confirmLabel: t('common.delete', 'Xóa'),
      variant: 'destructive',
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/manuals/${m.id}`)
      toast.success(t('manuals.deleted', 'Đã xóa hướng dẫn'))
      fetchManuals()
    } catch (err) {
      toast.error(formatApiError(err, t('manuals.deleteError', 'Xóa thất bại')))
    }
  }

  const toggleProductId = (id: string) => {
    setFormProductIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
  }

  const columns = useMemo<ColumnDef<Manual>[]>(() => [
    {
      id: 'title',
      header: t('manuals.colTitle', 'Tiêu đề'),
      cell: (m) => <span style={{ fontWeight: 500 }}>{m.title}</span>,
    },
    {
      id: 'products',
      header: t('manuals.colProducts', 'Sản phẩm'),
      cell: (m) => (
        <span style={{ color: '#9CA3AF', fontSize: 13 }}>
          {m.assigned_product_names.length > 0
            ? m.assigned_product_names.join(', ')
            : <em>{t('manuals.noProducts', 'Chưa gán')}</em>
          }
        </span>
      ),
    },
    {
      id: 'sort_order',
      header: t('manuals.colSortOrder', 'Thứ tự'),
      cell: (m) => <span>{m.sort_order}</span>,
    },
    {
      id: 'is_active',
      header: t('manuals.colStatus', 'Trạng thái'),
      cell: (m) => (
        <Badge variant={m.is_active ? 'success' : 'neutral'}>
          {m.is_active
            ? t('manuals.active', 'Hoạt động')
            : t('manuals.inactive', 'Tắt')
          }
        </Badge>
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      cell: (m) => (
        <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
          <IconButton
            icon={<Edit size={14} />}
            onClick={() => openEdit(m)}
            aria-label={t('common.edit', 'Sửa')}
            size="sm"
          />
          <IconButton
            icon={<Trash2 size={14} />}
            onClick={() => handleDelete(m)}
            aria-label={t('common.delete', 'Xóa')}
            size="sm"
            variant="destructive"
          />
        </div>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [t])

  return (
    <div style={{ padding: '24px', background: '#0F0F0D', minHeight: '100vh', color: '#E5E7EB' }}>
      <PageHeader
        title={t('nav.manuals', 'Hướng dẫn sử dụng')}
        description={t('manuals.description', 'Quản lý hướng dẫn sử dụng cho sản phẩm')}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <IconButton
              icon={<RefreshCw size={14} />}
              onClick={fetchManuals}
              aria-label={t('common.refresh', 'Làm mới')}
              size="sm"
              variant="ghost"
            />
            <Button onClick={openCreate} size="sm">
              <Plus size={14} style={{ marginRight: 4 }} />
              {t('manuals.create', 'Tạo mới')}
            </Button>
          </div>
        }
      />

      {error && (
        <div style={{ color: '#F87171', marginBottom: 16, padding: '8px 12px', background: '#1F1F1D', borderRadius: 6 }}>
          {error}
        </div>
      )}

      <div style={{ background: '#181816', borderRadius: 8, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} variant="line" height={36} />
            ))}
          </div>
        ) : (
          <Table<Manual> columns={columns} data={manuals} keyFn={m => m.id} />
        )}
      </div>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editTarget
          ? t('manuals.editTitle', 'Chỉnh sửa hướng dẫn')
          : t('manuals.createTitle', 'Tạo hướng dẫn mới')
        }
      >
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <FormField label={t('manuals.fieldTitle', 'Tiêu đề')} required>
            <Input
              value={formTitle}
              onChange={e => setFormTitle(e.target.value)}
              placeholder={t('manuals.titlePlaceholder', 'Tiêu đề hướng dẫn')}
            />
          </FormField>

          <FormField
            label={`${t('manuals.fieldContent', 'Nội dung')} (${formContent.length}/${CONTENT_MAX})`}
            required
          >
            <textarea
              value={formContent}
              onChange={e => setFormContent(e.target.value)}
              maxLength={CONTENT_MAX}
              rows={8}
              placeholder={t('manuals.contentPlaceholder', 'Nội dung hướng dẫn...')}
              style={{
                width: '100%',
                background: '#111110',
                border: '1px solid #2D2D2B',
                borderRadius: 6,
                color: '#E5E7EB',
                padding: '8px 12px',
                fontSize: 14,
                resize: 'vertical',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
                outline: 'none',
              }}
            />
          </FormField>

          <FormField label={t('manuals.fieldProducts', 'Sản phẩm áp dụng')}>
            <div style={{
              maxHeight: 200,
              overflowY: 'auto',
              background: '#111110',
              border: '1px solid #2D2D2B',
              borderRadius: 6,
              padding: 8,
            }}>
              {products.length === 0 ? (
                <span style={{ color: '#6B7280', fontSize: 13 }}>
                  {t('manuals.noProductsAvailable', 'Chưa có sản phẩm')}
                </span>
              ) : (
                products.map(p => (
                  <label
                    key={p.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '4px 0',
                      cursor: 'pointer',
                      fontSize: 14,
                      color: '#E5E7EB',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={formProductIds.includes(p.id)}
                      onChange={() => toggleProductId(p.id)}
                      style={{ accentColor: '#6EA8FF' }}
                    />
                    {p.name}
                  </label>
                ))
              )}
            </div>
          </FormField>

          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <FormField label={t('manuals.fieldSortOrder', 'Thứ tự hiển thị')}>
                <Input
                  type="number"
                  value={String(formSortOrder)}
                  onChange={e => setFormSortOrder(parseInt(e.target.value) || 0)}
                />
              </FormField>
            </div>
            <div style={{ paddingTop: 22 }}>
              <FormField label={t('manuals.fieldActive', 'Hoạt động')}>
                <Switch checked={formActive} onChange={setFormActive} />
              </FormField>
            </div>
          </div>

          {formError && (
            <div style={{ color: '#F87171', fontSize: 13 }}>{formError}</div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="secondary" type="button" onClick={() => setFormOpen(false)} size="sm">
              {t('common.cancel', 'Hủy')}
            </Button>
            <Button type="submit" disabled={formSaving} size="sm">
              {formSaving
                ? t('common.saving', 'Đang lưu...')
                : t('common.save', 'Lưu')
              }
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
