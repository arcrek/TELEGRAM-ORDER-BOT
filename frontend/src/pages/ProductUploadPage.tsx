import { useState, useEffect, useMemo } from 'react'
import { Upload, FileText, CheckCircle, XCircle, UploadCloud } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Tabs } from '../shared/components/Tabs'
import { FileDrop, FileChip } from '../shared/components/FileDrop'
import { Select } from '../shared/components/Select'
import { Textarea } from '../shared/components/Textarea'
import { FormField } from '../shared/components/FormField'
import { Radio } from '../shared/components/Radio'
import { StatCard } from '../shared/components/StatCard'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Button } from '../shared/components/Button'
import { useToast } from '../shared/components/Toast'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { apiClient, formatApiError } from '../shared/lib/api'
import './ProductUploadPage.css'

type FormatType = 'line_separated' | 'key_value' | 'csv'
type View = 'configure' | 'preview' | 'result'

interface ParsedItem { [key: string]: string }
interface UploadResult {
  success: number
  failed: number
  duplicates_skipped: number
  errors: Array<{ index: number; error: string; data: unknown }>
}
interface Variation { id: string; name: string }
interface ProductGroup { product_id: string; product_name: string; variations: Variation[] }
interface PreviewRow { idx: number; content: string }

function extractContent(item: ParsedItem): string {
  const keys = Object.keys(item)
  if (keys.length === 1 && keys[0] === 'data') return String(item.data)
  return JSON.stringify(item)
}

export function ProductUploadPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [view, setView] = useState<View>('configure')
  const [activeTab, setActiveTab] = useState<'file' | 'paste'>('file')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [pasteContent, setPasteContent] = useState('')
  const [formatType, setFormatType] = useState<FormatType>('line_separated')
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)
  const [selectedVariationId, setSelectedVariationId] = useState<string | null>(null)
  const [productGroups, setProductGroups] = useState<ProductGroup[]>([])
  const [parsedData, setParsedData] = useState<ParsedItem[]>([])
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [groupsLoading, setGroupsLoading] = useState(false)

  useEffect(() => {
    const load = async () => {
      setGroupsLoading(true)
      try {
        const res = await apiClient.get<{ items: ProductGroup[] }>('/api/variations')
        setProductGroups(res.data.items ?? [])
      } catch (err) {
        toast.error(formatApiError(err, t('upload.loadError', 'Không thể tải sản phẩm')))
      } finally {
        setGroupsLoading(false)
      }
    }
    load()
  }, [])

  const productOptions = useMemo(() =>
    productGroups.map(g => ({ value: g.product_id, label: g.product_name })),
    [productGroups],
  )

  const variationOptions = useMemo(() => {
    const group = productGroups.find(g => g.product_id === selectedProductId)
    return (group?.variations ?? []).map(v => ({ value: v.id, label: v.name }))
  }, [productGroups, selectedProductId])

  const selectedProductName = useMemo(() =>
    productGroups.find(g => g.product_id === selectedProductId)?.product_name ?? '',
    [productGroups, selectedProductId],
  )

  const selectedVariationName = useMemo(() => {
    const group = productGroups.find(g => g.product_id === selectedProductId)
    return group?.variations.find(v => v.id === selectedVariationId)?.name ?? ''
  }, [productGroups, selectedProductId, selectedVariationId])

  const canParse = !!(selectedProductId && selectedVariationId &&
    (activeTab === 'file' ? selectedFile : pasteContent.trim()))

  const handleParse = async () => {
    if (!canParse) return
    setLoading(true)
    try {
      let res: { data: { parsed_data: ParsedItem[] } }
      if (activeTab === 'file') {
        const formData = new FormData()
        formData.append('file', selectedFile!)
        formData.append('format_type', formatType)
        res = await apiClient.post('/api/products/upload/file', formData)
      } else {
        res = await apiClient.post('/api/products/upload/parse', {
          content: pasteContent,
          format_type: formatType,
        })
      }
      setParsedData(res.data.parsed_data ?? [])
      setView('preview')
    } catch (err) {
      toast.error(formatApiError(err, t('upload.parseError', 'Không thể phân tích dữ liệu')))
    } finally {
      setLoading(false)
    }
  }

  const buildUploadItems = () =>
    parsedData.map(item => ({
      product_id: selectedProductId!,
      variation_id: selectedVariationId!,
      product_data: extractContent(item),
    }))

  const doUpload = async (skipDuplicates: boolean) => {
    setLoading(true)
    try {
      const res = await apiClient.post<UploadResult>('/api/products/upload', {
        products: buildUploadItems(),
        skip_duplicates: skipDuplicates,
      })
      setUploadResult(res.data)
      setView('result')
    } catch (err) {
      toast.error(formatApiError(err, t('upload.uploadError', 'Không thể tải lên')))
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async () => {
    setLoading(true)
    try {
      const checkRes = await apiClient.post<{ duplicate_count: number; unique_count: number }>(
        '/api/products/upload/check-duplicates',
        { products: buildUploadItems() },
      )
      setLoading(false)

      const { duplicate_count, unique_count } = checkRes.data
      if (duplicate_count > 0) {
        const ok = await confirm({
          title: t('upload.duplicateTitle', `${duplicate_count} mục trùng lặp`),
          description: t('upload.duplicateDesc', `Có ${duplicate_count} mục đã tồn tại (đang có hoặc đã bán). Các mục này sẽ bị từ chối. ${unique_count} mục mới sẽ được thêm.`),
          confirmLabel: t('upload.continueUpload', 'Tiếp tục tải lên'),
        })
        if (!ok) return
        await doUpload(false)
      } else {
        await doUpload(false)
      }
    } catch (err) {
      setLoading(false)
      toast.error(formatApiError(err, t('upload.checkError', 'Không thể kiểm tra trùng lặp')))
    }
  }

  const handleReset = () => {
    setView('configure')
    setSelectedFile(null)
    setPasteContent('')
    setParsedData([])
    setUploadResult(null)
  }

  const previewRows: PreviewRow[] = parsedData.slice(0, 50).map((item, i) => ({
    idx: i + 1,
    content: extractContent(item),
  }))

  const previewColumns: ColumnDef<PreviewRow>[] = [
    { id: 'idx', header: '#', width: 56, mono: true, cell: row => String(row.idx) },
    { id: 'content', header: t('upload.colContent', 'Nội dung'), mono: true, cell: row => row.content },
  ]

  const formatOptions: Array<{ value: FormatType; label: string }> = [
    { value: 'line_separated', label: t('upload.fmtLine', 'Mỗi dòng') },
    { value: 'key_value', label: t('upload.fmtKV', 'Key=Value') },
    { value: 'csv', label: 'CSV' },
  ]

  const fileTabPanel = (
    <div className="product-upload-page__tab-content">
      {selectedFile ? (
        <FileChip file={selectedFile} onRemove={() => setSelectedFile(null)} />
      ) : (
        <FileDrop
          accept=".txt"
          onFiles={files => setSelectedFile(files[0] ?? null)}
          onError={msg => toast.error(msg)}
          label={t('upload.dropLabel', 'Kéo thả file .txt hoặc click để chọn')}
          hint={t('upload.dropHint', 'Chỉ hỗ trợ file .txt')}
        />
      )}
      <div className="product-upload-page__format-group">
        <span className="product-upload-page__format-label">{t('upload.format', 'Định dạng')}:</span>
        {formatOptions.map(o => (
          <Radio
            key={o.value}
            name="fmt-file"
            value={o.value}
            label={o.label}
            checked={formatType === o.value}
            onChange={v => setFormatType(v as FormatType)}
          />
        ))}
      </div>
    </div>
  )

  const pasteTabPanel = (
    <div className="product-upload-page__tab-content">
      <FormField label={t('upload.pasteLabel', 'Dán nội dung')}>
        <Textarea
          value={pasteContent}
          onChange={e => setPasteContent(e.target.value)}
          placeholder={t('upload.pastePlaceholder', 'Dán dữ liệu vào đây...')}
          rows={10}
          className="product-upload-page__paste-area"
        />
      </FormField>
      <div className="product-upload-page__format-group">
        <span className="product-upload-page__format-label">{t('upload.format', 'Định dạng')}:</span>
        {formatOptions.map(o => (
          <Radio
            key={o.value}
            name="fmt-paste"
            value={o.value}
            label={o.label}
            checked={formatType === o.value}
            onChange={v => setFormatType(v as FormatType)}
          />
        ))}
      </div>
    </div>
  )

  return (
    <div className="product-upload-page">
      <PageHeader title={t('nav.upload', 'Tải lên sản phẩm')} />

      {/* ── Target: Product + Variation ─────────────────────────── */}
      <div className="product-upload-page__target">
        <div className="product-upload-page__target-grid">
          <FormField label={t('upload.product', 'Sản phẩm')}>
            <Select
              options={productOptions}
              value={selectedProductId}
              onChange={v => { setSelectedProductId(v); setSelectedVariationId(null) }}
              placeholder={t('upload.selectProduct', 'Chọn sản phẩm')}
              searchable
              clearable
              disabled={groupsLoading}
            />
          </FormField>
          <FormField label={t('upload.variation', 'Biến thể')}>
            <Select
              options={variationOptions}
              value={selectedVariationId}
              onChange={setSelectedVariationId}
              placeholder={t('upload.selectVariation', 'Chọn biến thể')}
              disabled={!selectedProductId || groupsLoading}
            />
          </FormField>
        </div>
      </div>

      {/* ── Configure: tabs + parse ──────────────────────────────── */}
      {view === 'configure' && (
        <div className="product-upload-page__tabs-card">
          <Tabs
            tabs={[
              { key: 'file', label: t('upload.fileTab', 'File .txt'), panel: fileTabPanel },
              { key: 'paste', label: t('upload.pasteTab', 'Dán nội dung'), panel: pasteTabPanel },
            ]}
            activeKey={activeTab}
            onChange={k => setActiveTab(k as 'file' | 'paste')}
          />
          <div className="product-upload-page__parse-actions">
            <Button
              variant="primary"
              onClick={handleParse}
              disabled={!canParse}
              loading={loading}
              iconLeft={<FileText size={14} />}
            >
              {t('upload.parse', 'Phân tích')}
            </Button>
          </div>
        </div>
      )}

      {/* ── Preview ──────────────────────────────────────────────── */}
      {view === 'preview' && (
        <div className="product-upload-page__preview">
          <div className="product-upload-page__preview-banner">
            <span className="product-upload-page__preview-count">
              {t('upload.parsedCount', `${parsedData.length} mục đã phân tích`)}
            </span>
            {selectedProductName && (
              <span className="product-upload-page__preview-ctx">
                {selectedProductName} / {selectedVariationName}
              </span>
            )}
          </div>
          <div className="product-upload-page__preview-table">
            <Table<PreviewRow>
              columns={previewColumns}
              data={previewRows}
              keyFn={row => String(row.idx)}
              stickyHeader
              emptyTitle={t('upload.noData', 'Không có dữ liệu')}
            />
          </div>
          {parsedData.length > 50 && (
            <p className="product-upload-page__preview-note">
              {t('upload.previewNote', `Hiển thị 50/${parsedData.length} mục đầu tiên`)}
            </p>
          )}
          <div className="product-upload-page__preview-actions">
            <Button variant="secondary" tone="ghost" size="sm" onClick={() => setView('configure')}>
              {t('common.back', 'Quay lại')}
            </Button>
            <Button
              variant="primary"
              onClick={handleUpload}
              loading={loading}
              iconLeft={<Upload size={14} />}
            >
              {t('upload.upload', `Tải lên ${parsedData.length} mục`)}
            </Button>
          </div>
        </div>
      )}

      {/* ── Result ───────────────────────────────────────────────── */}
      {view === 'result' && uploadResult && (
        <div className="product-upload-page__result">
          <div className="product-upload-page__result-kpi">
            <StatCard
              label={t('upload.success', 'Thành công')}
              value={String(uploadResult.success)}
              icon={<CheckCircle size={16} />}
            />
            <StatCard
              label={t('upload.failed', 'Thất bại')}
              value={String(uploadResult.failed)}
              icon={<XCircle size={16} />}
            />
          </div>
          {uploadResult.errors.length > 0 && (
            <details className="product-upload-page__error-log">
              <summary className="product-upload-page__error-summary">
                {t('upload.errorCount', `${uploadResult.errors.length} lỗi chi tiết`)}
              </summary>
              <div className="product-upload-page__error-list">
                {uploadResult.errors.map((err, i) => (
                  <div key={i} className="product-upload-page__error-item">
                    <strong>#{err.index}:</strong> {err.error}
                  </div>
                ))}
              </div>
            </details>
          )}
          <div className="product-upload-page__reset">
            <Button variant="primary" iconLeft={<UploadCloud size={14} />} onClick={handleReset}>
              {t('upload.uploadMore', 'Tải lên thêm')}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
