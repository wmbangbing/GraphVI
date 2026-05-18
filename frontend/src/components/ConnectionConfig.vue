<script setup>
import { ref } from "vue";

const props = defineProps({
  config: { type: Object, required: true },
});

const emit = defineEmits(["update:config", "test"]);

const activeNames = ref([]);
const testing = ref(false);
const testResult = ref(null);

async function handleTest() {
  testing.value = true;
  testResult.value = null;
  emit("test", {
    uri: props.config.uri,
    username: props.config.username,
    password: props.config.password,
    database: props.config.database,
    onResult: (ok, msg) => {
      testResult.value = { ok, message: msg };
      testing.value = false;
    },
  });
}

function update(field, value) {
  emit("update:config", { ...props.config, [field]: value });
}
</script>

<template>
  <el-collapse v-model="activeNames" class="conn-config">
    <el-collapse-item title="数据库连接" name="db">
      <div class="conn-field">
        <label>URI</label>
        <el-input
          :model-value="config.uri"
          placeholder="bolt://localhost:7687"
          size="small"
          @input="update('uri', $event)"
        />
      </div>
      <div class="conn-field">
        <label>Username</label>
        <el-input
          :model-value="config.username"
          placeholder="neo4j"
          size="small"
          @input="update('username', $event)"
        />
      </div>
      <div class="conn-field">
        <label>Password</label>
        <el-input
          :model-value="config.password"
          type="password"
          placeholder="password"
          size="small"
          show-password
          @input="update('password', $event)"
        />
      </div>
      <div class="conn-field">
        <label>Database</label>
        <el-input
          :model-value="config.database"
          placeholder="neo4j"
          size="small"
          @input="update('database', $event)"
        />
      </div>

      <el-button
        class="conn-test-btn"
        :loading="testing"
        size="small"
        @click="handleTest"
      >
        测试连接
      </el-button>

      <div
        v-if="testResult"
        :class="['conn-result', testResult.ok ? 'success' : 'error']"
      >
        {{ testResult.message }}
      </div>
    </el-collapse-item>
  </el-collapse>
</template>
