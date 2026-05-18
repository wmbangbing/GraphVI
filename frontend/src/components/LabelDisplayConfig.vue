<script setup>
import { computed } from "vue";

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  labelProps: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["update:labelProps"]);

// Extract unique labels and their available properties
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
    <div class="label-config-body">
      <div v-for="cfg in labelConfigs" :key="cfg.label" class="label-config-row">
        <span class="label-name" :title="cfg.label">{{ cfg.label }}</span>
        <select
          :value="labelProps[cfg.label] || ''"
          @change="select(cfg.label, $event.target.value)"
        >
          <option value="">默认</option>
          <option v-for="p in cfg.props" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
    </div>
  </div>
</template>
