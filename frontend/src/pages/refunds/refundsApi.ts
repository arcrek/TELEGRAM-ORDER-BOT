import { apiClient } from '../../shared/lib/api'

export interface RefundUser {
  telegram_user_id: number
  username: string | null
  name: string | null
  balance: number
}

export interface RefundOrderItem {
  product: string | null
  variation: string | null
  quantity: number
}

export interface RefundOrderRow {
  id: string
  status: string
  total_amount: number
  created_at: string | null
  items: RefundOrderItem[]
  eligible: boolean
  ineligible_reason: string | null
}

export interface RefundOrdersResponse {
  user: RefundUser
  orders: RefundOrderRow[]
}

export interface PreviewRow {
  order_id: string
  duration_days: number
  elapsed: number
  remaining: number
  daily_rate: number
  refund_amount: number
  eligible: boolean
}

export interface PreviewResponse {
  rows: PreviewRow[]
  total_refund: number
}

export interface DurationItem {
  order_id: string
  days: number
  months: number
  years: number
}

export type RefundMode = 'credit' | 'status'

export interface ConfirmItem extends DurationItem {
  mode: RefundMode
}

export interface ConfirmResult {
  order_id: string
  success: boolean
  reason: string
  refund_amount: number | null
  new_balance: number | null
}

export interface ConfirmResponse {
  results: ConfirmResult[]
}

export async function fetchUserOrders(
  search: string,
  startDate?: string,
  endDate?: string,
): Promise<RefundOrdersResponse> {
  const params: Record<string, string> = { search }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  const res = await apiClient.get<RefundOrdersResponse>('/api/refunds/orders', { params })
  return res.data
}

export async function previewRefunds(items: DurationItem[]): Promise<PreviewResponse> {
  const res = await apiClient.post<PreviewResponse>('/api/refunds/preview', { items })
  return res.data
}

export async function confirmRefunds(items: ConfirmItem[]): Promise<ConfirmResponse> {
  const res = await apiClient.post<ConfirmResponse>('/api/refunds/confirm', { items })
  return res.data
}
