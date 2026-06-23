import { useEffect, useState } from 'react'
import { Plus, Trash2, Copy, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import { EmojiPreview, type EmojiUnit } from '../shared/components/EmojiPreview'

interface EmojiPlaceholder {
  id: number
  name: string
  configured: boolean
  raw_text: string | null
  token: string
  units: EmojiUnit[]
}

export function EmojiPlaceholdersPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [items, setItems] = useState<EmojiPlaceholder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const fetchItems = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<EmojiPlaceholder[]>('/api/emoji-placeholders')
      setItems(res.data)
    } catch (err) {
      setError(formatApiError(err, t('emoji.loadError', 'Could not load placeholders')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await apiClient.post('/api/emoji-placeholders', { name: newName.trim() })
      setNewName('')
      await fetchItems()
      toast.success(t('emoji.created', 'Placeholder created'))
    } catch (err) {
      toast.error(formatApiError(err, t('emoji.saveError', 'Could not save')))
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm(t('emoji.deleteConfirm', 'Delete this placeholder?'))) return
    try {
      await apiClient.delete(`/api/emoji-placeholders/${id}`)
      await fetchItems()
      toast.success(t('emoji.deleted', 'Placeholder deleted'))
    } catch (err) {
      toast.error(formatApiError(err, t('emoji.saveError', 'Could not save')))
    }
  }

  const copyToken = (token: string) => {
    navigator.clipboard?.writeText(token)
    toast.success(t('emoji.copied', 'Token copied'))
  }

  return (
    <div className="emoji-placeholders-page">
      <PageHeader
        title={t('emoji.title', 'Emoji Placeholders')}
        description={t('emoji.description', 'Manage custom emoji placeholders for the bot')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Refresh')}
            variant="ghost"
            size="sm"
            onClick={fetchItems}
            disabled={loading}
          />
        }
      />

      {error && (
        <div className="emoji-placeholders-page__error" role="alert">{error}</div>
      )}

      <div className="emoji-placeholders-page__create">
        <input
          className="emoji-placeholders-page__input"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder={t('emoji.namePlaceholder', 'Name (e.g. Header banner)')}
          onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
          disabled={creating}
        />
        <Button
          variant="primary"
          size="sm"
          iconLeft={<Plus size={14} />}
          onClick={handleCreate}
          loading={creating}
          disabled={!newName.trim()}
        >
          {t('emoji.create', 'New placeholder')}
        </Button>
      </div>

      {loading ? (
        <div className="emoji-placeholders-page__loading" aria-live="polite">…</div>
      ) : items.length === 0 ? (
        <div className="emoji-placeholders-page__empty">
          {t('emoji.empty', 'No placeholders yet. Create one above.')}
        </div>
      ) : (
        <div className="emoji-placeholders-page__table-wrap">
          <table className="emoji-placeholders-page__table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t('emoji.colName', 'Name')}</th>
                <th>{t('emoji.colToken', 'Token')}</th>
                <th>{t('emoji.colStatus', 'Status')}</th>
                <th>{t('emoji.colPreview', 'Preview')}</th>
                <th aria-label={t('common.actions', 'Actions')}></th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.name}</td>
                  <td className="emoji-placeholders-page__token-cell">
                    <code className="emoji-placeholders-page__token">{item.token}</code>
                    <IconButton
                      icon={<Copy size={12} />}
                      aria-label={t('emoji.copyToken', 'Copy token')}
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToken(item.token)}
                    />
                  </td>
                  <td>
                    <span
                      className={`emoji-placeholders-page__badge ${item.configured ? 'emoji-placeholders-page__badge--configured' : 'emoji-placeholders-page__badge--empty'}`}
                    >
                      {item.configured ? `${t('emoji.configured', 'Configured')} ✓` : t('emoji.emptyBadge', 'Empty')}
                    </span>
                  </td>
                  <td className="emoji-placeholders-page__preview-cell">
                    {item.configured && item.units && item.units.length > 0
                      ? <EmojiPreview units={item.units} />
                      : (
                        <span
                          className="emoji-placeholders-page__hint"
                          title={t('emoji.setHint', 'Run /set_emo {id} in the bot and send your premium emoji').replace('{id}', String(item.id))}
                        >
                          — <em>{t('emoji.setHint', 'Run /set_emo {id} in the bot').replace('{id}', String(item.id))}</em>
                        </span>
                      )
                    }
                  </td>
                  <td>
                    <IconButton
                      icon={<Trash2 size={14} />}
                      aria-label={t('common.delete', 'Delete')}
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(item.id)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
