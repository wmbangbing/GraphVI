<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed, nextTick } from "vue";
import ForceGraph2D from "force-graph";
import ForceGraph3D from "3d-force-graph";
import * as THREE from "three";
import LabelDisplayConfig from "./LabelDisplayConfig.vue";

// ─── Color Palette ───────────────────────────────────────────────────────────
const LABEL_COLORS = [
  "#e74c3c", "#f1c40f", "#2ecc71", "#3498db",
  "#9b59b6", "#1abc9c", "#e67e22", "#fd79a8",
  "#00cec9", "#ff7675", "#74b9ff", "#55efc4",
];

// ─── Glow Texture (shared across 3D nodes) ──────────────────────────────────
let glowTexture = null;
function getGlowTexture() {
  if (glowTexture) return glowTexture;
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.2, "rgba(255,255,255,0.8)");
  g.addColorStop(0.6, "rgba(255,255,255,0.2)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  glowTexture = new THREE.CanvasTexture(canvas);
  return glowTexture;
}

// ─── Props ───────────────────────────────────────────────────────────────────
const props = defineProps({
  nodes: { type: Array, default: () => [] },
  relationships: { type: Array, default: () => [] },
  labelProps: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["update:labelProps"]);

// ─── Refs ────────────────────────────────────────────────────────────────────
const wrapper2d = ref(null);
const wrapper3d = ref(null);
const containerRef = ref(null);
const tooltipRef = ref(null);
const mousePos = ref({ x: 0, y: 0 });

// ─── State ───────────────────────────────────────────────────────────────────
const dimension = ref("3d");
const isFullscreen = ref(false);
const graphError = ref(null);
const hoveredNode = ref(null);
const layoutMode = ref("default"); // default | compact | spread
const showNodeLabels = ref(true);
const showPropPanel = ref(false);
const perfMode = ref(false);

let graphInstance = null;

// ─── Pick primary label (skip "Entity" if other labels exist) ────────────────
function primaryLabel(labels) {
  if (!labels || labels.length === 0) return "Node";
  if (labels.length === 1) return labels[0];
  const other = labels.find((l) => l !== "Entity");
  return other || labels[0];
}

// ─── Color Map ───────────────────────────────────────────────────────────────
const colorMap = computed(() => {
  const map = {};
  let idx = 0;
  props.nodes.forEach((n) => {
    const label = primaryLabel(n.labels);
    if (!map[label]) map[label] = LABEL_COLORS[idx++ % LABEL_COLORS.length];
  });
  return map;
});

// ─── Display value helper ────────────────────────────────────────────────────
function pickDisplayValue(node, labelProps) {
  // If user selected a property for this label, use it
  const label = primaryLabel(node.labels);
  const propName = label ? labelProps[label] : null;
  if (propName) {
    let val = node.properties?.[propName];
    if (val != null) {
      let str = String(val);
      // Strip Neo4j double-wrapping quotes
      if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
        str = str.slice(1, -1);
      }
      if (str) return str;
    }
  }
  return node.caption || node.properties?.name || node.properties?.title || node.id;
}

// ─── Build fresh graph data (avoid d3-force mutation leaks) ──────────────────
function buildFreshData() {
  return {
    nodes: props.nodes.map((n) => ({
      id: n.id,
      name: pickDisplayValue(n, props.labelProps),
      labels: n.labels,
      properties: n.properties,
      color: colorMap.value[primaryLabel(n.labels)],
    })),
    links: props.relationships.map((r) => ({
      source: r.source,
      target: r.target,
      type: r.type,
      properties: r.properties,
    })),
  };
}

const hasData = computed(() => props.nodes.length > 0);

// ─── Tooltip (fixed at top-right) ────────────────────────────────────────────
function showTooltip(html) {
  const el = tooltipRef.value;
  if (!el) return;
  el.innerHTML = html;
  el.style.display = "block";
}

function hideTooltip() {
  if (tooltipRef.value) tooltipRef.value.style.display = "none";
}

function buildTooltipContent(node) {
  const label = primaryLabel(node.labels);
  const p = node.properties || {};
  const rows = Object.entries(p)
    .map(([k, v]) => `<tr><td>${k}</td><td>${String(v)}</td></tr>`)
    .join("");
  return `
    <h4>${node.name || label}</h4>
    <span class="label-tag">${label}</span>
    <table>${rows}</table>
  `;
}

// ─── Build 3D node object ────────────────────────────────────────────────────
function buildNodeObject3D(node) {
  const group = new THREE.Group();
  const isDimmed = highlightNodes.size > 0 && !highlightNodes.has(node.id);

  // Core sphere (white center for brightness)
  const geom = new THREE.SphereGeometry(0.8, 20, 20);
  const mat = new THREE.MeshBasicMaterial({
    color: isDimmed ? node.color : "#ffffff",
    transparent: true,
    opacity: isDimmed ? 0.2 : 1,
  });
  const sphere = new THREE.Mesh(geom, mat);
  group.add(sphere);

  // Colored inner sphere
  const geom2 = new THREE.SphereGeometry(0.6, 20, 20);
  const mat2 = new THREE.MeshBasicMaterial({
    color: node.color,
    transparent: true,
    opacity: isDimmed ? 0.2 : 0.7,
  });
  const sphere2 = new THREE.Mesh(geom2, mat2);
  group.add(sphere2);

  // Glow sprite
  if (!isDimmed) {
    const spriteMat = new THREE.SpriteMaterial({
      map: getGlowTexture(),
      color: node.color,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(5, 5, 1);
    group.add(sprite);
  }

  return group;
}

// ─── Hover Highlighting ──────────────────────────────────────────────────────
let highlightNodes = new Set();

function updateHighlight(node) {
  highlightNodes.clear();
  hoveredNode.value = node;

  if (!node) return;

  const nodeId = node.id;
  props.relationships.forEach((r) => {
    if (r.source === nodeId || r.target === nodeId) {
      highlightNodes.add(r.source);
      highlightNodes.add(r.target);
    }
  });
}

// Check if a link connects to the hovered node (by ID, not object ref)
function isLinkHovered(l) {
  if (!hoveredNode.value) return false;
  const id = hoveredNode.value.id;
  const sId = typeof l.source === "object" ? l.source.id : l.source;
  const tId = typeof l.target === "object" ? l.target.id : l.target;
  return sId === id || tId === id;
}

// ─── Initialize 3D Graph ────────────────────────────────────────────────────
function init3D(wrapper, data) {
  const isPerf = perfMode.value;

  const instance = ForceGraph3D()(wrapper)
    .graphData({ nodes: [], links: [] })
    .backgroundColor("#0a0a0f")
    .nodeThreeObject((node) => {
      if (isPerf) {
        // Performance mode: single sphere, no glow
        const geom = new THREE.SphereGeometry(1, 12, 12);
        const mat = new THREE.MeshBasicMaterial({ color: node.color });
        return new THREE.Mesh(geom, mat);
      }
      return buildNodeObject3D(node);
    })
    .nodeThreeObjectExtend(isPerf ? false : true)
    .nodeRelSize(isPerf ? 2.5 : 3)
    .linkColor((l) => {
      if (hoveredNode.value) {
        return isLinkHovered(l) ? "#ffffff" : "rgba(255,255,255,0.04)";
      }
      const src = typeof l.source === "object" ? l.source : null;
      return src?.color || "#888888";
    })
    .linkWidth(0.4)
    .linkCurvature(0)
    .linkDirectionalArrowLength(isPerf ? 0 : 2)
    .linkDirectionalArrowRelPos(0.99)
    .linkDirectionalParticles(isPerf ? 0 : 3)
    .linkDirectionalParticleSpeed(0.01)
    .linkDirectionalParticleWidth(1.5)
    .linkDirectionalParticleColor((l) => {
      const src = typeof l.source === "object" ? l.source : null;
      return src?.color || "#6c5ce7";
    })
    .d3AlphaDecay(0.05)
    .d3VelocityDecay(0.4)
    .onNodeHover((node) => {
      updateHighlight(node);
      if (node) {
        showTooltip(buildTooltipContent(node));
      } else {
        hideTooltip();
      }
    })
    .onNodeClick((node) => {
      showTooltip(buildTooltipContent(node));
    })
    .onBackgroundClick(() => hideTooltip());

  // Custom link color: highlight when hovered (3D)
  instance.linkColor((l) => {
    if (hoveredNode.value) {
      return isLinkHovered(l) ? "#ffffff" : "rgba(255,255,255,0.04)";
    }
    const src = typeof l.source === "object" ? l.source : null;
    return src?.color || "#888888";
  });

  // Custom node opacity (highlights)
  instance.nodeThreeObject((node) => {
    if (perfMode.value) {
      const geom = new THREE.SphereGeometry(1, 12, 12);
      const mat = new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: highlightNodes.size > 0 && !highlightNodes.has(node.id) ? 0.2 : 1,
      });
      return new THREE.Mesh(geom, mat);
    }
    return buildNodeObject3D(node);
  });

  return instance;
}

// ─── Layout presets ──────────────────────────────────────────────────────────
function applyLayout(instance) {
  if (!instance) return;
  const modes = {
    compact: { link: 30, charge: -50 },
    default: { link: 80, charge: -150 },
    spread: { link: 160, charge: -400 },
  };
  const m = modes[layoutMode.value] || modes.default;
  try {
    instance.d3Force("link")?.distance(m.link);
    instance.d3Force("charge")?.strength(m.charge);
    instance.d3ReheatSimulation();
  } catch (e) {
    console.warn("Layout apply error:", e);
  }
}

// ─── Initialize 2D Graph ────────────────────────────────────────────────────
function init2D(wrapper, data) {
  const instance = ForceGraph2D()(wrapper)
    .graphData({ nodes: [], links: [] })
    .backgroundColor("#0a0a0f")
    .nodeRelSize(4)
    .linkColor((l) => {
      if (hoveredNode.value) {
        return isLinkHovered(l) ? "#ffffff" : "rgba(255,255,255,0.04)";
      }
      const src = typeof l.source === "object" ? l.source : null;
      return src?.color || "#888888";
    })
    .linkWidth(1.5)
    .linkCurvature(0)
    .linkDirectionalArrowLength(5)
    .linkDirectionalArrowRelPos(0.99)
    .linkLabel((l) => l.type || "")
    .d3AlphaDecay(0.05)
    .d3VelocityDecay(0.4)
    .onNodeHover((node) => {
      updateHighlight(node);
      if (node) {
        showTooltip(buildTooltipContent(node));
      } else {
        hideTooltip();
      }
    })
    .onNodeClick((node) => {
      showTooltip(buildTooltipContent(node));
    })
    .onBackgroundClick(() => hideTooltip());

  // Custom node rendering with glow + label
  applyLayout(instance);

  instance.nodeCanvasObject((node, ctx, globalScale) => {
    // Skip nodes without valid positions (before first simulation tick)
    if (!node.x || !Number.isFinite(node.x)) return;

    const label = node.name || "";
    const size = 5;
    const isDimmed = highlightNodes.size > 0 && !highlightNodes.has(node.id);

    // Glow halo
    if (!isDimmed) {
      const grad = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, size * 3);
      grad.addColorStop(0, node.color + "60");
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(node.x, node.y, size * 3, 0, 2 * Math.PI);
      ctx.fill();
    }

    // Core circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = isDimmed ? node.color + "40" : node.color;
    ctx.fill();
    ctx.strokeStyle = isDimmed ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.5)";
    ctx.lineWidth = isDimmed ? 0.5 : 1.5;
    ctx.stroke();

    // Label
    if (showNodeLabels.value && !isDimmed && globalScale > 0.5) {
      const fontSize = Math.max(10, 12 / globalScale);
      ctx.font = `${fontSize}px "Inter", sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "rgba(255,255,255,0.7)";
      ctx.fillText(label, node.x, node.y + size + 4);
    }
  });

  return instance;
}

// ─── Init / Destroy ──────────────────────────────────────────────────────────
function initGraph() {
  destroyGraph();
  const data = buildFreshData();
  if (data.nodes.length === 0) return;

  const wrapper = dimension.value === "2d" ? wrapper2d.value : wrapper3d.value;
  if (!wrapper) return;

  try {
    const fn = dimension.value === "2d" ? init2D : init3D;
    graphInstance = fn(wrapper, data);

    graphInstance.graphData(data);
    setTimeout(() => {
      try {
        graphInstance.zoomToFit(400, 40);
      } catch {}
    }, 500);
  } catch (e) {
    console.error("Graph init error:", e);
    graphError.value = e.message;
  }
}

function destroyGraph() {
  if (graphInstance) {
    try {
      if (graphInstance._destructor) graphInstance._destructor();
    } catch {}
    graphInstance = null;
  }
  if (wrapper2d.value) wrapper2d.value.innerHTML = "";
  if (wrapper3d.value) wrapper3d.value.innerHTML = "";
}

// ─── Change layout (2D only) ─────────────────────────────────────────────────
function setLayout(mode) {
  layoutMode.value = mode;
  if (dimension.value === "2d" && graphInstance) {
    applyLayout(graphInstance);
  }
}

// ─── Toggle performance mode (3D only) ───────────────────────────────────────
function togglePerfMode() {
  perfMode.value = !perfMode.value;
  if (dimension.value === "3d" && props.nodes.length > 0) {
    initGraph();
  }
}

// ─── Toggle 2D/3D ────────────────────────────────────────────────────────────
function toggleDimension() {
  dimension.value = dimension.value === "2d" ? "3d" : "2d";
  layoutMode.value = "default";
  nextTick(() => initGraph());
}

// ─── Fullscreen ──────────────────────────────────────────────────────────────
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    containerRef.value?.requestFullscreen?.();
    isFullscreen.value = true;
  } else {
    document.exitFullscreen?.();
    isFullscreen.value = false;
  }
}

// ─── Watch data changes ──────────────────────────────────────────────────────
watch(
  () => [props.nodes, props.relationships, props.labelProps],
  () => {
    if (graphInstance) {
      try {
        graphInstance.graphData(buildFreshData());
        setTimeout(() => {
          try {
            graphInstance.zoomToFit(400, 40);
          } catch {}
        }, 500);
      } catch (e) {
        console.error("Graph update error:", e);
      }
    } else {
      initGraph();
    }
  }
);

// ─── Lifecycle ───────────────────────────────────────────────────────────────
onMounted(() => {
  if (props.nodes.length > 0) initGraph();
});

onBeforeUnmount(() => {
  destroyGraph();
});

// ─── Events ──────────────────────────────────────────────────────────────────
function onMouseMove(e) {
  mousePos.value = { x: e.clientX, y: e.clientY };
}

document.addEventListener("fullscreenchange", () => {
  isFullscreen.value = !!document.fullscreenElement;
  if (graphInstance && containerRef.value) {
    // Resize renderer to fullscreen dimensions, then re-zoom
    setTimeout(() => {
      try {
        const w = containerRef.value.clientWidth;
        const h = containerRef.value.clientHeight;
        if (w > 0 && h > 0) {
          graphInstance.width(w).height(h);
        }
        graphInstance.zoomToFit(400, 40);
      } catch {}
    }, 300);
  }
});
</script>

<template>
  <div class="graph-container" ref="containerRef" @mousemove="onMouseMove">
    <!-- 2D Wrapper -->
    <div v-if="dimension === '2d'" ref="wrapper2d" class="graph-wrapper" />
    <!-- 3D Wrapper -->
    <div v-if="dimension === '3d'" ref="wrapper3d" class="graph-wrapper" />

    <!-- Controls -->
    <div class="graph-controls">
      <button
        :title="dimension === '2d' ? '切换 3D' : '切换 2D'"
        :class="{ active: dimension === '3d' }"
        @click="toggleDimension"
      >
        {{ dimension === "2d" ? "3D" : "2D" }}
      </button>
      <!-- Performance mode toggle (3D only) -->
      <button
        v-if="dimension === '3d' && hasData"
        :title="perfMode ? '标准渲染' : '性能模式'"
        :class="{ active: perfMode }"
        @click="togglePerfMode"
      >Z</button>
      <!-- Label toggle (2D only) -->
      <button
        v-if="dimension === '2d'"
        :title="showNodeLabels ? '隐藏名称' : '显示名称'"
        :class="{ active: showNodeLabels }"
        @click="showNodeLabels = !showNodeLabels"
      >N</button>
      <!-- Layout buttons (2D only) -->
      <button
        v-if="dimension === '2d'"
        title="紧凑布局"
        :class="{ active: layoutMode === 'compact' }"
        @click="setLayout('compact')"
      >&#8801;</button>
      <button
        v-if="dimension === '2d'"
        title="默认布局"
        :class="{ active: layoutMode === 'default' }"
        @click="setLayout('default')"
      >&#9678;</button>
      <button
        v-if="dimension === '2d'"
        title="松散布局"
        :class="{ active: layoutMode === 'spread' }"
        @click="setLayout('spread')"
      >&#8853;</button>
      <!-- Separator (2D only) -->
      <div v-if="dimension === '2d'" class="ctrl-sep" />
      <button
        :title="isFullscreen ? '退出全屏' : '全屏'"
        :class="{ active: isFullscreen }"
        @click="toggleFullscreen"
      >
        {{ isFullscreen ? "✕" : "⛶" }}
      </button>
      <button
        v-if="hasData"
        :title="showPropPanel ? '隐藏属性面板' : '显示属性面板'"
        :class="{ active: showPropPanel }"
        @click="showPropPanel = !showPropPanel"
      >P</button>
    </div>

    <!-- Floating prop config panel -->
    <div v-if="hasData && showPropPanel" class="prop-panel">
      <div class="prop-panel-header">
        节点显示属性
        <span class="prop-panel-close" @click="showPropPanel = false">✕</span>
      </div>
      <LabelDisplayConfig
        :nodes="props.nodes"
        :label-props="props.labelProps"
        @update:label-props="$emit('update:labelProps', $event)"
      />
    </div>

    <!-- Error -->
    <div v-if="graphError" class="overlay" style="pointer-events: none">
      <div class="icon">&#9888;</div>
      <p style="color: #ec7063">图谱渲染错误: {{ graphError }}</p>
    </div>

    <!-- Empty -->
    <div v-if="!hasData && !graphError" class="overlay">
      <div class="icon">&#9673;</div>
      <p>输入 Cypher 查询语句，点击执行渲染图谱</p>
    </div>

    <!-- Tooltip -->
    <div class="tooltip" ref="tooltipRef" style="display: none" />

    <!-- Hint -->
    <div v-if="hasData" class="graph-hint">
      滚轮缩放 · 拖拽平移 · 悬停查看属性
    </div>
  </div>
</template>
