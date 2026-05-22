<script setup>
import { computed } from "vue";

const props = defineProps({
  status: { type: Object, default: () => ({ type: "info", message: "" }) },
  nodes: { type: Number, default: 0 },
  relationships: { type: Number, default: 0 },
});

const alertType = computed(() => {
  const map = { info: "info", success: "success", error: "error" };
  return map[props.status.type] || "info";
});
</script>

<template>
  <div v-if="status.message" class="status-bar">
    <el-alert :title="status.message" :type="alertType" :closable="false" show-icon />
  </div>
  <div v-if="nodes > 0" class="stats">
    共 {{ nodes }} 个节点 · {{ relationships }} 条关系
  </div>
</template>
