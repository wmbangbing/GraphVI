<script setup>
import PresetManager from "../components/PresetManager.vue";
</script>

<template>
  <div class="settings-page">
    <header class="settings-header">
      <router-link to="/" class="settings-back">← 返回图谱</router-link>
      <h1>系统设置</h1>
    </header>
    <div class="settings-body">
      <PresetManager />
    </div>
  </div>
</template>
