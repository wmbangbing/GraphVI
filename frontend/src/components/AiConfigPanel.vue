<script setup>
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";

const SETTINGS_API = "/api/settings";

const config = ref({
  llm_endpoint: "",
  llm_api_key: "",
  llm_model: "",
  summary_prompt: "",
});
const saving = ref(false);

async function fetchSettings() {
  try {
    const res = await fetch(SETTINGS_API);
    const data = await res.json();
    config.value = {
      llm_endpoint: data.llm_endpoint || "",
      llm_api_key: data.llm_api_key || "",
      llm_model: data.llm_model || "",
      summary_prompt: data.summary_prompt || "",
    };
  } catch {
    ElMessage.error("获取配置失败");
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    await fetch(SETTINGS_API, {
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

.config-section-desc code {
  font-size: 11px;
  background: var(--input-bg);
  padding: 1px 5px;
  border-radius: 3px;
}
</style>
