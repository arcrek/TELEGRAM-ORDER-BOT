import { describe, it, expect } from 'vitest'
import { buildToastDetail, buyerLabel, pickNewOrders } from './newOrderToast'

const order = (over = {}) => ({
  id: 'O1', user_id: 9, buyer_username: 'hung', buyer_name: 'Hùng', total_amount: 50000,
  items: [{ product_name: 'Netflix', variation_name: '1 tháng' }], ...over,
})

describe('newOrderToast helpers', () => {
  it('buyerLabel prefers username, then name, then #id', () => {
    expect(buyerLabel(order())).toBe('hung')
    expect(buyerLabel(order({ buyer_username: null }))).toBe('Hùng')
    expect(buyerLabel(order({ buyer_username: null, buyer_name: null }))).toBe('#9')
  })

  it('buildToastDetail joins product+variation, multi with " + "', () => {
    expect(buildToastDetail(order())).toBe('Netflix 1 tháng')
    expect(buildToastDetail(order({ items: [
      { product_name: 'Netflix', variation_name: '1 tháng' },
      { product_name: 'Spotify', variation_name: null },
    ] }))).toBe('Netflix 1 tháng + Spotify')
  })

  it('pickNewOrders returns only unseen ids and mutates the seen set', () => {
    const seen = new Set<string>(['O0'])
    const fresh = pickNewOrders([order({ id: 'O0' }), order({ id: 'O1' })], seen)
    expect(fresh.map(o => o.id)).toEqual(['O1'])
    expect(seen.has('O1')).toBe(true)
  })
})
