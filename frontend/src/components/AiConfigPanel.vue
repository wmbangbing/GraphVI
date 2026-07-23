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
  enable_script_stats: "false",
});
const saving = ref(false);
const testing = ref(false);
const testResult = ref(null);
const semanticTesting = ref(false);
const semanticTestResult = ref(null);

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
      enable_script_stats: data.enable_script_stats || "false",
    };
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

async function saveSettings() {
  saving.value = true;
  try {
    await fetch(apiUrl(SETTINGS_API), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: config.value }),
    });
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
      </el-form>
      <el-button size="small" :loading="semanticTesting" @click="testSemantic">测试向量检索</el-button>
      <div v-if="semanticTestResult" class="test-result" :class="{ success: semanticTestResult.ok, error: !semanticTestResult.ok }">
        {{ semanticTestResult.message }}
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
