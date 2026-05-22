<script setup>
import { ref } from "vue";

const DEFAULT_QUERY = `MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 50`;

const props = defineProps({ loading: Boolean });
const emit = defineEmits(["execute"]);

const cypher = ref("");

function handleExecute() {
  emit("execute", cypher.value || DEFAULT_QUERY);
}

function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    handleExecute();
  }
}

function handleClear() {
  cypher.value = "";
}
</script>

<template>
  <div class="query-editor">
    <label for="cypher-input">Cypher 查询</label>
    <el-input
      id="cypher-input"
      v-model="cypher"
      :placeholder="DEFAULT_QUERY"
      type="textarea"
      :rows="6"
      spellcheck="false"
      @keydown="handleKeydown"
    />
    <div class="btn-row">
      <el-button
        class="btn-run"
        type="primary"
        :loading="loading"
        @click="handleExecute"
      >
        执行查询
      </el-button>
      <el-button class="btn-clear" @click="handleClear">清空</el-button>
    </div>
    <div class="shortcut-hint">Ctrl + Enter 快速执行</div>
  </div>
</template>
