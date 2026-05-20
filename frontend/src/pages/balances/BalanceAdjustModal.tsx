import { useState, useEffect } from 'react'
import { Modal } from '../../shared/components/Modal'
import { Button } from '../../shared/components/Button'
import { Radio } from '../../shared/components/Radio'
import { FormField } from '../../shared/components/FormField'
import { Textarea } from '../../shared/components/Textarea'
import { useToast } from '../../shared/components/Toast'
import { apiClient, formatApiError } from '../../shared/lib/api'
import type { BalanceUserRow, AdjustAction, BalanceAdjustResponse } from './types'

interface BalanceAdjustModalProps {
  open: boolean
  onClose: () => void
  user: BalanceUserRow | null
  onSuccess: (botUserId: string, newBalance: number) => void
}

export function BalanceAdjustModal({ open, onClose, user, onSuccess }: BalanceAdjustModalProps) {
  const { toast } = useToast()

  const [action, setAction] = useState<AdjustAction>('add')
  const [amountInput, setAmountInput] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Reset form when opening for a new user
  useEffect(() => {
    if (open) {
      setAction('add')
      setAmountInput('')
      setReason('')
      setError(null)
    }
  }, [open, user?.bot_user_id])

  const formatAmount = (raw: string): number => {
    return parseInt(raw.replace(/[^0-9]/g, ''), 10) || 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return

    const amount = formatAmount(amountInput)
    if (amount <= 0 && action !== 'set') {
      setError('Số tiền phải lớn hơn 0')
      return
    }
    if (amount < 0) {
      setError('Số tiền không hợp lệ')
      return
    }
    if (!reason.trim()) {
      setError('Lý do là bắt buộc')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const res = await apiClient.post<BalanceAdjustResponse>(
        `/api/balances/${user.bot_user_id}/adjust`,
        { action, amount, reason: reason.trim() },
      )
      toast.success(
        `Cập nhật số dư thành công. Số dư mới: ${res.data.new_balance.toLocaleString('vi-VN')} VND`,
      )
      onSuccess(user.bot_user_id, res.data.new_balance)
      onClose()
    } catch (err) {
      setError(formatApiError(err, 'Không thể cập nhật số dư'))
    } finally {
      setSaving(false)
    }
  }

  const actionLabel: Record<AdjustAction, string> = {
    add: 'Thêm',
    subtract: 'Trừ',
    set: 'Đặt',
  }

  const displayName = user
    ? (user.username ? `@${user.username}` : [user.first_name, user.last_name].filter(Boolean).join(' ') || `#${user.telegram_user_id}`)
    : ''

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Điều chỉnh số dư"
      description={displayName ? `Người dùng: ${displayName}` : undefined}
      footer={
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="secondary" tone="ghost" size="sm" onClick={onClose} disabled={saving}>
            Huỷ
          </Button>
          <Button variant="primary" size="sm" type="submit" form="balance-adjust-form" loading={saving}>
            Xác nhận
          </Button>
        </div>
      }
    >
      <form id="balance-adjust-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {user && (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Số dư hiện tại:{' '}
            <strong style={{ color: 'var(--text-primary)' }}>
              {user.balance.toLocaleString('vi-VN')} VND
            </strong>
          </div>
        )}

        {error && (
          <div role="alert" style={{ color: 'var(--danger-500)', fontSize: 13 }}>
            {error}
          </div>
        )}

        <FormField label="Loại điều chỉnh">
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {(['add', 'subtract', 'set'] as AdjustAction[]).map(a => (
              <Radio
                key={a}
                value={a}
                checked={action === a}
                onChange={v => setAction(v as AdjustAction)}
                label={actionLabel[a]}
                name="adjust-action"
              />
            ))}
          </div>
        </FormField>

        <FormField label="Số tiền (VND)">
          <input
            type="text"
            inputMode="numeric"
            className="input-field__input"
            value={amountInput}
            onChange={e => setAmountInput(e.target.value.replace(/[^0-9]/g, ''))}
            onBlur={() => {
              const n = formatAmount(amountInput)
              if (n > 0) setAmountInput(n.toLocaleString('vi-VN'))
            }}
            onFocus={() => {
              const n = formatAmount(amountInput)
              setAmountInput(n > 0 ? String(n) : '')
            }}
            placeholder="0"
            style={{
              width: '100%',
              padding: '8px 12px',
              background: 'var(--bg-sunken)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 6,
              color: 'var(--text-primary)',
              fontSize: 14,
              outline: 'none',
            }}
          />
        </FormField>

        <FormField label="Lý do">
          <Textarea
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Nhập lý do điều chỉnh số dư..."
            rows={3}
          />
        </FormField>
      </form>
    </Modal>
  )
}
