<script setup>
defineProps({
  status: { type: Object, default: () => ({ type: "info", message: "" }) },
  nodes: { type: Number, default: 0 },
  relationships: { type: Number, default: 0 },
});
</script>

<template>
  <div v-if="status.message" :class="['status-bar', status.type]">
    {{ status.message }}
  </div>
  <div v-if="nodes > 0" class="stats">
    共 {{ nodes }} 个节点 · {{ relationships }} 条关系
  </div>
</template>
