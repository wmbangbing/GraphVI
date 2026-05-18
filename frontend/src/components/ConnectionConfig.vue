<script setup>
import { ref } from "vue";

const props = defineProps({
  config: { type: Object, required: true },
});

const emit = defineEmits(["update:config", "test"]);

const expanded = ref(false);
const testing = ref(false);
const testResult = ref(null); // { ok: bool, message: str }

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
  <div class="conn-config">
    <div class="conn-header" @click="expanded = !expanded">
      <span class="conn-label">数据库连接</span>
      <span class="conn-toggle">{{ expanded ? "−" : "+" }}</span>
    </div>

    <div v-if="expanded" class="conn-body">
      <div class="conn-field">
        <label>URI</label>
        <input
          type="text"
          :value="config.uri"
          placeholder="bolt://localhost:7687"
          @input="update('uri', $event.target.value)"
        />
      </div>
      <div class="conn-field">
        <label>Username</label>
        <input
          type="text"
          :value="config.username"
          placeholder="neo4j"
          @input="update('username', $event.target.value)"
        />
      </div>
      <div class="conn-field">
        <label>Password</label>
        <input
          type="password"
          :value="config.password"
          placeholder="password"
          @input="update('password', $event.target.value)"
        />
      </div>
      <div class="conn-field">
        <label>Database</label>
        <input
          type="text"
          :value="config.database"
          placeholder="neo4j"
          @input="update('database', $event.target.value)"
        />
      </div>

      <button class="conn-test-btn" :disabled="testing" @click="handleTest">
        {{ testing ? "测试中..." : "测试连接" }}
      </button>

      <div
        v-if="testResult"
        :class="['conn-result', testResult.ok ? 'success' : 'error']"
      >
        {{ testResult.message }}
      </div>
    </div>
  </div>
</template>
