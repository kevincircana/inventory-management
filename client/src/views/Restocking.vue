<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="budget-row">
        <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
        <span class="budget-value">{{ formatCurrency(budget) }}</span>
      </div>
      <input
        id="budget-slider"
        v-model.number="budget"
        type="range"
        :min="BUDGET_MIN"
        :max="BUDGET_MAX"
        :step="BUDGET_STEP"
        class="budget-slider"
      />
      <div class="budget-scale">
        <span>{{ formatCurrency(BUDGET_MIN) }}</span>
        <span>{{ formatCurrency(BUDGET_MAX) }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="orderResult" class="confirmation" role="status">
        <strong>{{ t('restocking.confirmation') }}</strong>
        <dl class="confirmation-details">
          <div>
            <dt>{{ t('restocking.orderNumber') }}</dt>
            <dd>{{ orderResult.order_number }}</dd>
          </div>
          <div>
            <dt>{{ t('restocking.submittedDate') }}</dt>
            <dd>{{ formatDate(orderResult.submitted_date) }}</dd>
          </div>
          <div>
            <dt>{{ t('restocking.expectedDelivery') }}</dt>
            <dd>{{ formatDate(orderResult.expected_delivery) }}</dd>
          </div>
          <div>
            <dt>{{ t('restocking.leadTime') }}</dt>
            <dd>{{ t('restocking.days', { count: orderResult.lead_time_days }) }}</dd>
          </div>
        </dl>
      </div>
      <div v-if="orderError" class="error" role="alert">{{ orderError }}</div>

      <div class="card">
        <div class="card-header recs-header">
          <h3 class="card-title">
            {{ t('restocking.recommendations') }} ({{ items.length }})
            <span v-if="refreshing" class="updating">{{ t('restocking.updating') }}</span>
          </h3>
          <button
            type="button"
            class="place-order-btn"
            :class="{ 'is-submitting': placing }"
            :disabled="!canPlaceOrder"
            :aria-busy="placing ? 'true' : 'false'"
            @click="placeOrder"
          >
            <span v-if="placing" class="spinner" aria-hidden="true"></span>
            {{ placing ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div class="summary-line">
          <span>{{ t('restocking.totalCost') }}: <strong>{{ formatCurrency(totalCost, true) }}</strong></span>
          <span>{{ t('restocking.remainingBudget') }}: <strong>{{ formatCurrency(remainingBudget, true) }}</strong></span>
        </div>

        <div v-if="items.length === 0" class="empty-state">{{ t('restocking.empty') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.forecastedDemand') }}</th>
                <th class="num">{{ t('restocking.table.onHand') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.name) }}</td>
                <td class="num"><strong>{{ item.quantity.toLocaleString() }}</strong></td>
                <td class="num">{{ formatCurrency(item.unit_cost, true) }}</td>
                <td class="num"><strong>{{ formatCurrency(item.line_total, true) }}</strong></td>
                <td class="num">{{ item.forecasted_demand.toLocaleString() }}</td>
                <td class="num">{{ item.quantity_on_hand.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { useRestockingOrder } from '../composables/useRestockingOrder'

const BUDGET_MIN = 0
const BUDGET_MAX = 50000
const BUDGET_STEP = 500
const DEBOUNCE_MS = 300

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

    const budget = ref(25000)
    const loading = ref(true) // first load only; later refreshes keep the table visible
    const refreshing = ref(false) // debounce pending or request in flight
    const error = ref(null)
    const items = ref([])
    const totalCost = ref(0)
    const remainingBudget = ref(0)

    let debounceTimer = null
    let requestSeq = 0

    const busy = computed(() => refreshing.value || loading.value)
    const { placing, orderResult, orderError, canPlaceOrder, placeOrder, resetForBudgetChange } =
      useRestockingOrder({
        items,
        busy,
        submit: (payload, key) => api.placeRestockingOrder(payload, key),
        formatError: err =>
          err.response?.data?.detail || t('restocking.orderFailed') + ': ' + err.message
      })

    const loadRecommendations = async () => {
      // Each request gets an id; only the latest one may write state. Without
      // this, a slow response for an old budget could overwrite a newer one.
      const seq = ++requestSeq
      try {
        const data = await api.getRestockingRecommendations(budget.value)
        if (seq !== requestSeq) return
        items.value = data.items
        totalCost.value = data.total_cost
        remainingBudget.value = data.remaining_budget
        error.value = null
      } catch (err) {
        if (seq !== requestSeq) return
        error.value = t('restocking.loadFailed') + ': ' + (err.response?.data?.detail || err.message)
      } finally {
        if (seq === requestSeq) {
          loading.value = false
          refreshing.value = false
        }
      }
    }

    // The slider fires on every step while dragging. Debounce so we only
    // fetch once the user pauses, instead of one request per step.
    watch(budget, () => {
      refreshing.value = true
      resetForBudgetChange() // clears placed marker + result so the new cart can be ordered
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(loadRecommendations, DEBOUNCE_MS)
    })

    const formatCurrency = (value, cents = false) => {
      const isJpy = currentCurrency.value === 'JPY'
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return Number(value).toLocaleString(locale, {
        style: 'currency',
        currency: isJpy ? 'JPY' : 'USD',
        minimumFractionDigits: cents && !isJpy ? 2 : 0,
        maximumFractionDigits: cents && !isJpy ? 2 : 0
      })
    }

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return '-'
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    onMounted(loadRecommendations)
    onBeforeUnmount(() => {
      clearTimeout(debounceTimer)
      requestSeq++ // drop any in-flight response after unmount
    })

    return {
      t,
      BUDGET_MIN,
      BUDGET_MAX,
      BUDGET_STEP,
      budget,
      loading,
      refreshing,
      error,
      items,
      totalCost,
      remainingBudget,
      placing,
      orderResult,
      orderError,
      canPlaceOrder,
      placeOrder,
      formatCurrency,
      formatDate,
      translateProductName
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #3b82f6;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: #64748b;
}

.recs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.updating {
  margin-left: 0.75rem;
  font-size: 0.813rem;
  font-weight: 400;
  color: #64748b;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.place-order-btn.is-submitting {
  background: #64748b;
  cursor: progress;
}

.spinner {
  display: inline-block;
  width: 0.75rem;
  height: 0.75rem;
  margin-right: 0.5rem;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: white;
  border-radius: 50%;
  vertical-align: -0.1em;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.summary-line {
  display: flex;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  font-size: 0.875rem;
  color: #64748b;
  border-bottom: 1px solid #f1f5f9;
}

.summary-line strong {
  color: #0f172a;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.num {
  text-align: right;
}

.confirmation {
  background: #d1fae5;
  border: 1px solid #10b981;
  border-radius: 10px;
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
  color: #065f46;
}

.confirmation-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
  margin: 0.75rem 0 0;
}

.confirmation-details dt {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.confirmation-details dd {
  margin: 0.125rem 0 0;
  font-weight: 600;
}
</style>
