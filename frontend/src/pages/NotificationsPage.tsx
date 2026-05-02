import { useState, useEffect } from 'react'
import { Send, Users, RefreshCw, CheckCircle, XCircle, Bell } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Tabs } from '../shared/components/Tabs'
import { Button } from '../shared/components/Button'
import { Textarea } from '../shared/components/Textarea'
import { Switch } from '../shared/components/Switch'
import { Badge } from '../shared/components/Badge'
import { FormField } from '../shared/components/FormField'
import { Skeleton } from '../shared/components/Skeleton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import './NotificationsPage.css'

interface BotUser {
  id: string
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  has_started: boolean
  is_active: boolean
}

interface NotificationResult {
  success: boolean
  total: number
  successful: number
  failed: number
}

interface OrderNotificationSettings {
  order_notify_enabled: boolean
  order_notify_on_created: boolean
  order_notify_on_paid: boolean
  whitelist_chat_ids: string[]
  upgrade_chat_ids: string[]
}

type AudienceMode = 'all' | 'active' | 'specific'

function parseChatIds(text: string): string[] {
  const seen = new Set<string>()
  return text
    .split(/[\n,]/)
    .map(s => s.trim())
    .filter(s => /^-?\d+(:\d+)?$/.test(s) && !seen.has(s) && seen.add(s))
}

export function NotificationsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()

  // ── Broadcast state ────────────────────────────────────────────────
  const [message, setMessage] = useState('')
  const [audienceMode, setAudienceMode] = useState<AudienceMode>('all')
  const [users, setUsers] = useState<BotUser[]>([])
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set())
  const [loadingUsers, setLoadingUsers] = useState(false)
  const [sending, setSending] = useState(false)
  const [sendResult, setSendResult] = useState<NotificationResult | null>(null)

  // ── Order notification settings state ─────────────────────────────
  const [orderSettings, setOrderSettings] = useState<OrderNotificationSettings | null>(null)
  const [whitelistText, setWhitelistText] = useState('')
  const [upgradeText, setUpgradeText] = useState('')
  const [loadingOrderSettings, setLoadingOrderSettings] = useState(false)
  const [savingOrderSettings, setSavingOrderSettings] = useState(false)

  useEffect(() => {
    fetchOrderSettings()
  }, [])

  useEffect(() => {
    if (audienceMode === 'specific') fetchUsers()
  }, [audienceMode])

  const fetchUsers = async () => {
    setLoadingUsers(true)
    try {
      const res = await apiClient.get<BotUser[]>('/api/notifications/users')
      setUsers(res.data)
    } catch (err) {
      toast.error(formatApiError(err, t('notifications.usersError', 'Không thể tải danh sách người dùng')))
    } finally {
      setLoadingUsers(false)
    }
  }

  const fetchOrderSettings = async () => {
    setLoadingOrderSettings(true)
    try {
      const res = await apiClient.get<OrderNotificationSettings>('/api/notifications/order-settings')
      setOrderSettings(res.data)
      setWhitelistText((res.data.whitelist_chat_ids ?? []).join('\n'))
      setUpgradeText((res.data.upgrade_chat_ids ?? []).join('\n'))
    } catch (err) {
      toast.error(formatApiError(err, t('notifications.settingsError', 'Không thể tải cài đặt thông báo')))
    } finally {
      setLoadingOrderSettings(false)
    }
  }

  const handleSend = async () => {
    if (!message.trim()) {
      toast.warning(t('notifications.emptyMessage', 'Nhập nội dung tin nhắn'))
      return
    }
    setSending(true)
    setSendResult(null)
    try {
      const payload: Record<string, unknown> = { message }
      let url = '/api/notifications/send'

      if (audienceMode === 'active') {
        url = '/api/notifications/send/active'
      } else if (audienceMode === 'specific' && selectedUserIds.size > 0) {
        payload.user_ids = Array.from(selectedUserIds)
      }

      const res = await apiClient.post<NotificationResult>(url, payload)
      setSendResult(res.data)
      if (res.data.success) {
        setMessage('')
        setSelectedUserIds(new Set())
        toast.success(
          t('notifications.sent', `Đã gửi: ${res.data.successful}/${res.data.total}`),
        )
      }
    } catch (err) {
      toast.error(formatApiError(err, t('notifications.sendError', 'Không thể gửi thông báo')))
    } finally {
      setSending(false)
    }
  }

  const handleSaveOrderSettings = async () => {
    if (!orderSettings) return
    setSavingOrderSettings(true)
    try {
      const res = await apiClient.put<OrderNotificationSettings>('/api/notifications/order-settings', {
        ...orderSettings,
        whitelist_chat_ids: parseChatIds(whitelistText),
        upgrade_chat_ids: parseChatIds(upgradeText),
      })
      setOrderSettings(res.data)
      setWhitelistText((res.data.whitelist_chat_ids ?? []).join('\n'))
      setUpgradeText((res.data.upgrade_chat_ids ?? []).join('\n'))
      toast.success(t('notifications.settingsSaved', 'Đã lưu cài đặt thông báo'))
    } catch (err) {
      toast.error(formatApiError(err, t('notifications.settingsSaveError', 'Không thể lưu cài đặt')))
    } finally {
      setSavingOrderSettings(false)
    }
  }

  const toggleUser = (userId: number) => {
    setSelectedUserIds(prev => {
      const next = new Set(prev)
      next.has(userId) ? next.delete(userId) : next.add(userId)
      return next
    })
  }

  const userName = (u: BotUser) =>
    u.username ? `@${u.username}` : [u.first_name, u.last_name].filter(Boolean).join(' ') || `#${u.telegram_user_id}`

  return (
    <div className="notifications-page">
      <PageHeader
        title={t('nav.notifications', 'Thông báo')}
        actions={
          <Button
            variant="secondary"
            tone="ghost"
            size="sm"
            iconLeft={<RefreshCw size={14} />}
            onClick={() => { fetchOrderSettings(); if (audienceMode === 'specific') fetchUsers() }}
          >
            {t('common.refresh', 'Làm mới')}
          </Button>
        }
      />

      <Tabs
        tabs={[
          {
            key: 'broadcast',
            label: t('notifications.broadcastTab', 'Phát tin'),
            panel: (
              <div className="notifications-page__broadcast">
                {/* Message compose */}
                <div className="notifications-page__compose-card">
                  <h3 className="notifications-page__section-title">
                    <Send size={14} />
                    {t('notifications.compose', 'Soạn tin nhắn')}
                  </h3>

                  <FormField label={t('notifications.message', 'Nội dung')} htmlFor="notif-msg">
                    <Textarea
                      id="notif-msg"
                      value={message}
                      onChange={e => setMessage(e.target.value)}
                      placeholder={t('notifications.messagePlaceholder', 'Nhập nội dung thông báo...')}
                      rows={5}
                      autoResize
                    />
                  </FormField>
                  <div className="notifications-page__char-count">
                    {message.length} {t('notifications.chars', 'ký tự')}
                  </div>

                  {/* Audience selector */}
                  <div className="notifications-page__audience">
                    <h4 className="notifications-page__audience-title">
                      <Users size={13} />
                      {t('notifications.audience', 'Đối tượng nhận')}
                    </h4>
                    <div className="notifications-page__audience-options">
                      {(['all', 'active', 'specific'] as AudienceMode[]).map(mode => (
                        <label key={mode} className={`notifications-page__audience-option ${audienceMode === mode ? 'notifications-page__audience-option--selected' : ''}`}>
                          <input
                            type="radio"
                            name="audience"
                            value={mode}
                            checked={audienceMode === mode}
                            onChange={() => setAudienceMode(mode)}
                          />
                          <span>{t(`notifications.audience_${mode}`, mode === 'all' ? 'Tất cả' : mode === 'active' ? 'Đang hoạt động' : 'Chọn cụ thể')}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Specific user selector */}
                  {audienceMode === 'specific' && (
                    <div className="notifications-page__user-list">
                      {loadingUsers ? (
                        <div className="notifications-page__user-skel">
                          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="line" height={32} />)}
                        </div>
                      ) : (
                        <>
                          <div className="notifications-page__user-list-header">
                            <span>{t('notifications.userListTitle', `${users.length} người dùng`)}</span>
                            <div className="notifications-page__user-list-actions">
                              <Button variant="secondary" tone="ghost" size="sm" onClick={() => setSelectedUserIds(new Set(users.map(u => u.telegram_user_id)))}>
                                {t('notifications.selectAll', 'Chọn tất cả')}
                              </Button>
                              <Button variant="secondary" tone="ghost" size="sm" onClick={() => setSelectedUserIds(new Set())}>
                                {t('notifications.deselectAll', 'Bỏ chọn')}
                              </Button>
                            </div>
                          </div>
                          <div className="notifications-page__user-rows">
                            {users.map(u => (
                              <label
                                key={u.telegram_user_id}
                                className={`notifications-page__user-row ${selectedUserIds.has(u.telegram_user_id) ? 'notifications-page__user-row--selected' : ''}`}
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedUserIds.has(u.telegram_user_id)}
                                  onChange={() => toggleUser(u.telegram_user_id)}
                                />
                                <span className="notifications-page__user-name">{userName(u)}</span>
                                <Badge variant={u.is_active ? 'success' : 'neutral'} size="sm">
                                  {u.is_active ? t('products.active', 'HĐ') : t('products.inactive', 'Tắt')}
                                </Badge>
                              </label>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  <div className="notifications-page__send-footer">
                    {audienceMode === 'specific' && selectedUserIds.size > 0 && (
                      <span className="notifications-page__selected-count">
                        {t('notifications.selectedUsers', `${selectedUserIds.size} người được chọn`)}
                      </span>
                    )}
                    <Button
                      variant="primary"
                      size="sm"
                      iconLeft={<Send size={14} />}
                      loading={sending}
                      onClick={handleSend}
                    >
                      {t('notifications.send', 'Gửi thông báo')}
                    </Button>
                  </div>
                </div>

                {/* Result */}
                {sendResult && (
                  <div className={`notifications-page__result ${sendResult.success ? 'notifications-page__result--success' : 'notifications-page__result--error'}`}>
                    {sendResult.success ? <CheckCircle size={16} /> : <XCircle size={16} />}
                    <span>
                      {t('notifications.result', `Gửi thành công: ${sendResult.successful}/${sendResult.total}`)}
                      {sendResult.failed > 0 && ` · ${t('notifications.failed', `Thất bại: ${sendResult.failed}`)}`}
                    </span>
                  </div>
                )}
              </div>
            ),
          },
          {
            key: 'order-alerts',
            label: t('notifications.orderAlertsTab', 'Cảnh báo đơn hàng'),
            panel: (
              <div className="notifications-page__order-settings">
                <div className="notifications-page__compose-card">
                  <h3 className="notifications-page__section-title">
                    <Bell size={14} />
                    {t('notifications.orderSettings', 'Cài đặt thông báo đơn hàng')}
                  </h3>

                  {loadingOrderSettings ? (
                    <div className="notifications-page__user-skel">
                      {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="line" height={36} />)}
                    </div>
                  ) : orderSettings ? (
                    <div className="notifications-page__order-form">
                      <div className="notifications-page__switch-row">
                        <Switch
                          checked={orderSettings.order_notify_enabled}
                          onChange={v => setOrderSettings(s => s ? { ...s, order_notify_enabled: v } : s)}
                          label={t('notifications.enableNotify', 'Bật thông báo đơn hàng')}
                        />
                      </div>
                      <div className="notifications-page__switch-row">
                        <Switch
                          checked={orderSettings.order_notify_on_created}
                          onChange={v => setOrderSettings(s => s ? { ...s, order_notify_on_created: v } : s)}
                          label={t('notifications.notifyOnCreated', 'Thông báo khi đơn mới được tạo')}
                        />
                      </div>
                      <div className="notifications-page__switch-row">
                        <Switch
                          checked={orderSettings.order_notify_on_paid}
                          onChange={v => setOrderSettings(s => s ? { ...s, order_notify_on_paid: v } : s)}
                          label={t('notifications.notifyOnPaid', 'Thông báo khi đơn được thanh toán')}
                        />
                      </div>

                      <FormField
                        label={t('notifications.whitelistChatIds', 'Chat ID nhận thông báo đơn hàng')}
                        htmlFor="notif-whitelist"
                        helperText={t('notifications.chatIdsHint', 'Mỗi dòng một ID. Dạng: -1001234 hoặc -100123:456')}
                      >
                        <Textarea
                          id="notif-whitelist"
                          value={whitelistText}
                          onChange={e => setWhitelistText(e.target.value)}
                          placeholder="-1001234567890"
                          rows={3}
                        />
                      </FormField>

                      <FormField
                        label={t('notifications.upgradeChatIds', 'Chat ID nhận thông báo nâng cấp')}
                        htmlFor="notif-upgrade"
                        helperText={t('notifications.chatIdsHint', 'Mỗi dòng một ID')}
                      >
                        <Textarea
                          id="notif-upgrade"
                          value={upgradeText}
                          onChange={e => setUpgradeText(e.target.value)}
                          placeholder="-1001234567890"
                          rows={3}
                        />
                      </FormField>

                      <div className="notifications-page__send-footer">
                        <Button
                          variant="primary"
                          size="sm"
                          loading={savingOrderSettings}
                          onClick={handleSaveOrderSettings}
                        >
                          {t('common.save', 'Lưu cài đặt')}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button variant="secondary" size="sm" onClick={fetchOrderSettings}>
                      {t('common.retry', 'Thử lại')}
                    </Button>
                  )}
                </div>
              </div>
            ),
          },
        ]}
        variant="underline"
        size="md"
      />
    </div>
  )
}
