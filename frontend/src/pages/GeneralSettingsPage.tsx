import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw, Save } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useBranding } from '../contexts/BrandingContext'
import { Button } from '../shared/components/Button'
import { FormField } from '../shared/components/FormField'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { PageHeader } from '../shared/components/PageHeader'
import { Select } from '../shared/components/Select'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import './GeneralSettingsPage.css'

interface AppSettingsResponse {
  system_name: string
  bot_url: string
  support_line_1: string
  support_line_2: string
  timezone: string
  order_prefix: string
  api_docs_url: string
}

const EMPTY_SETTINGS: AppSettingsResponse = {
  system_name: '',
  bot_url: '',
  support_line_1: '',
  support_line_2: '',
  timezone: 'Asia/Ho_Chi_Minh',
  order_prefix: 'ORD',
  api_docs_url: '',
}

const FALLBACK_TIMEZONES = [
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

function buildTimezoneOptions(): Array<{ value: string; label: string }> {
  const intl = typeof Intl === 'undefined'
    ? null
    : Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] }
  const supported = intl?.supportedValuesOf?.('timeZone') ?? FALLBACK_TIMEZONES
  return [...new Set([...supported, 'UTC'])].map(timezone => ({ value: timezone, label: timezone }))
}

const TIMEZONE_OPTIONS = buildTimezoneOptions()

export function GeneralSettingsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const { refresh } = useBranding()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [settings, setSettings] = useState<AppSettingsResponse>(EMPTY_SETTINGS)
  const formRef = useRef<HTMLFormElement>(null)
  const savedSettingsRef = useRef<AppSettingsResponse>(EMPTY_SETTINGS)
  const dirty = JSON.stringify(settings) !== JSON.stringify(savedSettingsRef.current)

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get<AppSettingsResponse>('/api/app-settings')
      setSettings(response.data)
      savedSettingsRef.current = response.data
    } catch (err) {
      setError(formatApiError(err, t('generalSettings.loadError')))
    } finally {
      setLoading(false)
    }
  }, [t])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setError(null)
    try {
      const response = await apiClient.put<AppSettingsResponse>('/api/app-settings', settings)
      setSettings(response.data)
      savedSettingsRef.current = response.data
      await refresh()
      toast.success(t('generalSettings.saved'))
    } catch (err) {
      setError(formatApiError(err, t('generalSettings.saveError')))
    } finally {
      setSaving(false)
    }
  }, [refresh, settings, t, toast])

  useEffect(() => { void fetchSettings() }, [fetchSettings])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 's') {
        event.preventDefault()
        if (dirty && !saving) formRef.current?.requestSubmit()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [dirty, saving])

  const updateSetting = (key: keyof AppSettingsResponse, value: string) => {
    setSettings(current => ({ ...current, [key]: value }))
  }

  return (
    <div className="general-settings-page">
      <PageHeader
        title={t('nav.generalSettings')}
        description={t('generalSettings.description')}
        actions={
          <div className="general-settings-page__actions">
            <IconButton
              icon={<RefreshCw size={14} />}
              aria-label={t('common.refresh')}
              variant="ghost"
              size="sm"
              onClick={fetchSettings}
              disabled={saving}
            />
            <Button
              type="submit"
              form="general-settings-form"
              variant="primary"
              size="sm"
              iconLeft={<Save size={14} />}
              loading={saving}
              disabled={!dirty}
            >
              {t('common.save')}
              {dirty && <span className="general-settings-page__dirty-dot" aria-hidden="true" />}
            </Button>
          </div>
        }
      />

      {error && <div className="general-settings-page__error" role="alert">{error}</div>}

      {loading ? (
        <div className="general-settings-page__skel">
          <div className="general-settings-page__skel-field">
            <Skeleton variant="line" width="30%" height={12} />
            <Skeleton variant="rect" height={42} radius="8px" />
          </div>
        </div>
      ) : (
        <form
          ref={formRef}
          id="general-settings-form"
          className="general-settings-page__form"
          onSubmit={event => {
            event.preventDefault()
            void handleSave()
          }}
        >
          <FormField
            label={t('generalSettings.systemName')}
            htmlFor="gs-system-name"
            helperText={t('generalSettings.systemNameHint')}
          >
            <Input
              id="gs-system-name"
              value={settings.system_name}
              onChange={event => updateSetting('system_name', event.target.value)}
              maxLength={80}
              required
            />
          </FormField>

          <FormField
            label={t('generalSettings.botUrl')}
            htmlFor="gs-bot-url"
            helperText={t('generalSettings.botUrlHint')}
          >
            <Input
              id="gs-bot-url"
              type="url"
              value={settings.bot_url}
              onChange={event => updateSetting('bot_url', event.target.value)}
              required
            />
          </FormField>

          <FormField
            label={t('generalSettings.supportLine1')}
            htmlFor="gs-support-line-1"
            helperText={t('generalSettings.supportLine1Hint')}
          >
            <Input
              id="gs-support-line-1"
              value={settings.support_line_1}
              onChange={event => updateSetting('support_line_1', event.target.value)}
              maxLength={200}
            />
          </FormField>

          <FormField
            label={t('generalSettings.supportLine2')}
            htmlFor="gs-support-line-2"
            helperText={t('generalSettings.supportLine2Hint')}
          >
            <Input
              id="gs-support-line-2"
              value={settings.support_line_2}
              onChange={event => updateSetting('support_line_2', event.target.value)}
              maxLength={200}
            />
          </FormField>

          <div className="general-settings-page__info-box">
            {t('generalSettings.timezoneNote')}
          </div>

          <FormField
            label={t('generalSettings.timezone')}
            htmlFor="gs-timezone"
            helperText={t('generalSettings.timezoneHint')}
            required
          >
            <Select
              id="gs-timezone"
              options={TIMEZONE_OPTIONS}
              value={settings.timezone}
              onChange={value => updateSetting('timezone', value ?? savedSettingsRef.current.timezone)}
              searchable
              placeholder={t('generalSettings.timezonePlaceholder')}
            />
          </FormField>

          <FormField
            label={t('generalSettings.orderPrefix')}
            htmlFor="gs-order-prefix"
            helperText={t('generalSettings.orderPrefixHint')}
          >
            <Input
              id="gs-order-prefix"
              value={settings.order_prefix}
              onChange={event => updateSetting('order_prefix', event.target.value)}
              minLength={2}
              maxLength={8}
              required
            />
          </FormField>

          <FormField
            label={t('generalSettings.apiDocsUrl')}
            htmlFor="gs-api-docs-url"
            helperText={t('generalSettings.apiDocsUrlHint')}
          >
            <Input
              id="gs-api-docs-url"
              type="url"
              value={settings.api_docs_url}
              onChange={event => updateSetting('api_docs_url', event.target.value)}
            />
          </FormField>

          <p className="general-settings-page__shortcut-hint">
            {t('generalSettings.saveShortcut')}
          </p>
        </form>
      )}
    </div>
  )
}
