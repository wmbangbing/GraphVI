<script setup>
import PresetManager from "../components/PresetManager.vue";
import AiConfigPanel from "../components/AiConfigPanel.vue";
import Neo4jConfigPanel from "../components/Neo4jConfigPanel.vue";
</script>

<template>
  <div class="settings-page">
    <header class="settings-header">
      <router-link to="/" class="settings-back">← 返回图谱</router-link>
      <h1>系统设置</h1>
    </header>
    <div class="settings-body">
      <el-card class="settings-card">
        <template #header>
          <span>预设问题</span>
        </template>
        <PresetManager />
      </el-card>

      <el-card class="settings-card">
        <template #header>
          <span>AI 配置</span>
        </template>
        <AiConfigPanel />
      </el-card>

      <el-card class="settings-card">
        <template #header>
          <span>数据库连接</span>
        </template>
        <Neo4jConfigPanel />
      </el-card>
    </div>
  </div>
</template>
