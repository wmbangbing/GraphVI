<script setup>
import { computed } from "vue";

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  labelProps: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["update:labelProps"]);

const labelConfigs = computed(() => {
  const map = {};
  props.nodes.forEach((n) => {
    const label = (n.labels?.length > 1 ? n.labels.find(l => l !== "Entity") : null) || n.labels?.[0] || "Node";
    if (!map[label]) {
      map[label] = {
        label,
        props: Object.keys(n.properties || {}),
      };
    }
  });
  return Object.values(map);
});

function select(label, propName) {
  emit("update:labelProps", { ...props.labelProps, [label]: propName });
}
</script>

<template>
  <div v-if="labelConfigs.length > 0" class="label-config">
    <div class="label-config-header">节点显示属性</div>
    <div class="label-config-body">
      <div v-for="cfg in labelConfigs" :key="cfg.label" class="label-config-row">
        <span class="label-name" :title="cfg.label">{{ cfg.label }}</span>
        <el-select
          :model-value="labelProps[cfg.label] || ''"
          size="small"
          @change="select(cfg.label, $event)"
        >
          <el-option label="默认" value="" />
          <el-option v-for="p in cfg.props" :key="p" :label="p" :value="p" />
        </el-select>
      </div>
    </div>
  </div>
</template>
