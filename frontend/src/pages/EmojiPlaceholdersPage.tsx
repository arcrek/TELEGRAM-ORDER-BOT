import { useEffect, useState } from 'react'
import { Plus, Trash2, Copy, Check, RefreshCw, Smile } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { Input } from '../shared/components/Input'
import { Badge } from '../shared/components/Badge'
import { Table, type ColumnDef } from '../shared/components/Table'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import { EmojiPreview, type EmojiUnit } from '../shared/components/EmojiPreview'
import './EmojiPlaceholdersPage.css'

interface EmojiPlaceholder {
  id: number
  name: string
  configured: boolean
  raw_text: string | null
  token: string
  units: EmojiUnit[]
}

function CopyableCode({ text, ms = 1500 }: { text: string; ms?: number }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), ms)
    })
  }
  return (
    <div className="emoji-page__code-cell">
      <code className="emoji-page__code">{text}</code>
      <button
        type="button"
        className={`emoji-page__copy-btn ${copied ? 'emoji-page__copy-btn--copied' : ''}`}
        onClick={copy}
        aria-label={copied ? 'Đã sao chép' : 'Sao chép'}
      >
        {copied ? <Check size={11} /> : <Copy size={11} />}
        {copied ? 'Đã chép' : 'Chép'}
      </button>
    </div>
  )
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

  const columns: ColumnDef<EmojiPlaceholder>[] = [
    {
      id: 'id',
      header: 'ID',
      mono: true,
      width: 56,
      cell: row => row.id,
    },
    {
      id: 'name',
      header: t('emoji.colName', 'Name'),
      cell: row => row.name,
    },
    {
      id: 'token',
      header: t('emoji.colToken', 'Token'),
      cell: row => <CopyableCode text={row.token} />,
    },
    {
      id: 'setup',
      header: t('emoji.colSetup', 'Setup command'),
      cell: row => <CopyableCode text={`/set_emo ${row.id}`} />,
    },
    {
      id: 'status',
      header: t('emoji.colStatus', 'Status'),
      width: 120,
      cell: row => (
        <Badge variant={row.configured ? 'success' : 'neutral'} size="sm">
          {row.configured ? t('emoji.configured', 'Configured') : t('emoji.emptyBadge', 'Empty')}
        </Badge>
      ),
    },
    {
      id: 'preview',
      header: t('emoji.colPreview', 'Preview'),
      cell: row => (
        <div className="emoji-page__preview-cell">
          {row.configured && row.units && row.units.length > 0
            ? <EmojiPreview units={row.units} />
            : <span className="emoji-page__no-preview">—</span>
          }
        </div>
      ),
    },
    {
      id: 'actions',
      header: '',
      width: 48,
      cell: row => (
        <div className="emoji-page__actions">
          <IconButton
            icon={<Trash2 size={14} />}
            aria-label={t('common.delete', 'Delete')}
            variant="destructive"
            size="sm"
            onClick={() => handleDelete(row.id)}
          />
        </div>
      ),
    },
  ]

  return (
    <div className="emoji-page">
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
        <div className="emoji-page__error" role="alert">{error}</div>
      )}

      <div className="emoji-page__create">
        <Input
          className="emoji-page__create-input"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder={t('emoji.namePlaceholder', 'Name (e.g. Header banner)')}
          onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
          disabled={creating}
          size="sm"
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

      <div className="emoji-page__table-card">
        <Table<EmojiPlaceholder>
          columns={columns}
          data={items}
          keyFn={row => String(row.id)}
          loading={loading}
          skeletonRows={4}
          emptyIcon={<Smile size={40} />}
          emptyTitle={t('emoji.emptyTitle', 'No placeholders yet')}
          emptyDescription={t('emoji.emptyDesc', 'Create a placeholder above, then use /set_emo in the bot to assign emojis.')}
        />
      </div>
    </div>
  )
}
