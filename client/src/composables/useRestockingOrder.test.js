import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useRestockingOrder } from './useRestockingOrder'

const cartA = [{ sku: 'A', quantity: 1 }]
const cartB = [{ sku: 'B', quantity: 2 }]

const setup = () => {
  const items = ref(cartA.map(i => ({ ...i })))
  const busy = ref(false)
  let n = 0
  const newKey = vi.fn(() => `key-${++n}`)
  const submit = vi.fn(async () => ({ order_number: 'RST-1' }))
  const order = useRestockingOrder({ items, busy, submit, formatError: e => e.message, newKey })
  return { items, busy, newKey, submit, ...order }
}

describe('useRestockingOrder', () => {
  it('blocks a second place for the same cart after success', async () => {
    const s = setup()
    await s.placeOrder()
    expect(s.canPlaceOrder.value).toBe(false)
    await s.placeOrder()
    expect(s.submit).toHaveBeenCalledTimes(1)
    expect(s.orderResult.value.order_number).toBe('RST-1')
  })

  it('never sends a new key for an unchanged cart', async () => {
    const s = setup()
    await s.placeOrder()
    await s.placeOrder()
    expect(s.newKey).toHaveBeenCalledTimes(1)
    expect(s.submit.mock.calls.every(c => c[1] === 'key-1')).toBe(true)
  })

  it('re-enables ordering after a budget change and reuses the key if the cart is identical', async () => {
    const s = setup()
    await s.placeOrder()
    s.resetForBudgetChange()
    s.items.value = cartB.map(i => ({ ...i }))
    expect(s.canPlaceOrder.value).toBe(true)
    // Budget away and back to the identical cart without ordering in between:
    // same key is sent, so the server replays the original order.
    const s2 = setup()
    await s2.placeOrder()
    s2.resetForBudgetChange()
    expect(s2.canPlaceOrder.value).toBe(true)
    await s2.placeOrder()
    expect(s2.submit.mock.calls.map(c => c[1])).toEqual(['key-1', 'key-1'])
  })

  it('keeps the key after a failure so a retry reuses it', async () => {
    const s = setup()
    s.submit.mockRejectedValueOnce(new Error('timeout'))
    await s.placeOrder()
    expect(s.orderError.value).toBe('timeout')
    expect(s.canPlaceOrder.value).toBe(true)
    await s.placeOrder()
    expect(s.submit.mock.calls.map(c => c[1])).toEqual(['key-1', 'key-1'])
  })

  it('gives a new cart a new key', async () => {
    const s = setup()
    await s.placeOrder()
    s.resetForBudgetChange()
    s.items.value = cartB.map(i => ({ ...i }))
    await s.placeOrder()
    expect(s.submit.mock.calls.map(c => c[1])).toEqual(['key-1', 'key-2'])
  })

  it('a changed cart re-enables ordering without a budget reset', async () => {
    const s = setup()
    await s.placeOrder()
    s.items.value = cartB.map(i => ({ ...i }))
    expect(s.canPlaceOrder.value).toBe(true)
  })
})
