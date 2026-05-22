<script setup>
import { ref, watch, nextTick } from "vue";
import { useNamespace } from "vue-element-plus-x/es/hooks/useNamespace.js";
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: false, linkify: true });

const props = defineProps({
  graphData: { type: Object, default: () => ({ nodes: [], relationships: [] }) },
});

const open = ref(false);
const content = ref("");
const loading = ref(false);
const error = ref("");

watch(() => props.graphData, () => {
  content.value = "";
  error.value = "";
}, { deep: true });

async function analyze() {
  if (!props.graphData.nodes.length && !props.graphData.relationships.length) return;

  open.value = true;
  loading.value = true;
  error.value = "";
  content.value = "";

  try {
    const res = await fetch("/api/analyze/stream", {
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
      loading.value = false;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      content.value = md.render(buffer);
    }
    content.value = md.render(buffer);
  } catch (e) {
    error.value = `网络错误: ${e.message}`;
  } finally {
    loading.value = false;
  }
}

function toggle() {
  open.value = !open.value;
}
</script>

<template>
  <div class="ai-right-panel" :class="{ open }">
    <!-- Vertical tab -->
    <div class="ai-tab" @click="toggle">
      <span>{{ open ? "✕" : "AI" }}</span>
    </div>

    <!-- Panel content -->
    <div v-if="open" class="ai-panel">
      <div class="ai-panel-header">
        <span class="ai-panel-title">AI 分析总结</span>
      </div>

      <div class="ai-panel-body">
        <el-button
          class="ai-generate-btn"
          type="primary"
          size="small"
          :disabled="graphData.nodes.length === 0 && graphData.relationships.length === 0"
          :loading="loading"
          @click="analyze"
        >
          {{ loading ? "生成中..." : "生成总结" }}
        </el-button>

        <div v-if="error" class="ai-error">
          <el-alert :title="error" type="error" show-icon :closable="false" />
        </div>

        <div v-if="content || loading" class="ai-result">
          <!-- eslint-disable vue/no-v-html -->
          <div v-if="content" class="ai-markdown" v-html="content" />
          <div v-else class="ai-placeholder">正在等待响应...</div>
        </div>

        <div v-if="!content && !loading && !error" class="ai-placeholder">
          点击"生成总结"对当前图谱数据进行分析
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-right-panel {
  position: relative;
  display: flex;
  flex-shrink: 0;
}

.ai-tab {
  width: 32px;
  min-width: 32px;
  background: var(--ctrl-bg);
  border-left: 1px solid var(--ctrl-border);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
  user-select: none;
  border-radius: 0;
}

.ai-tab:hover {
  background: var(--ctrl-hover-bg);
  color: var(--ctrl-hover-color);
}

.ai-tab span {
  writing-mode: vertical-lr;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 2px;
  color: var(--ctrl-color);
}

.ai-tab:hover span {
  color: var(--ctrl-hover-color);
}

.ai-panel {
  width: 360px;
  min-width: 360px;
  background: var(--prop-panel-bg);
  border-left: 1px solid var(--prop-panel-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ai-panel-header {
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--panel-border);
}

.ai-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ai-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.ai-generate-btn {
  width: 100%;
  margin-bottom: 12px;
}

.ai-error {
  margin-bottom: 12px;
}

.ai-result {
  min-height: 60px;
}

.ai-markdown {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  word-break: break-word;
}

.ai-markdown :deep(h1),
.ai-markdown :deep(h2),
.ai-markdown :deep(h3) {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 16px 0 8px;
}

.ai-markdown :deep(h1) { font-size: 17px; }
.ai-markdown :deep(h2) { font-size: 15px; }
.ai-markdown :deep(h3) { font-size: 14px; }

.ai-markdown :deep(p) {
  margin: 0 0 8px;
}

.ai-markdown :deep(ul),
.ai-markdown :deep(ol) {
  padding-left: 20px;
  margin: 0 0 8px;
}

.ai-markdown :deep(li) {
  margin-bottom: 4px;
}

.ai-markdown :deep(code) {
  font-size: 12px;
  background: var(--input-bg);
  padding: 1px 5px;
  border-radius: 3px;
}

.ai-markdown :deep(pre) {
  background: var(--input-bg);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0 0 12px;
}

.ai-markdown :deep(pre code) {
  background: none;
  padding: 0;
}

.ai-markdown :deep(strong) {
  color: var(--text-primary);
}

.ai-placeholder {
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
  padding: 24px 0;
}
</style>
