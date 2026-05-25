<script setup>
import { ref, onMounted } from "vue";
import { ElMessageBox, ElMessage } from "element-plus";

const props = defineProps({
  refreshKey: { type: Number, default: 0 },
});

const emit = defineEmits(["select"]);
const HISTORY_API = "/api/history";

const history = ref([]);
const activeNames = ref([]);

async function fetchHistory() {
  try {
    const res = await fetch(`${HISTORY_API}?limit=50`);
    history.value = await res.json();
  } catch {}
}

async function handleDelete(id) {
  try {
    await fetch(`${HISTORY_API}/${id}`, { method: "DELETE" });
    await fetchHistory();
  } catch {
    ElMessage.error("删除失败");
  }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm("确定清空当前数据库的所有查询历史？", "确认");
    await fetch(HISTORY_API, { method: "DELETE" });
    await fetchHistory();
  } catch {}
}

function handleSelect(item) {
  emit("select", item);
}

function formatTime(t) {
  if (!t) return "";
  return t.slice(5, 16);
}

onMounted(fetchHistory);
</script>

<template>
  <div v-if="history.length > 0" class="query-history">
    <div class="history-header">
      <span class="history-title">查询历史</span>
      <el-button size="small" text @click="handleClear">清空</el-button>
    </div>
    <div class="history-list">
      <div
        v-for="item in history"
        :key="item.id"
        class="history-item"
        :title="item.cypher"
        @click="handleSelect(item)"
      >
        <span :class="['history-badge', item.type]">{{ item.type === 'nl' ? 'NL' : 'CQL' }}</span>
        <span class="history-text">{{ item.question || item.cypher }}</span>
        <span class="history-time">{{ formatTime(item.created_at) }}</span>
        <span class="history-del" @click.stop="handleDelete(item.id)">✕</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.query-history {
  margin-top: 12px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.history-title {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.history-list {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px;
  border-radius: 5px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 11px;
  min-width: 0;
}

.history-item:hover {
  background: var(--ctrl-hover-bg);
}

.history-badge {
  flex-shrink: 0;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.5px;
}

.history-badge.nl {
  background: rgba(108, 92, 231, 0.15);
  color: #6c5ce7;
}

.history-badge.cql {
  background: rgba(46, 204, 113, 0.15);
  color: #2ecc71;
}

.history-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  min-width: 0;
}

.history-time {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text-tertiary);
}

.history-del {
  flex-shrink: 0;
  opacity: 0;
  color: var(--text-muted);
  font-size: 10px;
  padding: 1px 3px;
  border-radius: 3px;
  transition: opacity 0.12s;
}

.history-item:hover .history-del {
  opacity: 1;
}

.history-del:hover {
  color: #ec7063;
  background: rgba(231, 76, 60, 0.1);
}
</style>
