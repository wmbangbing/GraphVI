<script setup>
import { ref, reactive } from "vue";
import { ElMessage } from "element-plus";

const form = reactive({
  uri: "bolt://localhost:7687",
  username: "neo4j",
  password: "",
  database: "neo4j",
});
const testing = ref(false);
const saving = ref(false);

async function testConnection() {
  testing.value = true;
  try {
    const res = await fetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      ElMessage.success("连接成功");
    } else {
      const err = await res.json();
      ElMessage.error(err.detail || "连接失败");
    }
  } catch (e) {
    ElMessage.error(`网络错误: ${e.message}`);
  } finally {
    testing.value = false;
  }
}

async function saveAndConnect() {
  saving.value = true;
  try {
    const res = await fetch("/api/connect?save=true", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      ElMessage.success("配置已保存，连接已建立");
    } else {
      const err = await res.json();
      ElMessage.error(err.detail || "保存失败");
    }
  } catch (e) {
    ElMessage.error(`网络错误: ${e.message}`);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="neo4j-config">
    <el-form label-position="top" size="small">
      <el-form-item label="URI">
        <el-input v-model="form.uri" placeholder="bolt://localhost:7687" />
      </el-form-item>
      <el-form-item label="Username">
        <el-input v-model="form.username" placeholder="neo4j" />
      </el-form-item>
      <el-form-item label="Password">
        <el-input v-model="form.password" type="password" show-password placeholder="password" />
      </el-form-item>
      <el-form-item label="Database">
        <el-input v-model="form.database" placeholder="neo4j" />
      </el-form-item>
    </el-form>
    <div class="neo4j-actions">
      <el-button :loading="testing" @click="testConnection">测试连接</el-button>
      <el-button type="primary" :loading="saving" @click="saveAndConnect">保存并连接</el-button>
    </div>
  </div>
</template>

<style scoped>
.neo4j-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
