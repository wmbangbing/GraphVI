<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  graphData: { type: Object, default: () => ({ nodes: [], relationships: [] }) },
});

const summary = ref("");
const loading = ref(false);
const error = ref("");

watch(() => props.graphData, () => {
  summary.value = "";
  error.value = "";
}, { deep: true });

async function analyze() {
  if (!props.graphData.nodes.length && !props.graphData.relationships.length) return;

  loading.value = true;
  error.value = "";
  summary.value = "";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nodes: props.graphData.nodes,
        relationships: props.graphData.relationships,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      error.value = err.detail || "分析失败";
      return;
    }
    const data = await res.json();
    summary.value = data.summary;
  } catch (e) {
    error.value = `网络错误: ${e.message}`;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="ai-summary">
    <el-button
      class="btn-analyze"
      type="primary"
      size="small"
      :disabled="graphData.nodes.length === 0 && graphData.relationships.length === 0"
      :loading="loading"
      @click="analyze"
    >
      {{ loading ? "分析中..." : "AI 总结" }}
    </el-button>

    <div v-if="error" class="ai-summary-error">
      <el-alert :title="error" type="error" show-icon :closable="false" />
    </div>

    <div v-if="summary" class="ai-summary-result">
      <div class="ai-summary-content">{{ summary }}</div>
      <el-button size="small" text @click="summary = ''">收起</el-button>
    </div>
  </div>
</template>

<style scoped>
.ai-summary {
  margin-top: 12px;
}

.btn-analyze {
  width: 100%;
}

.ai-summary-error {
  margin-top: 8px;
}

.ai-summary-result {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--input-bg);
  border-radius: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.ai-summary-content {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 8px;
}
</style>
