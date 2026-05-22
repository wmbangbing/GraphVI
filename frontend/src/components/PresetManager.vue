<script setup>
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";

const API_BASE = "/api/presets";

const presets = ref([]);
const dialogVisible = ref(false);
const dialogTitle = ref("");
const form = ref({ question: "", cypher: "" });
const editingId = ref(null);

async function fetchPresets() {
  try {
    const res = await fetch(API_BASE);
    presets.value = await res.json();
  } catch {
    ElMessage.error("获取预设列表失败");
  }
}

function openCreate() {
  dialogTitle.value = "新增预设";
  editingId.value = null;
  form.value = { question: "", cypher: "" };
  dialogVisible.value = true;
}

function openEdit(preset) {
  dialogTitle.value = "编辑预设";
  editingId.value = preset.id;
  form.value = { question: preset.question, cypher: preset.cypher || "" };
  dialogVisible.value = true;
}

async function handleSave() {
  if (!form.value.question.trim()) {
    ElMessage.warning("请输入问题");
    return;
  }
  try {
    if (editingId.value) {
      await fetch(`${API_BASE}/${editingId.value}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: form.value.question,
          cypher: form.value.cypher || null,
        }),
      });
      ElMessage.success("更新成功");
    } else {
      await fetch(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: form.value.question,
          cypher: form.value.cypher || null,
        }),
      });
      ElMessage.success("新增成功");
    }
    dialogVisible.value = false;
    await fetchPresets();
  } catch {
    ElMessage.error("保存失败");
  }
}

async function handleDelete(preset) {
  try {
    await fetch(`${API_BASE}/${preset.id}`, { method: "DELETE" });
    ElMessage.success("删除成功");
    await fetchPresets();
  } catch {
    ElMessage.error("删除失败");
  }
}

onMounted(fetchPresets);
</script>

<template>
  <div class="preset-manager">
    <div class="preset-manager-header">
      <h2>预设问题</h2>
      <el-button type="primary" size="small" @click="openCreate">新增预设</el-button>
    </div>

    <el-table :data="presets" stripe style="width: 100%" size="small">
      <el-table-column prop="question" label="问题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="cypher" label="Cypher 语句" min-width="250" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="{ 'no-cypher': !row.cypher }">{{ row.cypher || "（无语句）" }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确定删除该预设？" @confirm="handleDelete(row)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" label-position="top">
        <el-form-item label="问题（必填）" required>
          <el-input v-model="form.question" placeholder="输入问题文本" />
        </el-form-item>
        <el-form-item label="Cypher 语句（选填）">
          <el-input
            v-model="form.cypher"
            type="textarea"
            :rows="4"
            placeholder="输入关联的 Cypher 查询语句"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.preset-manager-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.preset-manager-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.no-cypher {
  color: var(--text-muted);
  font-style: italic;
}
</style>
