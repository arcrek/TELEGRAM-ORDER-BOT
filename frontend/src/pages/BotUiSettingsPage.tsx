import { useEffect, useState } from 'react'
import axios from 'axios'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Loader, Save } from 'lucide-react'
import './BotUiSettingsPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface BotUiSettingsResponse {
  product_choose_text: string | null
  variation_choose_text: string | null
}

export function BotUiSettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [productChooseText, setProductChooseText] = useState('')
  const [variationChooseText, setVariationChooseText] = useState('')

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<BotUiSettingsResponse>(`${API_BASE_URL}/api/bot-ui-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setProductChooseText(response.data.product_choose_text || '')
      setVariationChooseText(response.data.variation_choose_text || '')
    } catch (e: any) {
      console.error('Failed to load bot UI settings', e)
      setError(e.response?.data?.detail || 'Failed to load bot UI settings')
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async () => {
    setSaving(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API_BASE_URL}/api/bot-ui-settings`,
        {
          product_choose_text: productChooseText,
          variation_choose_text: variationChooseText,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )
    } catch (e: any) {
      console.error('Failed to save bot UI settings', e)
      setError(e.response?.data?.detail || 'Failed to save bot UI settings')
      return
    } finally {
      setSaving(false)
    }

    await fetchSettings()
  }

  return (
    <div className="bot-ui-settings-page">
      <div className="bot-ui-settings-header">
        <h1>Bot UI Settings</h1>
        <p>Customize prompt text shown before product and variation button selection.</p>
      </div>

      <Card className="bot-ui-settings-card">
        {loading ? (
          <div className="bot-ui-settings-loading">
            <Loader size={24} className="spinning" />
            <span>Loading...</span>
          </div>
        ) : (
          <>
            {error && <div className="bot-ui-settings-error">{error}</div>}

            <div className="bot-ui-settings-form">
              <label className="bot-ui-settings-label">Product choose text</label>
              <textarea
                className="bot-ui-settings-textarea"
                value={productChooseText}
                onChange={(e) => setProductChooseText(e.target.value)}
                placeholder="Choose a category to view packages"
                rows={4}
                disabled={saving}
              />

              <label className="bot-ui-settings-label">Variation choose text</label>
              <textarea
                className="bot-ui-settings-textarea"
                value={variationChooseText}
                onChange={(e) => setVariationChooseText(e.target.value)}
                placeholder="Choose a package"
                rows={4}
                disabled={saving}
              />

              <div className="bot-ui-settings-actions">
                <Button variant="primary" onClick={saveSettings} disabled={saving}>
                  {saving ? (
                    <>
                      <Loader size={16} className="spinning" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Save size={16} />
                      <span>Save</span>
                    </>
                  )}
                </Button>
                <Button variant="outline" onClick={fetchSettings} disabled={saving}>
                  Reload
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

