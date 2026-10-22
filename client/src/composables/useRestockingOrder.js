import { ref, computed } from 'vue'

/**
 * Order placement state for the restocking cart.
 *
 * @param {object} opts
 * @param {import('vue').Ref<Array>} opts.items - current recommendations (cart)
 * @param {import('vue').Ref<boolean>} opts.busy - true while loading/refreshing recommendations
 * @param {Function} opts.submit - (payload, idempotencyKey) => Promise<order>
 * @param {Function} opts.formatError - (err) => string for display
 * @param {Function} [opts.newKey] - key generator (defaults to crypto.randomUUID)
 */
export function useRestockingOrder({ items, busy, submit, formatError, newKey = () => crypto.randomUUID() }) {
  const placing = ref(false)
  const orderResult = ref(null)
  const orderError = ref(null)

  let idempotencyKey = null // one key per distinct cart
  let idempotencyKeyCart = null // cart signature the key was issued for
  // Signature of the cart that was successfully placed. Reactive so the
  // button stays disabled until the cart actually changes.
  const placedSignature = ref(null)

  const payload = computed(() => items.value.map(i => ({ sku: i.sku, quantity: i.quantity })))
  const signature = computed(() => JSON.stringify(payload.value))

  const canPlaceOrder = computed(() =>
    items.value.length > 0 &&
    !placing.value &&
    !busy.value &&
    signature.value !== placedSignature.value
  )

  const placeOrder = async () => {
    // Guard the function itself (not only the button) against double submits.
    if (placing.value || !canPlaceOrder.value) return
    placing.value = true
    orderError.value = null
    orderResult.value = null
    const body = payload.value
    const sig = signature.value
    // The key is kept across failed attempts: a timed-out request may have
    // succeeded server-side, and resending the same key makes the server return
    // that order instead of creating a second one. It is also NOT cleared on
    // success: if the same cart is submitted again, the same key makes the
    // server replay the original order instead of creating a duplicate. A key
    // is only regenerated when the cart (signature) differs.
    if (!idempotencyKey || idempotencyKeyCart !== sig) {
      idempotencyKey = newKey()
      idempotencyKeyCart = sig
    }
    try {
      orderResult.value = await submit(body, idempotencyKey)
      placedSignature.value = sig
    } catch (err) {
      orderError.value = formatError(err)
    } finally {
      placing.value = false
    }
  }

  // Called when the budget changes. Clears the placed marker so ordering is
  // enabled for the new cart. Trade-off (intended): the key is a single slot for
  // the last cart. If the user moves the budget away and back so the exact same
  // cart reappears without ordering a different cart in between, the click
  // re-sends the same key and the server replays the already-placed order
  // instead of creating another one.
  const resetForBudgetChange = () => {
    placedSignature.value = null
    orderResult.value = null
    orderError.value = null
  }

  return { placing, orderResult, orderError, canPlaceOrder, placeOrder, resetForBudgetChange }
}
