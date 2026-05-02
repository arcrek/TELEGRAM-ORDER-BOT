import { useEffect, useState, useRef } from 'react'
import { Save, RefreshCw, Bot } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { FormField } from '../shared/components/FormField'
import { Textarea } from '../shared/components/Textarea'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import './BotUiSettingsPage.css'

interface BotUiSettingsResponse {
  product_choose_text: string | null
  variation_choose_text: string | null
  upload_notification_header: string | null
}

export function BotUiSettingsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  const [fields, setFields] = useState({
    product_choose_text: '',
    variation_choose_text: '',
    upload_notification_header: '',
  })
  const savedRef = useRef(fields)

  const setField = (key: keyof typeof fields) => (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFields(f => {
      const next = { ...f, [key]: e.target.value }
      setDirty(JSON.stringify(next) !== JSON.stringify(savedRef.current))
      return next
    })
  }

  const fetchSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<BotUiSettingsResponse>('/api/bot-ui-settings')
      const loaded = {
        product_choose_text: res.data.product_choose_text ?? '',
        variation_choose_text: res.data.variation_choose_text ?? '',
        upload_notification_header: res.data.upload_notification_header ?? '',
      }
      setFields(loaded)
      savedRef.current = loaded
      setDirty(false)
    } catch (err) {
      setError(formatApiError(err, t('botUi.loadError', 'Không thể tải cài đặt')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSettings() }, [])

  // Cmd/Ctrl+S to save
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (dirty && !saving) handleSave()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [dirty, saving, fields])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await apiClient.put('/api/bot-ui-settings', {
        product_choose_text: fields.product_choose_text || null,
        variation_choose_text: fields.variation_choose_text || null,
        upload_notification_header: fields.upload_notification_header || null,
      })
      savedRef.current = fields
      setDirty(false)
      toast.success(t('botUi.saved', 'Đã lưu cài đặt'))
    } catch (err) {
      setError(formatApiError(err, t('botUi.saveError', 'Không thể lưu cài đặt')))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bot-ui-settings-page">
      <PageHeader
        title={t('nav.botUiSettings', 'Cài đặt giao diện Bot')}
        description={t('botUi.description', 'Tuỳ chỉnh văn bản hiển thị trong bot Telegram')}
        actions={
          <div className="bot-ui-settings-page__actions">
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={fetchSettings}
              disabled={saving}
            />
            <Button
              variant="primary"
              size="sm"
              iconLeft={<Save size={14} />}
              onClick={handleSave}
              loading={saving}
              disabled={!dirty}
            >
              {t('common.save', 'Lưu')}
              {dirty && <span className="bot-ui-settings-page__dirty-dot" aria-hidden="true" />}
            </Button>
          </div>
        }
      />

      {error && (
        <div className="bot-ui-settings-page__error" role="alert">{error}</div>
      )}

      <div className="bot-ui-settings-page__layout">
        {/* ── Settings form ─────────────────────────────────────── */}
        <div className="bot-ui-settings-page__form-col">
          {loading ? (
            <div className="bot-ui-settings-page__skel">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="bot-ui-settings-page__skel-field">
                  <Skeleton variant="line" width="30%" height={12} />
                  <Skeleton variant="rect" height={80} radius="8px" />
                </div>
              ))}
            </div>
          ) : (
            <div className="bot-ui-settings-page__form">
              <FormField
                label={t('botUi.uploadHeader', 'Tiêu đề thông báo upload hàng')}
                htmlFor="bui-upload"
                helperText={t('botUi.uploadHeaderHint', 'Hiển thị khi có sản phẩm mới được tải lên')}
              >
                <Textarea
                  id="bui-upload"
                  value={fields.upload_notification_header}
                  onChange={setField('upload_notification_header')}
                  placeholder={t('botUi.uploadHeaderPlaceholder', '📢 Có hàng mới!')}
                  rows={2}
                  autoResize
                />
              </FormField>

              <FormField
                label={t('botUi.productText', 'Văn bản chọn sản phẩm')}
                htmlFor="bui-product"
                helperText={t('botUi.productTextHint', 'Hiển thị trước danh sách sản phẩm')}
              >
                <Textarea
                  id="bui-product"
                  value={fields.product_choose_text}
                  onChange={setField('product_choose_text')}
                  placeholder={t('botUi.productTextPlaceholder', 'Chọn loại dịch vụ bạn muốn')}
                  rows={4}
                  autoResize
                />
              </FormField>

              <FormField
                label={t('botUi.variationText', 'Văn bản chọn gói')}
                htmlFor="bui-variation"
                helperText={t('botUi.variationTextHint', 'Hiển thị trước danh sách gói')}
              >
                <Textarea
                  id="bui-variation"
                  value={fields.variation_choose_text}
                  onChange={setField('variation_choose_text')}
                  placeholder={t('botUi.variationTextPlaceholder', 'Chọn gói phù hợp')}
                  rows={4}
                  autoResize
                />
              </FormField>

              <p className="bot-ui-settings-page__shortcut-hint">
                {t('botUi.saveHint', 'Nhấn Ctrl+S (⌘S) để lưu nhanh')}
              </p>
            </div>
          )}
        </div>

        {/* ── Preview pane ─────────────────────────────────────── */}
        <div className="bot-ui-settings-page__preview-col">
          <div className="bot-ui-settings-page__preview-card">
            <div className="bot-ui-settings-page__preview-header">
              <Bot size={14} />
              <span>{t('botUi.preview', 'Xem trước')}</span>
            </div>
            <div className="bot-ui-settings-page__preview-body">
              {fields.upload_notification_header && (
                <div className="bot-ui-settings-page__preview-bubble">
                  <span className="bot-ui-settings-page__preview-label">
                    {t('botUi.uploadHeader', 'Thông báo upload')}
                  </span>
                  <p>{fields.upload_notification_header}</p>
                </div>
              )}
              {fields.product_choose_text && (
                <div className="bot-ui-settings-page__preview-bubble">
                  <span className="bot-ui-settings-page__preview-label">
                    {t('botUi.productText', 'Chọn sản phẩm')}
                  </span>
                  <p>{fields.product_choose_text}</p>
                  <div className="bot-ui-settings-page__preview-btns">
                    <span>{t('botUi.previewBtn', 'Tài khoản')} 1</span>
                    <span>{t('botUi.previewBtn', 'Tài khoản')} 2</span>
                  </div>
                </div>
              )}
              {fields.variation_choose_text && (
                <div className="bot-ui-settings-page__preview-bubble">
                  <span className="bot-ui-settings-page__preview-label">
                    {t('botUi.variationText', 'Chọn gói')}
                  </span>
                  <p>{fields.variation_choose_text}</p>
                  <div className="bot-ui-settings-page__preview-btns">
                    <span>100 follow — 50k</span>
                    <span>500 follow — 200k</span>
                  </div>
                </div>
              )}
              {!fields.upload_notification_header && !fields.product_choose_text && !fields.variation_choose_text && (
                <p className="bot-ui-settings-page__preview-empty">
                  {t('botUi.previewEmpty', 'Nhập nội dung bên trái để xem trước')}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
