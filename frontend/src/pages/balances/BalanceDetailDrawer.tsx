import { useState, useEffect, useCallback, useMemo } from 'react'
import { Modal } from '../../shared/components/Modal'
import { Button } from '../../shared/components/Button'
import { Tabs } from '../../shared/components/Tabs'
import { Table, type ColumnDef } from '../../shared/components/Table'
import { Badge } from '../../shared/components/Badge'
import { Pagination } from '../../shared/components/Pagination'
import { Spinner } from '../../shared/components/Spinner'
import { apiClient, formatApiError } from '../../shared/lib/api'
import { useFormat } from '../../shared/lib/format'
import type { BalanceUserRow, BalanceUserDetail, BalanceTxRow, TopupRow, ApiTokenResponse } from './types'

interface BalanceDetailDrawerProps {
  open: boolean
  onClose: () => void
  user: BalanceUserRow | null
}

const TX_KIND_LABEL: Record<string, string> = {
  topup: 'Nạp tiền',
  order_payment: 'Thanh toán đơn',
  admin_add: 'Cộng (Admin)',
  admin_subtract: 'Trừ (Admin)',
  admin_set: 'Đặt (Admin)',
}

const TX_KIND_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'neutral'> = {
  topup: 'success',
  order_payment: 'danger',
  admin_add: 'success',
  admin_subtract: 'danger',
  admin_set: 'info',
}

const TOPUP_STATUS_LABEL: Record<string, string> = {
  pending: 'Chờ thanh toán',
  paid: 'Đã thanh toán',
  cancelled: 'Đã huỷ',
}

const TOPUP_STATUS_VARIANT: Record<string, 'success' | 'neutral' | 'warning'> = {
  pending: 'warning',
  paid: 'success',
  cancelled: 'neutral',
}

export function BalanceDetailDrawer({ open, onClose, user }: BalanceDetailDrawerProps) {
  const fmt = useFormat()

  const [detail, setDetail] = useState<BalanceUserDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [txPage, setTxPage] = useState(1)
  const [txPerPage] = useState(10)
  const [topupPage, setTopupPage] = useState(1)
  const [topupPerPage] = useState(10)

  // API token state (initially populated from the user prop; updated by generate/revoke)
  const [apiToken, setApiToken] = useState<string | null>(null)
  const [tokenLoading, setTokenLoading] = useState(false)
  const [tokenError, setTokenError] = useState<string | null>(null)
  const [copyFeedback, setCopyFeedback] = useState(false)

  // Sync token from user prop when drawer opens
  useEffect(() => {
    if (open && user) setApiToken(user.api_token ?? null)
    if (!open) { setApiToken(null); setTokenError(null) }
  }, [open, user?.bot_user_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerateToken = useCallback(async () => {
    if (!user) return
    setTokenLoading(true)
    setTokenError(null)
    try {
      const res = await apiClient.post<ApiTokenResponse>(`/api/balances/${user.bot_user_id}/api-token`)
      setApiToken(res.data.api_token)
    } catch (err) {
      setTokenError(formatApiError(err, 'Không thể tạo token'))
    } finally {
      setTokenLoading(false)
    }
  }, [user])

  const handleRevokeToken = useCallback(async () => {
    if (!user) return
    if (!window.confirm('Thu hồi token API? Token hiện tại sẽ lập tức vô hiệu.')) return
    setTokenLoading(true)
    setTokenError(null)
    try {
      await apiClient.delete(`/api/balances/${user.bot_user_id}/api-token`)
      setApiToken(null)
    } catch (err) {
      setTokenError(formatApiError(err, 'Không thể thu hồi token'))
    } finally {
      setTokenLoading(false)
    }
  }, [user])

  const handleCopyToken = useCallback(() => {
    if (!apiToken) return
    navigator.clipboard.writeText(apiToken).then(() => {
      setCopyFeedback(true)
      setTimeout(() => setCopyFeedback(false), 2000)
    })
  }, [apiToken])

  const fetchDetail = useCallback(async () => {
    if (!user) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<BalanceUserDetail>(`/api/balances/${user.bot_user_id}`, {
        params: {
          transactions_page: txPage,
          transactions_per_page: txPerPage,
          topups_page: topupPage,
          topups_per_page: topupPerPage,
        },
      })
      setDetail(res.data)
    } catch (err) {
      setError(formatApiError(err, 'Không thể tải chi tiết số dư'))
    } finally {
      setLoading(false)
    }
  }, [user, txPage, txPerPage, topupPage, topupPerPage])

  useEffect(() => {
    if (open && user) {
      setTxPage(1)
      setTopupPage(1)
      fetchDetail()
    }
    if (!open) {
      setDetail(null)
      setError(null)
    }
  }, [open, user?.bot_user_id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch when pagination changes
  useEffect(() => {
    if (open && user) fetchDetail()
  }, [txPage, topupPage, fetchDetail]) // eslint-disable-line react-hooks/exhaustive-deps

  const txColumns = useMemo<ColumnDef<BalanceTxRow>[]>(() => [
    {
      id: 'created_at',
      header: 'Thời gian',
      width: 150,
      cell: row => <span style={{ fontSize: 12 }}>{fmt.dateTime(row.created_at)}</span>,
    },
    {
      id: 'kind',
      header: 'Loại',
      width: 130,
      cell: row => (
        <Badge variant={TX_KIND_VARIANT[row.kind] ?? 'neutral'} size="sm">
          {TX_KIND_LABEL[row.kind] ?? row.kind}
        </Badge>
      ),
    },
    {
      id: 'amount',
      header: 'Số tiền',
      align: 'right',
      width: 120,
      cell: row => (
        <span style={{ color: row.amount >= 0 ? 'var(--success-500)' : 'var(--danger-500)' }}>
          {row.amount >= 0 ? '+' : ''}{row.amount.toLocaleString('vi-VN')}
        </span>
      ),
    },
    {
      id: 'balance_after',
      header: 'Số dư sau',
      align: 'right',
      width: 120,
      cell: row => row.balance_after.toLocaleString('vi-VN'),
    },
    {
      id: 'reference',
      header: 'Tham chiếu',
      cell: row => (
        <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
          {row.reference_id ?? (row.admin_username ? `Admin: ${row.admin_username}` : '—')}
        </span>
      ),
    },
    {
      id: 'reason',
      header: 'Lý do',
      cell: row => <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{row.reason ?? '—'}</span>,
    },
  ], [fmt])

  const topupColumns = useMemo<ColumnDef<TopupRow>[]>(() => [
    {
      id: 'created_at',
      header: 'Thời gian',
      width: 150,
      cell: row => <span style={{ fontSize: 12 }}>{fmt.dateTime(row.created_at)}</span>,
    },
    {
      id: 'amount',
      header: 'Số tiền',
      align: 'right',
      width: 120,
      cell: row => `${row.amount.toLocaleString('vi-VN')} VND`,
    },
    {
      id: 'status',
      header: 'Trạng thái',
      width: 140,
      cell: row => (
        <Badge variant={TOPUP_STATUS_VARIANT[row.status] ?? 'neutral'} size="sm">
          {TOPUP_STATUS_LABEL[row.status] ?? row.status}
        </Badge>
      ),
    },
    {
      id: 'payment_provider',
      header: 'Cổng thanh toán',
      cell: row => row.payment_provider ?? '—',
    },
    {
      id: 'id',
      header: 'Mã nạp tiền',
      cell: row => <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{row.id}</span>,
    },
  ], [fmt])

  const displayName = user
    ? (user.username ? `@${user.username}` : [user.first_name, user.last_name].filter(Boolean).join(' ') || `#${user.telegram_user_id}`)
    : ''

  const tabs = useMemo(() => [
    {
      key: 'transactions',
      label: `Giao dịch${detail ? ` (${detail.transactions_total})` : ''}`,
      panel: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Table<BalanceTxRow>
            columns={txColumns}
            data={detail?.transactions ?? []}
            keyFn={row => row.id}
            loading={loading}
            skeletonRows={txPerPage}
            emptyTitle="Chưa có giao dịch"
            density="compact"
          />
          {detail && detail.transactions_total > txPerPage && (
            <Pagination
              page={txPage}
              pageSize={txPerPage}
              total={detail.transactions_total}
              onPageChange={setTxPage}
            />
          )}
        </div>
      ),
    },
    {
      key: 'topups',
      label: `Nạp tiền${detail ? ` (${detail.topups_total})` : ''}`,
      panel: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Table<TopupRow>
            columns={topupColumns}
            data={detail?.topups ?? []}
            keyFn={row => row.id}
            loading={loading}
            skeletonRows={topupPerPage}
            emptyTitle="Chưa có lệnh nạp tiền"
            density="compact"
          />
          {detail && detail.topups_total > topupPerPage && (
            <Pagination
              page={topupPage}
              pageSize={topupPerPage}
              total={detail.topups_total}
              onPageChange={setTopupPage}
            />
          )}
        </div>
      ),
    },
  ], [detail, loading, txColumns, topupColumns, txPage, txPerPage, topupPage, topupPerPage])

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title={`Chi tiết số dư — ${displayName}`}
      stickyHeader
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button variant="secondary" tone="ghost" size="sm" onClick={onClose}>
            Đóng
          </Button>
        </div>
      }
    >
      {loading && !detail && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div role="alert" style={{ color: 'var(--danger-500)', padding: '12px 0' }}>
          {error}
        </div>
      )}

      {detail && (
        <>
          {/* User summary card */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 12,
            marginBottom: 20,
            padding: 16,
            background: 'var(--bg-sunken)',
            borderRadius: 8,
            border: '1px solid var(--border-subtle)',
          }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Telegram ID</div>
              <div style={{ fontFamily: 'monospace', fontSize: 14 }}>{detail.user.telegram_user_id}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tên</div>
              <div style={{ fontSize: 14 }}>
                {[detail.user.first_name, detail.user.last_name].filter(Boolean).join(' ') || '—'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Số dư hiện tại</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--brand-500)' }}>
                {detail.user.balance.toLocaleString('vi-VN')} VND
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tổng nạp</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{detail.user.total_topup.toLocaleString('vi-VN')} VND</div>
            </div>
            {detail.user.last_topup_at && (
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Nạp cuối</div>
                <div style={{ fontSize: 13 }}>{fmt.dateTime(detail.user.last_topup_at)}</div>
              </div>
            )}
          </div>

          {/* API Token section */}
          <div style={{
            marginBottom: 20,
            padding: 16,
            background: 'var(--bg-sunken)',
            borderRadius: 8,
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
              API Token
            </div>
            {apiToken ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <code style={{
                  fontFamily: 'monospace',
                  fontSize: 12,
                  background: 'var(--bg-surface)',
                  padding: '4px 8px',
                  borderRadius: 4,
                  border: '1px solid var(--border-subtle)',
                  wordBreak: 'break-all',
                  flex: 1,
                  minWidth: 0,
                }}>
                  {apiToken}
                </code>
                <Button size="sm" variant="secondary" tone="ghost" onClick={handleCopyToken} disabled={tokenLoading}>
                  {copyFeedback ? '✓ Đã copy' : 'Copy'}
                </Button>
                <Button size="sm" variant="primary" onClick={handleGenerateToken} disabled={tokenLoading}>
                  {tokenLoading ? '...' : 'Tạo mới'}
                </Button>
                <Button size="sm" variant="destructive" tone="ghost" onClick={handleRevokeToken} disabled={tokenLoading}>
                  Thu hồi
                </Button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Chưa có token</span>
                <Button size="sm" variant="primary" onClick={handleGenerateToken} disabled={tokenLoading}>
                  {tokenLoading ? '...' : 'Tạo token'}
                </Button>
              </div>
            )}
            {tokenError && (
              <div style={{ color: 'var(--danger-500)', fontSize: 12, marginTop: 6 }}>{tokenError}</div>
            )}
          </div>

          {/* Tabs */}
          <Tabs tabs={tabs} variant="underline" size="sm" lazy />
        </>
      )}
    </Modal>
  )
}
