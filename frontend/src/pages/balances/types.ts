/** Shared TypeScript interfaces for the Balances feature. */

export interface BalanceUserRow {
  bot_user_id: string
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  balance: number
  total_topup: number
  last_topup_at: string | null
  api_token: string | null
}

export interface BalanceTxRow {
  id: string
  amount: number
  balance_after: number
  kind: string
  reference_id: string | null
  admin_id: string | null
  admin_username: string | null
  reason: string | null
  created_at: string
}

export interface TopupRow {
  id: string
  amount: number
  status: string
  payment_provider: string | null
  payment_transaction_id: string | null
  created_at: string
  updated_at: string
}

export interface BalancesListResponse {
  items: BalanceUserRow[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface BalanceUserDetail {
  user: BalanceUserRow
  transactions: BalanceTxRow[]
  transactions_total: number
  topups: TopupRow[]
  topups_total: number
}

export type AdjustAction = 'add' | 'subtract' | 'set'

export interface BalanceAdjustRequest {
  action: AdjustAction
  amount: number
  reason?: string
}

export interface BalanceAdjustResponse {
  success: boolean
  new_balance: number
  reason?: string
}

export interface ApiTokenResponse {
  bot_user_id: string
  api_token: string | null
}
