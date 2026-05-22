<script setup>
import { ref, reactive, watch, onMounted } from "vue";
import QueryEditor from "../components/QueryEditor.vue";
import GraphView from "../components/GraphView.vue";
import StatusBar from "../components/StatusBar.vue";
import AiSummaryPanel from "../components/AiSummaryPanel.vue";

const isDark = ref(localStorage.getItem("theme") !== "light");
document.documentElement.classList.toggle("dark", isDark.value);

function toggleTheme() {
  isDark.value = !isDark.value;
  document.documentElement.classList.toggle("dark", isDark.value);
  localStorage.setItem("theme", isDark.value ? "dark" : "light");
}

const API_BASE = "/api/query";

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

async function executeQuery(cypher) {
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
      const err = await res.json();
      status.type = "error";
      status.message = err.detail || `请求失败 (${res.status})`;
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
  } catch (e) {
    status.type = "error";
    status.message = `网络错误: ${e.message}`;
    graphData.value = { nodes: [], relationships: [] };
  } finally {
    loading.value = false;
  }
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
  if (!preset.cypher) return;
  executeQuery(preset.cypher);
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
        <div v-if="presets.length > 0" class="preset-list">
          <div class="preset-list-header">预设问题</div>
          <div
            v-for="p in presets"
            :key="p.id"
            class="preset-item"
            :class="{ disabled: !p.cypher }"
            :title="p.cypher || '暂无可执行的查询语句'"
            @click="executePreset(p)"
          >
            <span class="preset-question">{{ p.question }}</span>
            <span v-if="!p.cypher" class="preset-badge">待配置</span>
          </div>
        </div>
        <QueryEditor :loading="loading" @execute="executeQuery" />
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
      />
      <AiSummaryPanel :graph-data="graphData" />
    </div>
  </div>
</template>
