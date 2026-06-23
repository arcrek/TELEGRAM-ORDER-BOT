import { useState } from 'react'
import { apiClient } from '../lib/api'

export interface EmojiUnit {
  type: 'text' | 'emoji'
  value?: string | null
  emoji_id?: string | null
  fallback?: string | null
}

const API_BASE = apiClient.defaults.baseURL ?? ''

function EmojiImg({ emojiId, fallback }: { emojiId: string; fallback: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <span className="emoji-preview__fallback">{fallback}</span>
  return (
    <img
      src={`${API_BASE}/api/emoji-thumbnails/${emojiId}`}
      alt={fallback}
      className="emoji-preview__img"
      width={20}
      height={20}
      onError={() => setFailed(true)}
    />
  )
}

export function EmojiPreview({ units }: { units: EmojiUnit[] }) {
  return (
    <span className="emoji-preview">
      {units.map((u, i) =>
        u.type === 'emoji' && u.emoji_id ? (
          <EmojiImg key={i} emojiId={u.emoji_id} fallback={u.fallback ?? ''} />
        ) : (
          <span key={i}>{u.value ?? ''}</span>
        ),
      )}
    </span>
  )
}
