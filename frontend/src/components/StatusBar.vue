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
    <el-alert :type="alertType" :closable="false" show-icon>
      <div class="alert-content">{{ status.message }}</div>
    </el-alert>
  </div>
  <div v-if="nodes > 0" class="stats">
    共 {{ nodes }} 个节点 · {{ relationships }} 条关系
  </div>
</template>

<style scoped>
/* 长消息（如 Cypher）限制高度，内部滚动+保留换行，完整可查看且不覆盖上方面板 */
.status-bar {
  max-height: 180px;
  overflow-y: auto;
}
.alert-content {
  max-height: 150px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 12px;
}
</style>
