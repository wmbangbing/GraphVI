<script setup>
defineProps({
  labels: { type: Array, default: () => [] },
});

defineEmits(["close"]);
</script>

<template>
  <div class="legend-panel">
    <div class="legend-header">
      图例
      <span class="legend-close" @click="$emit('close')">✕</span>
    </div>
    <div class="legend-body">
      <div v-for="item in labels" :key="item.label" class="legend-item">
        <span class="legend-swatch" :style="{ background: item.color }" />
        <span class="legend-label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>
