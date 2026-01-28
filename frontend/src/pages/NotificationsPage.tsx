/**
 * Notifications page for sending custom notifications to bot users.
 * Premium Dark SaaS Design System.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { 
  Send, 
  Users, 
  UserCheck,
  CheckCircle,
  XCircle,
  Loader
} from 'lucide-react'
import axios from 'axios'
import './NotificationsPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface BotUser {
  id: string
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  has_started: boolean
  started_at: string | null
  is_active: boolean
}

interface NotificationResult {
  success: boolean
  total: number
  successful: number
  failed: number
  details?: Array<{
    success: boolean
    telegram_user_id: number
    error?: string
  }>
}

interface OrderNotificationSettings {
  order_notify_enabled: boolean
  order_notify_on_created: boolean
  order_notify_on_paid: boolean
  whitelist_chat_ids: number[]
}

export function NotificationsPage() {
  const [message, setMessage] = useState('')
  const [users, setUsers] = useState<BotUser[]>([])
  const [selectedUsers, setSelectedUsers] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingUsers, setLoadingUsers] = useState(false)
  const [result, setResult] = useState<NotificationResult | null>(null)
  const [activeOnly, setActiveOnly] = useState(false)
  const [sendToAll, setSendToAll] = useState(true)

  const [orderSettings, setOrderSettings] = useState<OrderNotificationSettings | null>(null)
  const [orderSettingsText, setOrderSettingsText] = useState('')
  const [loadingOrderSettings, setLoadingOrderSettings] = useState(false)
  const [savingOrderSettings, setSavingOrderSettings] = useState(false)
  const [testingOrderSettings, setTestingOrderSettings] = useState(false)

  useEffect(() => {
    fetchUsers()
  }, [activeOnly])

  useEffect(() => {
    fetchOrderSettings()
  }, [])

  const fetchUsers = async () => {
    setLoadingUsers(true)
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get(`${API_BASE_URL}/api/notifications/users`, {
        params: { active_only: activeOnly },
        headers: { Authorization: `Bearer ${token}` }
      })
      setUsers(response.data)
    } catch (error: any) {
      console.error('Error fetching users:', error)
      alert('Failed to load users')
    } finally {
      setLoadingUsers(false)
    }
  }

  const fetchOrderSettings = async () => {
    setLoadingOrderSettings(true)
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get(`${API_BASE_URL}/api/notifications/order-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const settings: OrderNotificationSettings = response.data
      setOrderSettings(settings)
      setOrderSettingsText((settings.whitelist_chat_ids || []).join('\n'))
    } catch (error: any) {
      console.error('Error fetching order notification settings:', error)
      // Don't block the rest of the page
    } finally {
      setLoadingOrderSettings(false)
    }
  }

  const parseChatIds = (text: string): number[] => {
    const parts = text.split(/[\s,]+/).map(p => p.trim()).filter(Boolean)
    const ids: number[] = []
    const seen = new Set<number>()
    for (const part of parts) {
      const n = Number(part)
      if (!Number.isFinite(n) || !Number.isInteger(n)) continue
      if (!seen.has(n)) {
        seen.add(n)
        ids.push(n)
      }
    }
    return ids
  }

  const handleSaveOrderSettings = async () => {
    if (!orderSettings) return
    setSavingOrderSettings(true)
    try {
      const token = localStorage.getItem('token')
      const whitelist_chat_ids = parseChatIds(orderSettingsText)

      const response = await axios.put(
        `${API_BASE_URL}/api/notifications/order-settings`,
        {
          order_notify_enabled: orderSettings.order_notify_enabled,
          order_notify_on_created: orderSettings.order_notify_on_created,
          order_notify_on_paid: orderSettings.order_notify_on_paid,
          whitelist_chat_ids
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      const updated: OrderNotificationSettings = response.data
      setOrderSettings(updated)
      setOrderSettingsText((updated.whitelist_chat_ids || []).join('\n'))
      alert('Order notification settings saved')
    } catch (error: any) {
      console.error('Error saving order notification settings:', error)
      alert(error.response?.data?.detail || 'Failed to save order notification settings')
    } finally {
      setSavingOrderSettings(false)
    }
  }

  const handleTestOrderSettings = async () => {
    setTestingOrderSettings(true)
    try {
      const token = localStorage.getItem('token')
      const response = await axios.post(
        `${API_BASE_URL}/api/notifications/order-settings/test`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setResult(response.data)
    } catch (error: any) {
      console.error('Error sending test order notification:', error)
      alert(error.response?.data?.detail || 'Failed to send test notification')
    } finally {
      setTestingOrderSettings(false)
    }
  }

  const handleSendNotification = async (targetActiveOnly: boolean = false) => {
    if (!message.trim()) {
      alert('Please enter a message')
      return
    }

    setLoading(true)
    setResult(null)

    try {
      const token = localStorage.getItem('token')
      let response

      if (targetActiveOnly) {
        response = await axios.post(
          `${API_BASE_URL}/api/notifications/send/active`,
          { message },
          { headers: { Authorization: `Bearer ${token}` } }
        )
      } else if (sendToAll || selectedUsers.length === 0) {
        response = await axios.post(
          `${API_BASE_URL}/api/notifications/send`,
          { message },
          { headers: { Authorization: `Bearer ${token}` } }
        )
      } else {
        response = await axios.post(
          `${API_BASE_URL}/api/notifications/send`,
          { message, user_ids: selectedUsers },
          { headers: { Authorization: `Bearer ${token}` } }
        )
      }

      setResult(response.data)
      
      if (response.data.success) {
        setMessage('')
        setSelectedUsers([])
      }
    } catch (error: any) {
      console.error('Error sending notification:', error)
      alert(error.response?.data?.detail || 'Failed to send notification')
    } finally {
      setLoading(false)
    }
  }

  const toggleUserSelection = (userId: number) => {
    setSelectedUsers(prev => 
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    )
  }

  const selectAllUsers = () => {
    setSelectedUsers(users.map(u => u.telegram_user_id))
  }

  const deselectAllUsers = () => {
    setSelectedUsers([])
  }

  return (
    <div className="notifications-page">
      <div className="page-header">
        <h1>Notifications</h1>
        <p>Send custom notifications to bot users</p>
      </div>

      <div className="notifications-content">
        <Card className="notification-composer">
          <h2>Order Notifications</h2>
          <p style={{ opacity: 0.8, marginTop: -8 }}>
            Send automatic order alerts to whitelisted Telegram chat IDs.
          </p>

          {loadingOrderSettings ? (
            <div className="loading-state">
              <Loader size={24} className="spinning" />
              <span>Loading order notification settings...</span>
            </div>
          ) : !orderSettings ? (
            <div className="empty-state">
              <p>Order notification settings are not available.</p>
              <Button variant="outline" onClick={fetchOrderSettings} disabled={loadingOrderSettings}>
                Retry
              </Button>
            </div>
          ) : (
            <>
              <div className="send-options">
                <div className="option-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={orderSettings.order_notify_enabled}
                      onChange={(e) =>
                        setOrderSettings({ ...orderSettings, order_notify_enabled: e.target.checked })
                      }
                      disabled={savingOrderSettings}
                    />
                    <span>Enable order notifications</span>
                  </label>
                </div>
              </div>

              <div className="send-options">
                <div className="option-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={orderSettings.order_notify_on_created}
                      onChange={(e) =>
                        setOrderSettings({ ...orderSettings, order_notify_on_created: e.target.checked })
                      }
                      disabled={savingOrderSettings}
                    />
                    <span>Notify on order created</span>
                  </label>
                </div>
                <div className="option-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={orderSettings.order_notify_on_paid}
                      onChange={(e) =>
                        setOrderSettings({ ...orderSettings, order_notify_on_paid: e.target.checked })
                      }
                      disabled={savingOrderSettings}
                    />
                    <span>Notify on order paid</span>
                  </label>
                </div>
              </div>

              <div className="form-group">
                <label>Whitelisted chat IDs</label>
                <textarea
                  className="message-input"
                  value={orderSettingsText}
                  onChange={(e) => setOrderSettingsText(e.target.value)}
                  placeholder={"Example:\n123456789\n-1001234567890"}
                  rows={5}
                  disabled={savingOrderSettings}
                />
                <div className="char-count">{parseChatIds(orderSettingsText).length} IDs</div>
              </div>

              <div className="action-buttons">
                <Button
                  variant="primary"
                  onClick={handleSaveOrderSettings}
                  disabled={savingOrderSettings}
                >
                  {savingOrderSettings ? (
                    <>
                      <Loader size={16} className="spinning" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Settings</span>
                  )}
                </Button>

                <Button
                  variant="secondary"
                  onClick={handleTestOrderSettings}
                  disabled={testingOrderSettings || savingOrderSettings}
                >
                  {testingOrderSettings ? (
                    <>
                      <Loader size={16} className="spinning" />
                      <span>Sending test...</span>
                    </>
                  ) : (
                    <span>Send Test</span>
                  )}
                </Button>
              </div>
            </>
          )}
        </Card>

        <Card className="notification-composer">
          <h2>Compose Notification</h2>
          
          <div className="form-group">
            <label>Message</label>
            <textarea
              className="message-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Enter your notification message..."
              rows={6}
            />
            <div className="char-count">{message.length} characters</div>
          </div>

          <div className="send-options">
            <div className="option-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={sendToAll}
                  onChange={(e) => {
                    setSendToAll(e.target.checked)
                    if (e.target.checked) {
                      setSelectedUsers([])
                    }
                  }}
                />
                <span>Send to all users</span>
              </label>
            </div>

            <div className="action-buttons">
              <Button
                variant="primary"
                onClick={() => handleSendNotification(false)}
                disabled={loading || !message.trim()}
              >
                {loading ? (
                  <>
                    <Loader size={16} className="spinning" />
                    <span>Sending...</span>
                  </>
                ) : (
                  <>
                    <Send size={16} />
                    <span>Send to All</span>
                  </>
                )}
              </Button>

              <Button
                variant="secondary"
                onClick={() => handleSendNotification(true)}
                disabled={loading || !message.trim()}
              >
                {loading ? (
                  <>
                    <Loader size={16} className="spinning" />
                    <span>Sending...</span>
                  </>
                ) : (
                  <>
                    <UserCheck size={16} />
                    <span>Send to Active Only</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>

        <div className="users-section">
          <Card>
            <div className="users-header">
              <h2>Select Users</h2>
              <div className="users-controls">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={activeOnly}
                    onChange={(e) => setActiveOnly(e.target.checked)}
                  />
                  <span>Active users only</span>
                </label>
                {!sendToAll && (
                  <>
                    <Button variant="outline" size="small" onClick={selectAllUsers}>
                      Select All
                    </Button>
                    <Button variant="outline" size="small" onClick={deselectAllUsers}>
                      Deselect All
                    </Button>
                  </>
                )}
              </div>
            </div>

            {loadingUsers ? (
              <div className="loading-state">
                <Loader size={24} className="spinning" />
                <span>Loading users...</span>
              </div>
            ) : users.length === 0 ? (
              <div className="empty-state">
                <Users size={48} />
                <p>No users found</p>
              </div>
            ) : (
              <>
                <div className="users-list">
                  {users.map(user => (
                    <div
                      key={user.id}
                      className={`user-item ${selectedUsers.includes(user.telegram_user_id) ? 'selected' : ''} ${!user.is_active ? 'inactive' : ''}`}
                      onClick={() => !sendToAll && toggleUserSelection(user.telegram_user_id)}
                    >
                      <div className="user-info">
                        <div className="user-name">
                          {user.first_name} {user.last_name || ''}
                          {user.username && <span className="username">@{user.username}</span>}
                        </div>
                        <div className="user-meta">
                          <span>ID: {user.telegram_user_id}</span>
                          {user.is_active ? (
                            <span className="badge active">Active</span>
                          ) : (
                            <span className="badge inactive">Inactive</span>
                          )}
                        </div>
                      </div>
                      {!sendToAll && (
                        <div className="user-checkbox">
                          <input
                            type="checkbox"
                            checked={selectedUsers.includes(user.telegram_user_id)}
                            onChange={() => toggleUserSelection(user.telegram_user_id)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {!sendToAll && selectedUsers.length > 0 && (
                  <div className="selected-count">
                    {selectedUsers.length} user{selectedUsers.length !== 1 ? 's' : ''} selected
                    <Button
                      variant="primary"
                      size="small"
                      onClick={() => handleSendNotification(false)}
                      disabled={loading || !message.trim()}
                    >
                      <Send size={14} />
                      <span>Send to Selected</span>
                    </Button>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>

        {result && (
          <Card className="result-card">
            <h2>Delivery Status</h2>
            <div className="result-stats">
              <div className="stat-item">
                <span className="stat-label">Total</span>
                <span className="stat-value">{result.total}</span>
              </div>
              <div className="stat-item success">
                <CheckCircle size={20} />
                <span className="stat-label">Successful</span>
                <span className="stat-value">{result.successful}</span>
              </div>
              <div className="stat-item failed">
                <XCircle size={20} />
                <span className="stat-label">Failed</span>
                <span className="stat-value">{result.failed}</span>
              </div>
            </div>
            {result.details && result.details.length > 0 && (
              <div className="result-details">
                <h3>Details</h3>
                <div className="details-list">
                  {result.details.slice(0, 10).map((detail, idx) => (
                    <div key={idx} className={`detail-item ${detail.success ? 'success' : 'failed'}`}>
                      <span>User {detail.telegram_user_id}</span>
                      {detail.success ? (
                        <CheckCircle size={16} />
                      ) : (
                        <span className="error-text">{detail.error}</span>
                      )}
                    </div>
                  ))}
                  {result.details.length > 10 && (
                    <div className="detail-item">
                      <span>... and {result.details.length - 10} more</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}

