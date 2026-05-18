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
    <textarea
      id="cypher-input"
      v-model="cypher"
      :placeholder="DEFAULT_QUERY"
      spellcheck="false"
      @keydown="handleKeydown"
    />
    <div class="btn-row">
      <button class="btn-run" :disabled="loading" @click="handleExecute">
        {{ loading ? "执行中..." : "执行查询" }}
      </button>
      <button class="btn-clear" @click="handleClear">清空</button>
    </div>
    <div class="shortcut-hint">Ctrl + Enter 快速执行</div>
  </div>
</template>
