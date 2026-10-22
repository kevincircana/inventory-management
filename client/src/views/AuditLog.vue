<template>
  <div class="audit-log">
    <div class="page-header">
      <h2>{{ t('auditLog.title') }}</h2>
      <p>{{ t('auditLog.subtitle') }}</p>
      <p class="retention-note">{{ t('auditLog.retentionNote') }}</p>
    </div>

    <div class="card filters-card">
      <div class="audit-filters">
        <div class="filter-group">
          <label for="audit-entity-type">{{ t('auditLog.filters.entityType') }}</label>
          <select id="audit-entity-type" v-model="entityType" class="filter-select">
            <option value="all">{{ t('auditLog.filters.all') }}</option>
            <option value="purchase_order">{{ t('auditLog.entityType.purchase_order') }}</option>
            <option value="restocking_order">{{ t('auditLog.entityType.restocking_order') }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label for="audit-action">{{ t('auditLog.filters.action') }}</label>
          <select id="audit-action" v-model="action" class="filter-select">
            <option value="all">{{ t('auditLog.filters.all') }}</option>
            <option value="create">{{ t('auditLog.action.create') }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label for="audit-start">{{ t('auditLog.filters.startDate') }}</label>
          <input id="audit-start" v-model="startDate" type="date" class="filter-select" :max="endDate || undefined" />
        </div>
        <div class="filter-group">
          <label for="audit-end">{{ t('auditLog.filters.endDate') }}</label>
          <input id="audit-end" v-model="endDate" type="date" class="filter-select" :min="startDate || undefined" />
        </div>
        <button type="button" class="secondary-btn" :disabled="!hasActiveFilters" @click="resetFilters">
          {{ t('auditLog.filters.reset') }}
        </button>
        <button type="button" class="primary-btn export-btn" :disabled="entries.length === 0" @click="exportCsv">
          {{ t('auditLog.exportCsv') }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">{{ t('auditLog.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="card">
      <div v-if="entries.length === 0" class="empty-state">{{ t('auditLog.noData') }}</div>
      <div v-else class="table-container">
        <table>
          <thead>
            <tr>
              <th>{{ t('auditLog.columns.timestamp') }}</th>
              <th>{{ t('auditLog.columns.entityType') }}</th>
              <th>{{ t('auditLog.columns.entityId') }}</th>
              <th>{{ t('auditLog.columns.action') }}</th>
              <th>{{ t('auditLog.columns.actor') }}</th>
              <th>{{ t('auditLog.columns.changes') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="entry in entries" :key="entry.id">
              <tr>
                <td class="nowrap">{{ formatTimestamp(entry.timestamp) }}</td>
                <td>{{ entityTypeLabel(entry.entity_type) }}</td>
                <td><strong>{{ entry.entity_id }}</strong></td>
                <td>{{ actionLabel(entry.action) }}</td>
                <td>
                  <template v-if="entry.actor_name">
                    <div>{{ entry.actor_name }}</div>
                    <div class="actor-note">{{ t('auditLog.actorReportedByClient') }}</div>
                  </template>
                  <template v-else>-</template>
                </td>
                <td>
                  <button
                    type="button"
                    class="expand-btn"
                    :aria-expanded="isExpanded(entry.id)"
                    :aria-controls="'audit-changes-' + entry.id"
                    @click="toggleExpanded(entry.id)"
                  >
                    {{ isExpanded(entry.id) ? t('auditLog.collapse') : t('auditLog.expand') }}
                  </button>
                </td>
              </tr>
              <tr v-if="isExpanded(entry.id)" :id="'audit-changes-' + entry.id" class="expanded-row">
                <td colspan="6">
                  <template v-if="entry.before === null || entry.before === undefined">
                    <p class="no-previous">{{ t('auditLog.noPreviousValue') }}</p>
                    <dl class="after-list">
                      <div v-for="row in changeRows(entry)" :key="row.field" class="after-item">
                        <dt>{{ row.field }}</dt>
                        <dd><AuditValue :value="row.after" /></dd>
                      </div>
                    </dl>
                  </template>
                  <table v-else class="diff-table">
                    <thead>
                      <tr>
                        <th>{{ t('auditLog.field') }}</th>
                        <th>{{ t('auditLog.before') }}</th>
                        <th>{{ t('auditLog.after') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in changeRows(entry)" :key="row.field" :class="{ changed: row.changed }">
                        <td><strong>{{ row.field }}</strong></td>
                        <td class="mono"><AuditValue :value="row.before" /></td>
                        <td class="mono"><AuditValue :value="row.after" /></td>
                      </tr>
                    </tbody>
                  </table>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import AuditValue from '../components/AuditValue.vue'

export default {
  name: 'AuditLog',
  components: { AuditValue },
  setup() {
    const { t, currentLocale } = useI18n()

    const loading = ref(true) // true while a fetch is in flight
    const error = ref(null)
    const entries = ref([])
    const expandedIds = ref(new Set())

    const entityType = ref('all')
    const action = ref('all')
    const startDate = ref('')
    const endDate = ref('')

    const hasActiveFilters = computed(() =>
      entityType.value !== 'all' || action.value !== 'all' || !!startDate.value || !!endDate.value
    )

    let requestSeq = 0

    const loadEntries = async () => {
      // Each request gets an id; only the latest may write state, so a slow
      // response for an older filter combination cannot overwrite a newer one.
      const seq = ++requestSeq
      loading.value = true
      error.value = null
      try {
        const data = await api.getAuditLog({
          entityType: entityType.value,
          action: action.value,
          startDate: startDate.value,
          endDate: endDate.value
        })
        if (seq !== requestSeq) return
        entries.value = Array.isArray(data) ? data : []
      } catch (err) {
        if (seq !== requestSeq) return
        error.value = t('auditLog.loadFailed', { message: err.response?.data?.detail || err.message })
      } finally {
        if (seq === requestSeq) loading.value = false
      }
    }

    watch([entityType, action, startDate, endDate], loadEntries)

    const resetFilters = () => {
      entityType.value = 'all'
      action.value = 'all'
      startDate.value = ''
      endDate.value = ''
    }

    const isExpanded = (id) => expandedIds.value.has(id)
    const toggleExpanded = (id) => {
      const next = new Set(expandedIds.value)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      expandedIds.value = next
    }

    // Unknown types/actions fall back to the raw value so new server values still render.
    const entityTypeLabel = (type) => {
      const key = `auditLog.entityType.${type}`
      const label = t(key)
      return label === key ? type : label
    }
    const actionLabel = (value) => {
      const key = `auditLog.action.${value}`
      const label = t(key)
      return label === key ? value : label
    }

    const formatTimestamp = (ts) => {
      const date = new Date(ts)
      if (isNaN(date.getTime())) return ts || '-'
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleString(locale, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      })
    }

    // The changes panel is for people, so lists/objects become key: value lines.
    // exportCsv deliberately still uses JSON.stringify: CSV cells must be machine-readable.
    const numberLocale = () => (currentLocale.value === 'ja' ? 'ja-JP' : 'en-US')

    const formatScalar = (v) => {
      if (v === null || v === undefined) return '-'
      if (typeof v === 'number') return v.toLocaleString(numberLocale())
      return String(v)
    }

    // Flatten an object to key: value pairs; nested objects/arrays get dotted/indexed keys
    // so that no JSON text ever reaches the panel.
    const flattenPairs = (obj, prefix = '') => {
      const pairs = []
      for (const [k, v] of Object.entries(obj)) {
        const key = prefix ? `${prefix}.${k}` : k
        if (Array.isArray(v)) {
          v.forEach((el, i) => {
            if (el !== null && typeof el === 'object') pairs.push(...flattenPairs(el, `${key}[${i}]`))
            else pairs.push({ key: `${key}[${i}]`, text: formatScalar(el) })
          })
        } else if (v !== null && typeof v === 'object') {
          pairs.push(...flattenPairs(v, key))
        } else {
          pairs.push({ key, text: formatScalar(v) })
        }
      }
      return pairs
    }

    // Display model consumed by AuditValue: kind is 'text' | 'list' | 'object'.
    const toDisplay = (v) => {
      if (Array.isArray(v)) {
        if (v.length === 0) return { kind: 'text', text: '-' }
        return {
          kind: 'list',
          items: v.map(el => (el !== null && typeof el === 'object'
            ? { sku: el.sku, pairs: flattenPairs(el) }
            : { text: formatScalar(el) }))
        }
      }
      if (v !== null && typeof v === 'object') {
        const pairs = flattenPairs(v)
        return pairs.length ? { kind: 'object', pairs } : { kind: 'text', text: '-' }
      }
      return { kind: 'text', text: formatScalar(v) }
    }

    // Union of keys from before and after, so added/removed fields both show up.
    const changeRows = (entry) => {
      const before = entry.before || {}
      const after = entry.after || {}
      const fields = [...new Set([...Object.keys(before), ...Object.keys(after)])]
      return fields.map(field => ({
        field,
        before: toDisplay(before[field]),
        after: toDisplay(after[field]),
        // Compare raw values (JSON) so object/array fields highlight correctly.
        changed: JSON.stringify(before[field]) !== JSON.stringify(after[field])
      }))
    }

    // RFC 4180 style: wrap every cell in quotes and double any embedded quote,
    // so commas, newlines and the JSON columns' quotes survive a round trip.
    const csvCell = (v) => {
      const s = v === null || v === undefined ? '' : String(v)
      return '"' + s.replace(/"/g, '""') + '"'
    }

    const exportCsv = () => {
      const header = ['id', 'timestamp', 'entity_type', 'entity_id', 'action', 'actor_name', 'before', 'after']
      const lines = [header.map(csvCell).join(',')]
      for (const e of entries.value) {
        lines.push([
          e.id, e.timestamp, e.entity_type, e.entity_id, e.action, e.actor_name,
          e.before === null || e.before === undefined ? '' : JSON.stringify(e.before),
          e.after === null || e.after === undefined ? '' : JSON.stringify(e.after)
        ].map(csvCell).join(','))
      }
      const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      const d = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      link.href = url
      link.download = `audit-log-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.csv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }

    onMounted(loadEntries)
    onBeforeUnmount(() => {
      requestSeq++ // drop any in-flight response after unmount
    })

    return {
      t,
      loading,
      error,
      entries,
      entityType,
      action,
      startDate,
      endDate,
      hasActiveFilters,
      resetFilters,
      isExpanded,
      toggleExpanded,
      entityTypeLabel,
      actionLabel,
      formatTimestamp,
      changeRows,
      exportCsv
    }
  }
}
</script>

<style scoped>
.retention-note {
  margin-top: 0.25rem;
  font-size: 0.813rem;
  color: #64748b;
}

.filters-card {
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
}

.audit-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-group label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
}

.filter-select {
  padding: 0.4rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.813rem;
  color: #0f172a;
  background: white;
  font-weight: 500;
  min-width: 140px;
}

.filter-select:hover {
  border-color: #94a3b8;
}

.filter-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.primary-btn,
.secondary-btn {
  border-radius: 6px;
  padding: 0.4rem 1rem;
  font-size: 0.813rem;
  font-weight: 600;
  cursor: pointer;
}

.primary-btn {
  background: #0f172a;
  color: white;
  border: 1px solid #0f172a;
}

.primary-btn:hover:not(:disabled) {
  background: #1e293b;
}

.secondary-btn {
  background: white;
  color: #0f172a;
  border: 1px solid #cbd5e1;
}

.secondary-btn:hover:not(:disabled) {
  border-color: #94a3b8;
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.export-btn {
  margin-left: auto;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.nowrap {
  white-space: nowrap;
}

.actor-note {
  font-size: 0.75rem;
  color: #64748b;
}

.expand-btn {
  background: none;
  border: none;
  padding: 0;
  color: #3b82f6;
  font-weight: 500;
  cursor: pointer;
}

.expand-btn:hover {
  color: #2563eb;
  text-decoration: underline;
}

.expanded-row > td {
  background: #f8fafc;
}

.no-previous {
  margin: 0 0 0.5rem;
  font-size: 0.813rem;
  font-style: italic;
  color: #64748b;
}

.after-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
  margin: 0;
}

.after-item dt {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.after-item dd {
  margin: 0.125rem 0 0;
  font-size: 0.875rem;
  color: #0f172a;
  word-break: break-word;
}

.diff-table {
  width: 100%;
  background: white;
  border: 1px solid #e2e8f0;
}

.diff-table tr.changed td {
  background: #fefce8;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.813rem;
  word-break: break-word;
}
</style>
