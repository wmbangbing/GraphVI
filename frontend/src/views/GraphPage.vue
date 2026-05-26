<script setup>
import { ref, reactive, watch, onMounted } from "vue";
import QueryEditor from "../components/QueryEditor.vue";
import GraphView from "../components/GraphView.vue";
import StatusBar from "../components/StatusBar.vue";
import AiSummaryPanel from "../components/AiSummaryPanel.vue";
import QueryHistory from "../components/QueryHistory.vue";

const isDark = ref(localStorage.getItem("theme") !== "light");
const historyRefreshKey = ref(0);
document.documentElement.classList.toggle("dark", isDark.value);

function toggleTheme() {
  isDark.value = !isDark.value;
  document.documentElement.classList.toggle("dark", isDark.value);
  localStorage.setItem("theme", isDark.value ? "dark" : "light");
}

const API_BASE = "/api/query";
const NL_API = "/api/query/nl";

const graphData = ref({ nodes: [], relationships: [] });
const loading = ref(false);
const status = reactive({ type: "info", message: "" });
const labelProps = ref({});

watch(
  () => graphData.value.nodes,
  (nodes) => {
    const defaults = { ...labelProps.value };
    let changed = false;
    nodes.forEach((n) => {
      const label = (n.labels?.length > 1 ? n.labels.find(l => l !== "Entity") : null) || n.labels?.[0] || "Node";
      if (!label || defaults[label]) return;
      const keys = Object.keys(n.properties || {});
      const preferred = keys.find((k) => k === "name" || k === "title");
      defaults[label] = preferred || keys[0] || "";
      changed = true;
    });
    if (changed) labelProps.value = defaults;
  }
);

async function executeQuery(cypher, historyMeta) {
  loading.value = true;
  status.type = "info";
  status.message = "查询执行中...";
  try {
    const res = await fetch(API_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cypher }),
    });
    if (!res.ok) {
      let detail = `请求失败 (${res.status})`;
      try {
        const err = await res.json();
        if (err.detail) detail = err.detail;
      } catch {}
      status.type = "error";
      status.message = detail;
      graphData.value = { nodes: [], relationships: [] };
      return;
    }
    const data = await res.json();
    if (data.nodes.length === 0 && data.relationships.length === 0) {
      status.type = "info";
      status.message = "查询成功，但未找到匹配的图谱数据";
    } else {
      status.type = "success";
      status.message = `查询成功`;
    }
    graphData.value = { nodes: data.nodes, relationships: data.relationships };
    saveHistory(historyMeta || { question: cypher, cypher, type: "cypher" });
  } catch (e) {
    status.type = "error";
    status.message = `网络错误: ${e.message}`;
    graphData.value = { nodes: [], relationships: [] };
  } finally {
    loading.value = false;
  }
}

async function saveHistory(item) {
  try {
    await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(item),
    });
    historyRefreshKey.value++;
  } catch {}
}

function selectHistory(item) {
  executeQuery(item.cypher, { question: item.question, cypher: item.cypher, type: item.type });
}

async function executeNLQuery(question) {
  loading.value = true;
  status.type = "info";
  status.message = "自然语言查询中...";
  try {
    const res = await fetch(NL_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      let detail = `请求失败 (${res.status})`;
      try {
        const err = await res.json();
        if (err.detail) detail = err.detail;
      } catch {}
      status.type = "error";
      status.message = detail;
      graphData.value = { nodes: [], relationships: [] };
      return;
    }
    const data = await res.json();
    if (data.nodes.length === 0 && data.relationships.length === 0) {
      status.type = "info";
      status.message = `查询成功，但未找到匹配的图谱数据。生成的Cypher: ${data.generated_cypher}`;
    } else {
      status.type = "success";
      status.message = `查询成功 (${data.generated_cypher})`;
    }
    graphData.value = { nodes: data.nodes, relationships: data.relationships };
    saveHistory({ question, cypher: data.generated_cypher, type: "nl" });
  } catch (e) {
    status.type = "error";
    status.message = `网络错误: ${e.message}`;
    graphData.value = { nodes: [], relationships: [] };
  } finally {
    loading.value = false;
  }
}

// ─── AI Summary ─────────────────────────────────────────────────────────────
const showAiSummary = ref(false);

function toggleAiSummary() {
  showAiSummary.value = !showAiSummary.value;
}

function closeAiSummary() {
  showAiSummary.value = false;
}
// ─── Preset Quick List ──────────────────────────────────────────────────────
const presets = ref([]);

async function fetchPresets() {
  try {
    const res = await fetch("/api/presets");
    presets.value = await res.json();
  } catch {}
}

function executePreset(preset) {
  if (preset.cypher) {
    executeQuery(preset.cypher, { question: preset.question, cypher: preset.cypher, type: "cypher" });
  } else {
    executeNLQuery(preset.question);
  }
}

onMounted(fetchPresets);
</script>

<template>
  <div class="app">
    <div class="side-panel">
      <div class="side-scroll">
        <div class="logo">
          <span class="logo-text">Graph<span>VI</span></span>
          <div class="logo-actions">
            <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换亮色主题' : '切换暗色主题'">
              {{ isDark ? "☀️" : "🌙" }}
            </button>
            <router-link to="/settings" class="settings-link" title="系统设置">⚙️</router-link>
          </div>
        </div>
        <QueryEditor :loading="loading" @execute="executeQuery" @execute-nl="executeNLQuery" />
        <div v-if="presets.length > 0" class="preset-list">
          <div class="preset-list-header">预设问题</div>
          <div
            v-for="p in presets"
            :key="p.id"
            class="preset-item"
            :title="p.cypher || '点击通过自然语言查询'"
            @click="executePreset(p)"
          >
            <span class="preset-question">{{ p.question }}</span>
            <span v-if="!p.cypher" class="preset-badge">NL</span>
          </div>
        </div>
        <QueryHistory :refresh-key="historyRefreshKey" @select="selectHistory" />
      </div>
      <StatusBar
        :status="status"
        :nodes="graphData.nodes.length"
        :relationships="graphData.relationships.length"
      />
    </div>
    <div class="graph-area">
      <GraphView
        :nodes="graphData.nodes"
        :relationships="graphData.relationships"
        :label-props="labelProps"
        :dark="isDark"
        @update:label-props="labelProps = $event"
        @toggle-ai-summary="toggleAiSummary"
      />
      <AiSummaryPanel
        :graph-data="graphData"
        :visible="showAiSummary"
        @close="closeAiSummary"
      />
    </div>
  </div>
</template>
