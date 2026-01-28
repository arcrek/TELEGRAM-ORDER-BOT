/**
 * Image of the Day settings page (hidden from navbar).
 */
import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Loader, Save, Image as ImageIcon } from 'lucide-react'
import './IotdPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface IotdResponse {
  image_url: string | null
}

export function IotdPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [imageUrl, setImageUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const previewUrl = useMemo(() => imageUrl.trim(), [imageUrl])

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<IotdResponse>(`${API_BASE_URL}/api/iotd`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setImageUrl(response.data.image_url || '')
    } catch (e: any) {
      console.error('Failed to load IOTD config', e)
      setError(e.response?.data?.detail || 'Failed to load IOTD config')
    } finally {
      setLoading(false)
    }
  }

  const saveConfig = async () => {
    setSaving(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      const trimmed = imageUrl.trim()
      await axios.put(
        `${API_BASE_URL}/api/iotd`,
        { image_url: trimmed ? trimmed : null },
        { headers: { Authorization: `Bearer ${token}` } }
      )
    } catch (e: any) {
      console.error('Failed to save IOTD config', e)
      setError(e.response?.data?.detail || 'Failed to save IOTD config')
      return
    } finally {
      setSaving(false)
    }
    await fetchConfig()
  }

  return (
    <div className="iotd-page">
      <div className="iotd-header">
        <div>
          <h1>Image of the Day</h1>
          <p>Configure the image URL shown on the Statistics dashboard.</p>
        </div>
      </div>

      <Card className="iotd-card">
        {loading ? (
          <div className="iotd-loading">
            <Loader size={24} className="spinning" />
            <span>Loading...</span>
          </div>
        ) : (
          <>
            {error && <div className="iotd-error">{error}</div>}

            <div className="iotd-form">
              <label className="iotd-label">Image URL</label>
              <input
                className="iotd-input"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="https://example.com/image.jpg"
                disabled={saving}
              />
              <div className="iotd-actions">
                <Button variant="primary" onClick={saveConfig} disabled={saving}>
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
                <Button variant="outline" onClick={fetchConfig} disabled={saving}>
                  Reload
                </Button>
              </div>
            </div>

            <div className="iotd-preview">
              <div className="iotd-preview-title">
                <ImageIcon size={18} />
                <span>Preview</span>
              </div>
              <div className="iotd-preview-frame">
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="Image of the Day preview"
                    onError={() => setError('Preview failed to load (check the URL)')}
                  />
                ) : (
                  <div className="iotd-preview-empty">No image URL set</div>
                )}
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

