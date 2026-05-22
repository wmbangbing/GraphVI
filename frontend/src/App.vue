<script setup>
import { ref, reactive, watch } from "vue";
import QueryEditor from "./components/QueryEditor.vue";
import GraphView from "./components/GraphView.vue";
import StatusBar from "./components/StatusBar.vue";
import ConnectionConfig from "./components/ConnectionConfig.vue";

const isDark = ref(localStorage.getItem("theme") !== "light");
document.documentElement.classList.toggle("dark", isDark.value);

function toggleTheme() {
  isDark.value = !isDark.value;
  document.documentElement.classList.toggle("dark", isDark.value);
  localStorage.setItem("theme", isDark.value ? "dark" : "light");
}
const API_BASE = "/api/query";
const CONNECT_BASE = "/api/connect";

const graphData = ref({ nodes: [], relationships: [] });
const loading = ref(false);
const status = reactive({ type: "info", message: "" });
const labelProps = ref({});

const config = reactive({
  uri: "bolt://localhost:7687",
  username: "neo4j",
  password: "neo4j@openspg",
  database: "kmdevelop",
});

// Initialize labelProps defaults when new data arrives
watch(
  () => graphData.value.nodes,
  (nodes) => {
    const defaults = { ...labelProps.value };
    let changed = false;
    nodes.forEach((n) => {
      const label = (n.labels?.length > 1 ? n.labels.find(l => l !== "Entity") : null) || n.labels?.[0] || "Node";
      if (!label || defaults[label]) return;
      // Pick first property or prefer name/title
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
      body: JSON.stringify({
        cypher,
        uri: config.uri,
        username: config.username,
        password: config.password,
        database: config.database,
      }),
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

async function testConnection({ uri, username, password, database, onResult }) {
  try {
    const res = await fetch(CONNECT_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uri, username, password, database }),
    });
    if (res.ok) {
      const data = await res.json();
      onResult(true, data.message || "Neo4j 连接成功");
    } else {
      const err = await res.json();
      onResult(false, err.detail || "连接失败");
    }
  } catch (e) {
    onResult(false, `网络错误: ${e.message}`);
  }
}
</script>

<template>
  <div class="app">
    <div class="side-panel">
      <div class="side-scroll">
        <div class="logo">
          <span class="logo-text">Graph<span>VI</span></span>
          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换亮色主题' : '切换暗色主题'">
            {{ isDark ? "☀️" : "🌙" }}
          </button>
        </div>
        <ConnectionConfig
          :config="config"
          @update:config="Object.assign(config, $event)"
          @test="testConnection"
        />
        <QueryEditor :loading="loading" @execute="executeQuery" />
      </div>
      <StatusBar
        :status="status"
        :nodes="graphData.nodes.length"
        :relationships="graphData.relationships.length"
      />
    </div>
    <GraphView
      :nodes="graphData.nodes"
      :relationships="graphData.relationships"
      :label-props="labelProps"
      :dark="isDark"
      @update:label-props="labelProps = $event"
    />
  </div>
</template>
