import { useEffect, useMemo, useState } from 'react'
import { Image as ImageIcon, Save, RefreshCw, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import './IotdPage.css'

interface IotdResponse {
  image_url: string | null
}

export function IotdPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [imageUrl, setImageUrl] = useState('')
  const [savedUrl, setSavedUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [imgError, setImgError] = useState(false)

  const previewUrl = useMemo(() => imageUrl.trim(), [imageUrl])
  const dirty = previewUrl !== savedUrl

  const fetchConfig = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<IotdResponse>('/api/iotd')
      const url = res.data.image_url ?? ''
      setImageUrl(url)
      setSavedUrl(url)
      setImgError(false)
    } catch (err) {
      setError(formatApiError(err, t('iotd.loadError', 'Không thể tải cài đặt')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchConfig() }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await apiClient.put('/api/iotd', { image_url: previewUrl || null })
      setSavedUrl(previewUrl)
      toast.success(t('iotd.saved', 'Đã lưu ảnh ngày'))
    } catch (err) {
      setError(formatApiError(err, t('iotd.saveError', 'Không thể lưu')))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="iotd-page">
      <PageHeader
        title={t('nav.iotd', 'Ảnh ngày')}
        description={t('iotd.description', 'Ảnh hiển thị trên trang thống kê')}
        actions={
          <div className="iotd-page__actions">
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh', 'Làm mới')}
              variant="ghost"
              size="sm"
              onClick={fetchConfig}
              disabled={saving}
            />
            <Button
              variant="primary"
              size="sm"
              iconLeft={<Save size={14} />}
              loading={saving}
              disabled={!dirty}
              onClick={handleSave}
            >
              {t('common.save', 'Lưu')}
            </Button>
          </div>
        }
      />

      {error && <div className="iotd-page__error" role="alert">{error}</div>}

      <div className="iotd-page__layout">
        {/* ── Form ───────────────────────────────────────────────── */}
        <div className="iotd-page__form-col">
          <div className="iotd-page__form-card">
            {loading ? (
              <div className="iotd-page__skel">
                <Skeleton variant="line" width="25%" height={12} />
                <Skeleton variant="rect" height={40} radius="8px" />
              </div>
            ) : (
              <div className="iotd-page__field">
                <label className="iotd-page__label" htmlFor="iotd-url">
                  {t('iotd.urlLabel', 'URL ảnh')}
                </label>
                <Input
                  id="iotd-url"
                  value={imageUrl}
                  onChange={e => { setImageUrl(e.target.value); setImgError(false) }}
                  placeholder="https://example.com/image.jpg"
                  leftIcon={<ImageIcon size={14} />}
                  rightIcon={
                    previewUrl ? (
                      <a href={previewUrl} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>
                        <ExternalLink size={14} />
                      </a>
                    ) : undefined
                  }
                  clearable
                />
                <p className="iotd-page__hint">
                  {t('iotd.urlHint', 'Ảnh định dạng JPG, PNG, GIF hoặc WebP. Kích thước khuyến nghị: 1200×630px')}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ── Preview ─────────────────────────────────────────────── */}
        <div className="iotd-page__preview-col">
          <div className="iotd-page__preview-card">
            <div className="iotd-page__preview-header">{t('iotd.preview', 'Xem trước')}</div>
            <div className="iotd-page__preview-body">
              {previewUrl && !imgError ? (
                <img
                  src={previewUrl}
                  alt={t('iotd.previewAlt', 'Ảnh ngày')}
                  className="iotd-page__preview-img"
                  onError={() => setImgError(true)}
                />
              ) : imgError ? (
                <div className="iotd-page__preview-broken">
                  <ImageIcon size={32} />
                  <span>{t('iotd.imageError', 'Không tải được ảnh')}</span>
                </div>
              ) : (
                <div className="iotd-page__preview-empty">
                  <ImageIcon size={32} />
                  <span>{t('iotd.noImage', 'Chưa có ảnh')}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
