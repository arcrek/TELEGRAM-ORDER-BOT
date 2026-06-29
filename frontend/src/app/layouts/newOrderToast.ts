import { formatVndCompact } from '../../shared/lib/format'

export interface PaidOrderItem {
  product_name: string | null
  variation_name: string | null
}

export interface PaidOrder {
  id: string
  user_id: number
  buyer_username: string | null
  buyer_name: string | null
  total_amount: number
  items: PaidOrderItem[]
}

export function buyerLabel(o: PaidOrder): string {
  return o.buyer_username || o.buyer_name || `#${o.user_id}`
}

export function buildToastDetail(o: PaidOrder): string {
  return o.items
    .map((i) => [i.product_name, i.variation_name].filter(Boolean).join(' '))
    .filter(Boolean)
    .join(' + ')
}

/** Returns orders whose id is not yet in `seen`; adds the returned ids to `seen`. */
export function pickNewOrders(orders: PaidOrder[], seen: Set<string>): PaidOrder[] {
  const fresh: PaidOrder[] = []
  for (const o of orders) {
    if (!seen.has(o.id)) {
      seen.add(o.id)
      fresh.push(o)
    }
  }
  return fresh
}

export interface NewOrderToastParams { buyer: string; detail: string; total: string; [key: string]: string }
export function buildToastParams(o: PaidOrder): NewOrderToastParams {
  return { buyer: buyerLabel(o), detail: buildToastDetail(o), total: formatVndCompact(o.total_amount) }
}
