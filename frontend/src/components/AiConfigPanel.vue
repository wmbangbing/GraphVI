<script setup>
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";

const apiUrl = (p) => (window.__API_BASE__ || "") + p;
const SETTINGS_API = "/api/settings";

const config = ref({
  llm_endpoint: "",
  llm_api_key: "",
  llm_model: "",
  summary_prompt: "",
  nl_query_prompt: "",
  nl_schema_examples: "false",
  embedding_endpoint: "https://api.openai.com/v1",
  embedding_api_key: "",
  embedding_model: "text-embedding-3-small",
  vector_index_name: "entity_vector",
  semantic_query_hops: 1,
  semantic_score_threshold: 0.6,
  semantic_top_k: 10,
  semantic_query_limit: 2000,
  enable_semantic_rerank: "true",
  rerank_endpoint: "https://api.siliconflow.cn/v1",
  rerank_api_key: "",
  rerank_model: "Qwen/Qwen3-Reranker-4B",
  rerank_threshold: 0.8,
  enable_script_stats: "false",
  auto_default_strategy: "auto",
  auto_analyze_prompt: "",
  auto_parallel_timeout: 40,
  ignored_label: "_Embeddable",
  auto_semantic_top_k: 10,
  auto_semantic_score_threshold: 0.6,
  cache_ttl: 300,
  schema_include: "",
});
const saving = ref(false);
const testing = ref(false);
const testResult = ref(null);
const semanticTesting = ref(false);
const semanticTestResult = ref(null);
const rerankTesting = ref(false);
const rerankTestResult = ref(null);

// Schema config
const schemaAllTypes = ref({ node_types: [], rel_types: [] });
const schemaLoading = ref(false);
const savedSchemaInclude = ref({ node_types: [], rel_types: [] });

async function fetchSchemaTypes() {
  schemaLoading.value = true;
  try {
    const res = await fetch(apiUrl("/api/schema/types"));
    if (res.ok) {
      const data = await res.json();
      schemaAllTypes.value = data;
      // Save full list to settings for next page load
      await fetch(apiUrl(SETTINGS_API), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: { schema_types: JSON.stringify(data) } }),
      });
    }
  } catch {}
  schemaLoading.value = false;
}

function parseSchemaInclude(str) {
  if (!str) return { node_types: [], rel_types: [] };
  try { return JSON.parse(str); } catch { return { node_types: [], rel_types: [] }; }
}

function _updateSchemaInclude(newSel) {
  savedSchemaInclude.value = newSel;
  config.value.schema_include = JSON.stringify(newSel);
}

function toggleSchemaNode(type) {
  const sel = { ...savedSchemaInclude.value };
  if (sel.node_types.includes(type)) {
    sel.node_types = sel.node_types.filter(t => t !== type);
  } else {
    sel.node_types = [...sel.node_types, type];
  }
  _updateSchemaInclude(sel);
}

function toggleSchemaRel(type) {
  const sel = { ...savedSchemaInclude.value };
  if (sel.rel_types.includes(type)) {
    sel.rel_types = sel.rel_types.filter(t => t !== type);
  } else {
    sel.rel_types = [...sel.rel_types, type];
  }
  _updateSchemaInclude(sel);
}

function selectAllNodes() {
  _updateSchemaInclude({
    ...savedSchemaInclude.value,
    node_types: [...schemaAllTypes.value.node_types],
  });
}

function deselectAllNodes() {
  _updateSchemaInclude({
    ...savedSchemaInclude.value,
    node_types: [],
  });
}

function selectAllRels() {
  _updateSchemaInclude({
    ...savedSchemaInclude.value,
    rel_types: [...schemaAllTypes.value.rel_types],
  });
}

function deselectAllRels() {
  _updateSchemaInclude({
    ...savedSchemaInclude.value,
    rel_types: [],
  });
}

async function fetchSettings() {
  try {
    const res = await fetch(apiUrl(SETTINGS_API));
    const data = await res.json();
    config.value = {
      llm_endpoint: data.llm_endpoint || "",
      llm_api_key: data.llm_api_key || "",
      llm_model: data.llm_model || "",
      summary_prompt: data.summary_prompt || "",
      nl_query_prompt: data.nl_query_prompt || "",
      nl_schema_examples: data.nl_schema_examples || "false",
      embedding_endpoint: data.embedding_endpoint || "https://api.openai.com/v1",
      embedding_api_key: data.embedding_api_key || "",
      embedding_model: data.embedding_model || "text-embedding-3-small",
      vector_index_name: data.vector_index_name || "entity_vector",
      semantic_query_hops: Number(data.semantic_query_hops) || 1,
      semantic_score_threshold: Number(data.semantic_score_threshold) || 0.6,
      semantic_top_k: Number(data.semantic_top_k) || 10,
      semantic_query_limit: Number(data.semantic_query_limit) || 2000,
      enable_semantic_rerank: data.enable_semantic_rerank ?? "true",
      rerank_endpoint: data.rerank_endpoint || "https://api.siliconflow.cn/v1",
      rerank_api_key: data.rerank_api_key || "",
      rerank_model: data.rerank_model || "Qwen/Qwen3-Reranker-4B",
      rerank_threshold: Number(data.rerank_threshold) || 0.8,
      enable_script_stats: data.enable_script_stats || "false",
      auto_default_strategy: data.auto_default_strategy || "auto",
      auto_analyze_prompt: data.auto_analyze_prompt || "",
      auto_parallel_timeout: Number(data.auto_parallel_timeout) || 8,
      ignored_label: data.ignored_label || "_Embeddable",
      auto_semantic_top_k: Number(data.auto_semantic_top_k) || 10,
      auto_semantic_score_threshold: Number(data.auto_semantic_score_threshold) || 0.6,
      cache_ttl: Number(data.cache_ttl) || 300,
      schema_include: data.schema_include || "",
    };
    savedSchemaInclude.value = parseSchemaInclude(data.schema_include);
    // Load cached full type list from DB
    if (data.schema_types) {
      try { schemaAllTypes.value = JSON.parse(data.schema_types); } catch {}
    }
  } catch {
    ElMessage.error("获取配置失败");
  }
}

async function testConnection() {
  testing.value = true;
  testResult.value = null;
  try {
    const res = await fetch(apiUrl("/api/analyze/test"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        llm_endpoint: config.value.llm_endpoint,
        llm_api_key: config.value.llm_api_key,
        llm_model: config.value.llm_model,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      testResult.value = { ok: true, message: `连接成功: ${data.reply}` };
    } else {
      const err = await res.json();
      testResult.value = { ok: false, message: err.detail || "测试失败" };
    }
  } catch (e) {
    testResult.value = { ok: false, message: `网络错误: ${e.message}` };
  } finally {
    testing.value = false;
  }
}

async function testSemantic() {
  semanticTesting.value = true;
  semanticTestResult.value = null;
  try {
    const res = await fetch(apiUrl("/api/query/semantic/test"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        embedding_endpoint: config.value.embedding_endpoint,
        embedding_api_key: config.value.embedding_api_key,
        embedding_model: config.value.embedding_model,
        vector_index_name: config.value.vector_index_name,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      semanticTestResult.value = {
        ok: true,
        message: data.detail || "测试通过",
      };
    } else {
      const err = await res.json();
      semanticTestResult.value = { ok: false, message: err.detail || "测试失败" };
    }
  } catch (e) {
    semanticTestResult.value = { ok: false, message: `网络错误: ${e.message}` };
  } finally {
    semanticTesting.value = false;
  }
}

async function testRerank() {
  rerankTesting.value = true;
  rerankTestResult.value = null;
  try {
    const res = await fetch(apiUrl("/api/test-rerank"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rerank_endpoint: config.value.rerank_endpoint,
        rerank_api_key: config.value.rerank_api_key,
        rerank_model: config.value.rerank_model,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      rerankTestResult.value = { ok: true, message: data.detail || "测试通过" };
    } else {
      const err = await res.json();
      rerankTestResult.value = { ok: false, message: err.detail || "测试失败" };
    }
  } catch (e) {
    rerankTestResult.value = { ok: false, message: `网络错误: ${e.message}` };
  } finally {
    rerankTesting.value = false;
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    await fetch(apiUrl(SETTINGS_API), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: config.value }),
    });
    // Sync ignored_label to localStorage for GraphView
    if (config.value.ignored_label) {
      localStorage.setItem("ignored_label", config.value.ignored_label);
    }
    ElMessage.success("配置已保存");
  } catch {
    ElMessage.error("保存配置失败");
  } finally {
    saving.value = false;
  }
}

onMounted(fetchSettings);
</script>

<template>
  <div class="ai-config">
    <div class="config-section">
      <h3 class="config-section-title">LLM 连接</h3>
      <el-form label-position="top" size="small">
        <el-form-item label="API 地址">
          <el-input v-model="config.llm_endpoint" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="config.llm_api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="config.llm_model" placeholder="gpt-4o / deepseek-chat" />
        </el-form-item>
        <el-button size="small" :loading="testing" @click="testConnection">测试模型</el-button>
        <div v-if="testResult" class="test-result" :class="{ success: testResult.ok, error: !testResult.ok }">
          {{ testResult.message }}
        </div>
      </el-form>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">总结提示词</h3>
      <p class="config-section-desc">
        可用变量：<code>{node_count}</code> <code>{rel_count}</code> <code>{nodes}</code> <code>{rels}</code>
      </p>
      <el-input
        v-model="config.summary_prompt"
        type="textarea"
        :rows="12"
        placeholder="输入总结提示词模板"
      />
    </div>

    <div class="config-section">
      <h3 class="config-section-title">NL 查询提示词</h3>
      <p class="config-section-desc">
        用于自然语言→Cypher 转换。可用变量：<code>{schema}</code> <code>{examples}</code> <code>{query_text}</code>
      </p>
      <el-input
        v-model="config.nl_query_prompt"
        type="textarea"
        :rows="12"
        placeholder="输入 NL 查询提示词模板"
      />
      <div class="config-switch">
        <el-switch
          v-model="config.nl_schema_examples"
          active-value="true"
          inactive-value="false"
          size="small"
        />
        <span>Schema 示例值（为每个标签采样属性值，提高查询准确率）</span>
      </div>
      <div class="config-switch">
        <el-switch
          v-model="config.enable_script_stats"
          active-value="true"
          inactive-value="false"
          size="small"
        />
        <span>脚本统计（AI 总结时用 Python 代码精确计算数值，而非 LLM 估算）</span>
      </div>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">语义检索</h3>
      <el-form label-position="top" size="small">
        <el-form-item label="Embedding API 地址">
          <el-input v-model="config.embedding_endpoint" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="config.embedding_api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="config.embedding_model" placeholder="text-embedding-3-small" />
        </el-form-item>
        <el-form-item label="向量索引名">
          <el-input v-model="config.vector_index_name" placeholder="entity_vector" />
        </el-form-item>
        <el-form-item label="关联跳数">
          <el-input-number v-model="config.semantic_query_hops" :min="0" :max="5" size="small" />
        </el-form-item>
        <el-form-item label="分数阈值">
          <el-input-number v-model="config.semantic_score_threshold" :min="0" :max="1" :step="0.05" size="small" />
        </el-form-item>
        <el-form-item label="最多返回">
          <el-input-number v-model="config.semantic_top_k" :min="1" :max="200" size="small" />
        </el-form-item>
        <el-form-item label="查询 LIMIT">
          <el-input-number v-model="config.semantic_query_limit" :min="100" :max="10000" :step="100" size="small" />
        </el-form-item>
      </el-form>
      <el-button size="small" :loading="semanticTesting" @click="testSemantic">测试向量检索</el-button>
      <div v-if="semanticTestResult" class="test-result" :class="{ success: semanticTestResult.ok, error: !semanticTestResult.ok }">
        {{ semanticTestResult.message }}
      </div>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">重排序（Rerank）</h3>
      <p class="config-section-desc">
        语义/语义NL/auto 接口的入口精排与过滤，提高检索准确性
      </p>
      <el-form label-position="top" size="small">
        <el-form-item label="启用重排序">
          <el-switch v-model="config.enable_semantic_rerank" active-value="true" inactive-value="false" />
        </el-form-item>
        <el-form-item label="Rerank API 地址">
          <el-input v-model="config.rerank_endpoint" placeholder="https://api.siliconflow.cn/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="config.rerank_api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="config.rerank_model" placeholder="Qwen/Qwen3-Reranker-4B" />
        </el-form-item>
        <el-form-item label="过滤阈值">
          <el-input-number v-model="config.rerank_threshold" :min="0" :max="1" :step="0.05" size="small" />
        </el-form-item>
      </el-form>
      <el-button size="small" :loading="rerankTesting" @click="testRerank">测试重排模型</el-button>
      <div v-if="rerankTestResult" class="test-result" :class="{ success: rerankTestResult.ok, error: !rerankTestResult.ok }">
        {{ rerankTestResult.message }}
      </div>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">智能查询分析</h3>
      <p class="config-section-desc">
        用于 <code>/api/query/auto</code> 接口的默认配置
      </p>
      <el-form label-position="top" size="small">
        <el-form-item label="默认策略">
          <el-select v-model="config.auto_default_strategy" size="small">
            <el-option label="LLM 分类 (auto)" value="auto" />
            <el-option label="并行择优 (parallel)" value="parallel" />
            <el-option label="顺序尝试 (sequential)" value="sequential" />
          </el-select>
        </el-form-item>
        <el-form-item label="并行检索超时 (秒)">
          <el-input-number v-model="config.auto_parallel_timeout" :min="5" :max="120" size="small" />
        </el-form-item>
        <el-form-item label="语义检索 top_k">
          <el-input-number v-model="config.auto_semantic_top_k" :min="1" :max="200" size="small" />
        </el-form-item>
        <el-form-item label="语义检索分数阈值">
          <el-input-number v-model="config.auto_semantic_score_threshold" :min="0" :max="1" :step="0.05" size="small" />
        </el-form-item>
      </el-form>
      <el-form-item label="专题分析提示词（可选）">
        <p class="config-section-desc">
          用于 LLM 生成 Python 统计脚本的领域上下文，留空使用内置默认（英文，应急指挥领域）
        </p>
        <el-input
          v-model="config.auto_analyze_prompt"
          type="textarea"
          :rows="6"
          placeholder="留空使用内置默认提示词（英文）"
        />
      </el-form-item>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">全局设置</h3>
      <el-form label-position="top" size="small">
        <el-form-item label="忽略的节点标签">
          <el-input v-model="config.ignored_label" placeholder="_Embeddable" />
        </el-form-item>
        <p class="config-section-desc">
          Neo4j 向量索引等自动添加的标签，在取节点主标签时跳过。多个标签用逗号分隔
        </p>
        <el-form-item label="查询结果缓存(秒)">
          <el-input-number v-model="config.cache_ttl" :min="0" :max="3600" size="small" />
        </el-form-item>
        <p class="config-section-desc">
          相同问题的查询结果缓存时间。设为 0 则不缓存
        </p>
      </el-form>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">Schema 配置</h3>
      <p class="config-section-desc">
        勾选需要参与查询的节点类型和关系类型，减少 LLM 处理的 token 量
        <el-button size="small" :loading="schemaLoading" @click="fetchSchemaTypes" style="margin-left:8px">
          刷新
        </el-button>
      </p>

      <div v-if="schemaAllTypes.node_types.length > 0" style="margin-bottom:8px">
        <div style="font-size:12px;font-weight:600;margin-bottom:4px">节点类型</div>
        <div style="margin-bottom:4px">
          <el-button size="small" @click="selectAllNodes">全选</el-button>
          <el-button size="small" @click="deselectAllNodes">取消全选</el-button>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;max-height:200px;overflow-y:auto">
          <el-checkbox
            v-for="t in schemaAllTypes.node_types"
            :key="t"
            :checked="savedSchemaInclude.node_types.includes(t)"
            @change="toggleSchemaNode(t)"
            size="small"
          >{{ t }}</el-checkbox>
        </div>
      </div>

      <div v-if="schemaAllTypes.rel_types.length > 0">
        <div style="font-size:12px;font-weight:600;margin-bottom:4px">关系类型</div>
        <div style="margin-bottom:4px">
          <el-button size="small" @click="selectAllRels">全选</el-button>
          <el-button size="small" @click="deselectAllRels">取消全选</el-button>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;max-height:200px;overflow-y:auto">
          <el-checkbox
            v-for="t in schemaAllTypes.rel_types"
            :key="t"
            :checked="savedSchemaInclude.rel_types.includes(t)"
            @change="toggleSchemaRel(t)"
            size="small"
          >{{ t }}</el-checkbox>
        </div>
      </div>
    </div>

    <el-button type="primary" :loading="saving" @click="saveSettings" style="margin-top: 16px">
      保存配置
    </el-button>
  </div>
</template>

<style scoped>
.config-section {
  margin-bottom: 20px;
}

.config-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px 0;
}

.config-section-desc {
  font-size: 11px;
  color: var(--text-tertiary);
  margin: -8px 0 10px 0;
}

.test-result {
  margin-top: 8px;
  padding: 6px 10px;
  font-size: 11px;
  border-radius: 5px;
}

.test-result.success {
  background: rgba(46, 204, 113, 0.1);
  color: #58d68d;
  border: 1px solid rgba(46, 204, 113, 0.15);
}

.test-result.error {
  background: rgba(231, 76, 60, 0.1);
  color: #ec7063;
  border: 1px solid rgba(231, 76, 60, 0.15);
}

.config-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.config-section-desc code {
  font-size: 11px;
  background: var(--input-bg);
  padding: 1px 5px;
  border-radius: 3px;
}
</style>
