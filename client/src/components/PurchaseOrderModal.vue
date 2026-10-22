<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">{{ mode === 'view' ? 'Purchase Order' : 'Create Purchase Order' }}</h3>
            <button class="close-button" aria-label="Close" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <form class="po-form" novalidate @submit.prevent="submit">
            <div class="modal-body">
              <div class="context-card">
                <div class="info-item">
                  <div class="info-label">Item SKU</div>
                  <div class="info-value sku">{{ backlogItem.item_sku }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">Item Name</div>
                  <div class="info-value">{{ backlogItem.item_name }}</div>
                </div>
              </div>

              <!-- View mode -->
              <template v-if="mode === 'view'">
                <div v-if="loading" class="state-message">Loading purchase order...</div>
                <div v-else-if="notFound" class="state-message">
                  No purchase order exists for this backlog item.
                </div>
                <div v-else-if="error" class="alert error" role="alert">{{ error }}</div>
                <div v-else-if="purchaseOrder" class="info-grid">
                  <div v-for="field in viewFields" :key="field.key" class="info-item">
                    <div class="info-label">{{ field.label }}</div>
                    <div class="info-value" :class="field.class">{{ field.value }}</div>
                  </div>
                </div>
              </template>

              <!-- Create mode -->
              <template v-else>
                <div v-if="error" class="alert error" role="alert">{{ error }}</div>

                <div class="form-grid">
                  <div class="form-field full">
                    <label for="po-supplier">Supplier Name</label>
                    <input id="po-supplier" v-model.trim="form.supplier_name" type="text" :class="{ invalid: fieldErrors.supplier_name }" :disabled="submitting" />
                    <span v-if="fieldErrors.supplier_name" class="field-error">{{ fieldErrors.supplier_name }}</span>
                  </div>

                  <div class="form-field">
                    <label for="po-quantity">Quantity</label>
                    <input id="po-quantity" v-model="form.quantity" type="number" min="1" step="1" :class="{ invalid: fieldErrors.quantity }" :disabled="submitting" />
                    <span v-if="fieldErrors.quantity" class="field-error">{{ fieldErrors.quantity }}</span>
                  </div>

                  <div class="form-field">
                    <label for="po-cost">Unit Cost (USD)</label>
                    <input id="po-cost" v-model="form.unit_cost" type="number" min="0" step="0.01" :class="{ invalid: fieldErrors.unit_cost }" :disabled="submitting" />
                    <span v-if="fieldErrors.unit_cost" class="field-error">{{ fieldErrors.unit_cost }}</span>
                  </div>

                  <div class="form-field full">
                    <label for="po-date">Expected Delivery Date</label>
                    <input id="po-date" v-model="form.expected_delivery_date" type="date" :class="{ invalid: fieldErrors.expected_delivery_date }" :disabled="submitting" />
                    <span v-if="fieldErrors.expected_delivery_date" class="field-error">{{ fieldErrors.expected_delivery_date }}</span>
                  </div>

                  <div class="form-field full">
                    <label for="po-notes">Notes (optional)</label>
                    <textarea id="po-notes" v-model="form.notes" rows="3" :disabled="submitting"></textarea>
                  </div>
                </div>
              </template>
            </div>

            <div class="modal-footer">
              <button type="button" class="btn-secondary" @click="close">
                {{ mode === 'view' ? 'Close' : 'Cancel' }}
              </button>
              <button v-if="mode !== 'view'" type="submit" class="btn-primary" :disabled="submitting">
                {{ submitting ? 'Creating...' : 'Create Purchase Order' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  backlogItem: { type: Object, default: null },
  mode: { type: String, default: 'create' }
})

const emit = defineEmits(['close', 'po-created'])

const form = reactive({
  supplier_name: '',
  quantity: '',
  unit_cost: '',
  expected_delivery_date: '',
  notes: ''
})
const fieldErrors = reactive({})
const error = ref(null)
const submitting = ref(false)
const loading = ref(false)
const notFound = ref(false)
const purchaseOrder = ref(null)

// Guards against a slow response from a previous item/open overwriting current state
let requestToken = 0

const resetState = () => {
  requestToken++
  form.supplier_name = ''
  // Default to the full quantity needed: the backlog line is blocked until that
  // amount is covered, so ordering it all is the common case. User can reduce it.
  form.quantity = props.backlogItem ? props.backlogItem.quantity_needed : ''
  form.unit_cost = ''
  form.expected_delivery_date = ''
  form.notes = ''
  Object.keys(fieldErrors).forEach(k => delete fieldErrors[k])
  error.value = null
  submitting.value = false
  loading.value = false
  notFound.value = false
  purchaseOrder.value = null
}

const loadPurchaseOrder = async () => {
  const token = requestToken
  loading.value = true
  try {
    const po = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
    if (token !== requestToken) return
    purchaseOrder.value = po
  } catch (err) {
    if (token !== requestToken) return
    // 404 is an expected state (no PO yet), not a failure, so it gets its own message
    if (err.response?.status === 404) {
      notFound.value = true
    } else {
      error.value = errorMessage(err, 'Failed to load purchase order')
    }
  } finally {
    if (token === requestToken) loading.value = false
  }
}

// Reset whenever the modal opens/closes or the item/mode changes; fetch for view mode
watch(
  () => [props.isOpen, props.backlogItem?.id, props.mode],
  () => {
    resetState()
    if (props.isOpen && props.backlogItem && props.mode === 'view') {
      loadPurchaseOrder()
    }
  },
  { immediate: true }
)

const errorMessage = (err, fallback) => {
  const detail = err.response?.data?.detail
  // FastAPI validation errors return detail as an array of objects
  if (Array.isArray(detail)) return detail.map(d => d.msg).filter(Boolean).join('; ') || fallback
  return detail || fallback
}

const todayString = () => {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const validate = () => {
  Object.keys(fieldErrors).forEach(k => delete fieldErrors[k])

  if (!form.supplier_name) fieldErrors.supplier_name = 'Supplier name is required'

  const qty = Number(form.quantity)
  if (form.quantity === '' || !Number.isInteger(qty) || qty <= 0) {
    fieldErrors.quantity = 'Quantity must be a positive whole number'
  }

  const cost = Number(form.unit_cost)
  if (form.unit_cost === '' || !Number.isFinite(cost) || cost <= 0) {
    fieldErrors.unit_cost = 'Unit cost must be greater than zero'
  }

  if (!form.expected_delivery_date) {
    fieldErrors.expected_delivery_date = 'Expected delivery date is required'
  } else if (isNaN(new Date(form.expected_delivery_date).getTime())) {
    fieldErrors.expected_delivery_date = 'Enter a valid date'
  } else if (form.expected_delivery_date < todayString()) {
    // ISO date strings compare correctly as text
    fieldErrors.expected_delivery_date = 'Delivery date cannot be in the past'
  }

  return Object.keys(fieldErrors).length === 0
}

const submit = async () => {
  if (props.mode !== 'create' || submitting.value) return
  error.value = null
  if (!validate()) return

  const token = requestToken
  submitting.value = true
  try {
    const payload = {
      backlog_item_id: props.backlogItem.id,
      supplier_name: form.supplier_name,
      quantity: Number(form.quantity),
      unit_cost: Number(form.unit_cost),
      expected_delivery_date: form.expected_delivery_date
    }
    if (form.notes.trim()) payload.notes = form.notes.trim()

    const po = await api.createPurchaseOrder(payload)
    if (token !== requestToken) return
    emit('po-created', po)
  } catch (err) {
    if (token !== requestToken) return
    // Keep the form as-is so the user can correct and retry
    error.value = errorMessage(err, 'Failed to create purchase order')
  } finally {
    if (token === requestToken) submitting.value = false
  }
}

const close = () => emit('close')

const formatDate = (value) => {
  if (!value) return 'N/A'
  // Date-only strings parse as UTC; add a time so they display as the same local day
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value)
  if (isNaN(date.getTime())) return 'N/A'
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

const formatMoney = (n) =>
  Number.isFinite(Number(n))
    ? Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
    : 'N/A'

const viewFields = computed(() => {
  const po = purchaseOrder.value
  if (!po) return []
  return [
    { key: 'id', label: 'PO Number', value: po.id, class: 'sku' },
    { key: 'status', label: 'Status', value: po.status },
    { key: 'supplier', label: 'Supplier', value: po.supplier_name },
    { key: 'quantity', label: 'Quantity', value: `${po.quantity} units` },
    { key: 'unit_cost', label: 'Unit Cost', value: formatMoney(po.unit_cost) },
    { key: 'total', label: 'Total Cost', value: formatMoney(po.quantity * po.unit_cost) },
    { key: 'delivery', label: 'Expected Delivery', value: formatDate(po.expected_delivery_date) },
    { key: 'created', label: 'Created', value: formatDate(po.created_date) },
    { key: 'notes', label: 'Notes', value: po.notes || 'None' }
  ]
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.po-form {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.context-card {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 1.5rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.info-value.sku {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.state-message {
  padding: 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.alert {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.alert.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-field.full {
  grid-column: 1 / -1;
}

.form-field label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.form-field input,
.form-field textarea {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.938rem;
  font-family: inherit;
  color: #0f172a;
  background: white;
}

.form-field textarea {
  resize: vertical;
}

.form-field input:focus,
.form-field textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.form-field input.invalid {
  border-color: #dc2626;
}

.field-error {
  font-size: 0.813rem;
  color: #dc2626;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #2563eb;
  border: 1px solid #2563eb;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
