import { useEffect, useState, useRef } from 'react'
import { Save, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { FormField } from '../shared/components/FormField'
import { Select } from '../shared/components/Select'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import './GeneralSettingsPage.css'

interface AppSettingsResponse {
  timezone: string
}

/** Build a list of IANA timezone options for the dropdown. */
function buildTimezoneOptions(): Array<{ value: string; label: string }> {
  // Intl.supportedValuesOf is ES2022 — guard for environments that lack it
  const supported =
    typeof Intl !== 'undefined' &&
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    typeof (Intl as any).supportedValuesOf === 'function'
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (Intl as any).supportedValuesOf('timeZone') as string[]
      : FALLBACK_TIMEZONES

  return supported.map(tz => ({ value: tz, label: tz }))
}

/** Curated fallback list for environments without Intl.supportedValuesOf. */
const FALLBACK_TIMEZONES: string[] = [
  'Asia/Ho_Chi_Minh',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'UTC',
]

export function GeneralSettingsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  const [timezone, setTimezone] = useState<string>('Asia/Ho_Chi_Minh')
  const savedTimezoneRef = useRef<string>(timezone)

  const tzOptions = buildTimezoneOptions()

  const fetchSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<AppSettingsResponse>('/api/app-settings')
      const loaded = res.data.timezone
      setTimezone(loaded)
      savedTimezoneRef.current = loaded
      setDirty(false)
    } catch (err) {
      setError(formatApiError(err, t('generalSettings.loadError', 'Không thể tải cài đặt')))
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
  }, [dirty, saving, timezone])

  const handleTimezoneChange = (value: string | null) => {
    const next = value ?? savedTimezoneRef.current
    setTimezone(next)
    setDirty(next !== savedTimezoneRef.current)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await apiClient.put('/api/app-settings', { timezone })
      savedTimezoneRef.current = timezone
      setDirty(false)
      toast.success(t('generalSettings.saved', 'Đã lưu cài đặt'))
    } catch (err) {
      setError(formatApiError(err, t('generalSettings.saveError', 'Không thể lưu cài đặt')))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="general-settings-page">
      <PageHeader
        title={t('nav.generalSettings', 'Cài đặt chung')}
        description={t('generalSettings.description', 'Cấu hình múi giờ và các tuỳ chọn toàn cục')}
        actions={
          <div className="general-settings-page__actions">
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
              {dirty && <span className="general-settings-page__dirty-dot" aria-hidden="true" />}
            </Button>
          </div>
        }
      />

      {error && (
        <div className="general-settings-page__error" role="alert">{error}</div>
      )}

      {loading ? (
        <div className="general-settings-page__skel">
          <div className="general-settings-page__skel-field">
            <Skeleton variant="line" width="30%" height={12} />
            <Skeleton variant="rect" height={42} radius="8px" />
          </div>
        </div>
      ) : (
        <div className="general-settings-page__form">
          <div className="general-settings-page__info-box">
            {t(
              'generalSettings.timezoneNote',
              'Múi giờ này áp dụng cho bot Telegram — tất cả thời gian hiển thị trong bot sẽ theo múi giờ này. Dashboard luôn hiển thị theo múi giờ trình duyệt của bạn.',
            )}
          </div>

          <FormField
            label={t('generalSettings.timezone', 'Múi giờ bot')}
            htmlFor="gs-timezone"
            helperText={t('generalSettings.timezoneHint', 'Chọn múi giờ IANA cho bot Telegram')}
          >
            <Select
              id="gs-timezone"
              options={tzOptions}
              value={timezone}
              onChange={handleTimezoneChange}
              searchable
              placeholder={t('generalSettings.timezonePlaceholder', 'Chọn múi giờ...')}
            />
          </FormField>

          <p className="general-settings-page__shortcut-hint">
            {t('botUi.saveHint', 'Nhấn Ctrl+S (⌘S) để lưu nhanh')}
          </p>
        </div>
      )}
    </div>
  )
}
