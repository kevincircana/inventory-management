<template>
  <ul v-if="value.kind === 'list'" class="audit-list">
    <!-- Index key: list items are display-only, never reordered, and only restocking items carry a sku. -->
    <li v-for="(item, index) in value.items" :key="item.sku || index" class="audit-list-item">
      <template v-if="item.pairs">
        <div v-for="pair in item.pairs" :key="pair.key" class="audit-pair">
          <span class="audit-key">{{ pair.key }}:</span> {{ pair.text }}
        </div>
      </template>
      <template v-else>{{ item.text }}</template>
    </li>
  </ul>
  <div v-else-if="value.kind === 'object'" class="audit-object">
    <div v-for="pair in value.pairs" :key="pair.key" class="audit-pair">
      <span class="audit-key">{{ pair.key }}:</span> {{ pair.text }}
    </div>
  </div>
  <span v-else>{{ value.text }}</span>
</template>

<script>
// Renders a display model built by AuditLog.vue (see toDisplay there).
export default {
  name: 'AuditValue',
  props: {
    value: { type: Object, required: true }
  }
}
</script>

<style scoped>
.audit-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.audit-list-item {
  padding: 0.25rem 0;
}

.audit-list-item + .audit-list-item {
  border-top: 1px solid #e2e8f0;
}

.audit-key {
  color: #64748b;
}
</style>
