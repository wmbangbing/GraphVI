<script setup>
import { ref } from "vue";

const DEFAULT_QUERY = `MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 50`;

const props = defineProps({ loading: Boolean });
const emit = defineEmits(["execute", "execute-nl", "execute-semantic"]);

const mode = ref("cypher");
const cypher = ref("");
const nlQuestion = ref("");

function handleExecute() {
  if (mode.value === "cypher") {
    emit("execute", cypher.value || DEFAULT_QUERY);
  } else if (mode.value === "nl") {
    if (!nlQuestion.value.trim()) return;
    emit("execute-nl", nlQuestion.value);
  } else {
    if (!nlQuestion.value.trim()) return;
    emit("execute-semantic", nlQuestion.value);
  }
}

function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    handleExecute();
  }
}

function handleClear() {
  if (mode.value === "cypher") {
    cypher.value = "";
  } else {
    nlQuestion.value = "";
  }
}
</script>

<template>
  <div class="query-editor">
    <div class="qe-tabs">
      <span :class="{ active: mode === 'cypher' }" @click="mode = 'cypher'">Cypher</span>
      <span :class="{ active: mode === 'nl' }" @click="mode = 'nl'">自然语言</span>
      <span :class="{ active: mode === 'semantic' }" @click="mode = 'semantic'">语义</span>
    </div>

    <div v-if="mode === 'cypher'">
      <el-input
        id="cypher-input"
        v-model="cypher"
        :placeholder="DEFAULT_QUERY"
        type="textarea"
        :rows="6"
        spellcheck="false"
        @keydown="handleKeydown"
      />
    </div>

    <div v-else-if="mode === 'nl'">
      <el-input
        v-model="nlQuestion"
        placeholder="输入自然语言问题，例如：查询所有事件"
        type="textarea"
        :rows="4"
        @keydown="handleKeydown"
      />
    </div>
    <div v-else>
      <el-input
        v-model="nlQuestion"
        placeholder="输入搜索内容，例如：巴威台风应急事件"
        type="textarea"
        :rows="4"
        @keydown="handleKeydown"
      />
      <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">
        基于向量检索，搜索图谱中语义相似的节点及关联信息
      </div>
    </div>

    <div class="btn-row">
      <el-button
        class="btn-run"
        type="primary"
        :loading="loading"
        :disabled="mode === 'nl' && !nlQuestion.trim()"
        @click="handleExecute"
      >
        执行查询
      </el-button>
      <el-button class="btn-clear" @click="handleClear">清空</el-button>
    </div>
    <div class="shortcut-hint">Ctrl + Enter 快速执行</div>
  </div>
</template>

<style scoped>
.qe-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--panel-border);
}

.qe-tabs span {
  padding: 4px 14px;
  font-size: 12px;
  color: var(--text-tertiary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
  user-select: none;
}

.qe-tabs span:hover {
  color: var(--text-secondary);
}

.qe-tabs span.active {
  color: #6c5ce7;
  border-bottom-color: #6c5ce7;
}
</style>
