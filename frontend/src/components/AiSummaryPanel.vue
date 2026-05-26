<script setup>
import { ref, watch } from "vue";
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: false, linkify: true });

const props = defineProps({
  graphData: { type: Object, default: () => ({ nodes: [], relationships: [] }) },
  visible: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

const content = ref("");
const loading = ref(false);
const error = ref("");

watch(() => props.graphData, () => {
  content.value = "";
  error.value = "";
}, { deep: true });

watch(() => props.visible, (v) => {
  if (!v) {
    // keep content for reopen, only reset loading/error
    loading.value = false;
  }
});

async function analyze() {
  if (!props.graphData.nodes.length && !props.graphData.relationships.length) return;

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
</script>

<template>
  <div v-show="visible" class="ai-summary-panel">
    <div class="ai-summary-header">
      <span>AI 分析总结</span>
      <span class="ai-summary-close" @click="$emit('close')">✕</span>
    </div>

    <div class="ai-summary-body">
      <el-button
        class="ai-gen-btn"
        type="primary"
        size="small"
        :disabled="graphData.nodes.length === 0 && graphData.relationships.length === 0"
        :loading="loading"
        @click="analyze"
      >
        {{ loading ? "生成中..." : "生成总结" }}
      </el-button>

      <div v-if="error" class="ai-summary-error">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>

      <div v-if="content" class="ai-markdown" v-html="content" />

      <div v-if="!content && !loading && !error" class="ai-summary-empty">
        点击"生成总结"对当前图谱数据进行分析
      </div>

      <div v-if="loading && !content" class="ai-summary-empty">正在等待响应...</div>
    </div>
  </div>
</template>

<style scoped>
.ai-summary-panel {
  position: absolute;
  top: 16px;
  right: 74px;
  width: 420px;
  max-height: 80%;
  display: flex;
  flex-direction: column;
  background: var(--prop-panel-bg);
  border: 1px solid var(--prop-panel-border);
  border-radius: 12px;
  z-index: 50;
  backdrop-filter: blur(16px);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}

.ai-summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--panel-border);
}

.ai-summary-close {
  cursor: pointer;
  color: #555;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.15s;
}

.ai-summary-close:hover {
  color: #ec7063;
}

.ai-summary-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 18px 18px;
}

.ai-gen-btn {
  width: 100%;
  margin-bottom: 12px;
}

.ai-summary-error {
  margin-bottom: 12px;
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
  font-weight: 600;
  color: var(--text-primary);
  margin: 16px 0 8px;
}

.ai-markdown :deep(h1) { font-size: 17px; }
.ai-markdown :deep(h2) { font-size: 15px; }
.ai-markdown :deep(h3) { font-size: 14px; }

.ai-markdown :deep(p) { margin: 0 0 8px; }

.ai-markdown :deep(ul),
.ai-markdown :deep(ol) {
  padding-left: 20px;
  margin: 0 0 8px;
}

.ai-markdown :deep(li) { margin-bottom: 4px; }

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

.ai-markdown :deep(strong) { color: var(--text-primary); }

.ai-summary-empty {
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
  padding: 24px 0;
}
</style>
