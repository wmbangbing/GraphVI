<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed, nextTick } from "vue";
import ForceGraph2D from "force-graph";
import ForceGraph3D from "3d-force-graph";
import * as THREE from "three";
import SpriteText from "three-spritetext";
import { markRaw } from "vue";
// LabelDisplayConfig merged into panel directly

// ─── Color Palette ───────────────────────────────────────────────────────────
const LABEL_COLORS = [
  "#e74c3c", "#f1c40f", "#2ecc71", "#3498db",
  "#9b59b6", "#1abc9c", "#e67e22", "#fd79a8",
  "#00cec9", "#ff7675", "#74b9ff", "#55efc4",
];

// ─── Shared geometries (one copy in GPU memory for all nodes) ───────────────
const CORE_SPHERE_GEOM = new THREE.SphereGeometry(0.8, 20, 20);
const INNER_SPHERE_GEOM = new THREE.SphereGeometry(0.6, 20, 20);
const RING_GEOM = new THREE.TorusGeometry(1.2, 0.06, 12, 40);

// ─── Glow Texture (shared across 3D nodes) ──────────────────────────────────
let glowTexture = null;
function getGlowTexture() {
  if (glowTexture) return glowTexture;
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.9)");
  g.addColorStop(0.55, "rgba(255,255,255,0.4)");
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
  dark: { type: Boolean, default: true },
});

const emit = defineEmits(["update:labelProps", "toggleAiSummary"]);

// ─── Refs ────────────────────────────────────────────────────────────────────
const wrapper2d = ref(null);
const wrapper3d = ref(null);
const containerRef = ref(null);
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
const showSearch = ref(false);
const searchQuery = ref("");
const tooltipNode = ref(null);

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

// ─── Legend Data ──────────────────────────────────────────────────────────────
const legendLabels = computed(() => {
  return Object.entries(colorMap.value)
    .map(([label, color]) => ({ label, color }))
    .sort((a, b) => a.label.localeCompare(b.label));
});

const legendWithProps = computed(() => {
  const propMap = {};
  props.nodes.forEach((n) => {
    const label = primaryLabel(n.labels);
    if (!propMap[label]) {
      propMap[label] = { props: Object.keys(n.properties || {}), label };
    }
  });
  return legendLabels.value.map((item) => ({
    ...item,
    props: propMap[item.label]?.props || [],
  }));
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
const graphBg = computed(() => (props.dark ? "#0a0a0f" : "#f5f6fa"));

function forceRender2D() {
  if (dimension.value === "2d" && graphInstance) {
    const k = graphInstance.zoom();
    if (k !== null) graphInstance.zoom(k);
  }
}

// ─── Search ───────────────────────────────────────────────────────────────────
const searchResults = computed(() => {
  if (!searchQuery.value || !graphInstance) return [];
  const q = searchQuery.value.toLowerCase();
  const data = graphInstance.graphData();
  if (!data?.nodes) return [];
  return data.nodes
    .filter((n) => n.name && n.name.toLowerCase().includes(q))
    .slice(0, 20);
});

function focusNode(node) {
  if (!graphInstance || !node || !Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
  if (dimension.value === "2d") {
    graphInstance.centerAt(node.x, node.y, 1000);
    graphInstance.zoom(2.5, 1500);
  } else {
    const z = node.z || 0;
    graphInstance.cameraPosition(
      { x: node.x, y: node.y - 25, z: z + 55 },
      { x: node.x, y: node.y, z },
      1000
    );
  }
  updateHighlight(node);
  if (dimension.value === "3d") refresh3DHighlights();
  showTooltip(node);
  setTimeout(() => {
    showSearch.value = false;
    searchQuery.value = "";
  }, 2000);
}

// ─── Tooltip (persistent info panel, top-left) ──────────────────────────────
// Extract URL from markdown or plain text
function extractUrl(v) {
  if (typeof v !== "string") return null;
  // Markdown image: ![alt](url) or Markdown link: [text](url)
  const mdMatch = v.match(/!?\[.*?\]\((\S+?)\)/);
  if (mdMatch) return mdMatch[1];
  // Plain URL
  if (v.startsWith("http://") || v.startsWith("https://")) return v;
  return null;
}

function isImageUrl(v) {
  const url = extractUrl(v);
  return url && /\.(jpg|jpeg|png|gif|webp|svg|bmp)([?#]|$)/i.test(url);
}

function isVideoUrl(v) {
  const url = extractUrl(v);
  return url && /\.(mp4|webm|ogg|mov|avi)([?#]|$)/i.test(url);
}

function extractMediaUrl(v) {
  return extractUrl(v);
}

function isHttpUrl(v) {
  return !!extractUrl(v);
}

function showTooltip(node) {
  tooltipNode.value = node;
}

function hideTooltip() {
  tooltipNode.value = null;
}

// ─── Build 3D node object ────────────────────────────────────────────────────
function buildNodeObject3D(node) {
  const group = new THREE.Group();

  // Core sphere (white center for brightness)
  const coreMat = new THREE.MeshBasicMaterial({
    color: "#ffffff",
    transparent: true,
    opacity: 1,
  });
  group.add(new THREE.Mesh(CORE_SPHERE_GEOM, coreMat));

  // Colored inner sphere
  const innerMat = new THREE.MeshBasicMaterial({
    color: node.color,
    transparent: true,
    opacity: 0.7,
  });
  group.add(new THREE.Mesh(INNER_SPHERE_GEOM, innerMat));

  // Glow sprite
  const spriteMat = new THREE.SpriteMaterial({
    map: getGlowTexture(),
    color: node.color,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(spriteMat);
  sprite.scale.set(6, 6, 1);
  group.add(sprite);

  // Hover ring (hidden by default) — TorusGeometry for 360° visibility
  const ringMat = new THREE.MeshBasicMaterial({
    color: "#ffffff",
    transparent: true,
    opacity: 0,
    depthWrite: false,
  });
  const ring = new THREE.Mesh(RING_GEOM, ringMat);
  ring.rotation.x = Math.PI / 2;
  ring.visible = false;
  group.add(ring);

  // Store material references for dynamic updates
  group.userData = { coreMat, innerMat, spriteMat, sprite, ringMat, ring, color: node.color, nodeId: node.id, ringScale: 1 };
  nodeObjects3D.set(node.id, group);

  // Label sprite (shown/hidden via showNodeLabels)
  const label = new SpriteText(node.name || "");
  label.color = props.dark ? "rgba(255,255,255,0.9)" : "rgba(0,0,0,0.85)";
  label.textHeight = 2.5;
  label.position.set(0, 3, 0);
  // Ensure label always renders on top: ignore depth buffer + highest render order
  label.material.depthTest = false;
  label.material.depthWrite = false;
  label.renderOrder = Infinity;
  label.visible = showNodeLabels.value;
  group.userData.label = label;
  group.add(label);

  return markRaw(group);
}

// ─── 3D node object tracking for dynamic highlight updates ───────────────────
const nodeObjects3D = new Map();

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

  if (dimension.value === "3d") refresh3DHighlights();
  else forceRender2D();
}

// Check if a link connects to the hovered node (by ID, not object ref)
function isLinkHovered(l) {
  if (!hoveredNode.value) return false;
  const id = hoveredNode.value.id;
  const sId = typeof l.source === "object" ? l.source.id : l.source;
  const tId = typeof l.target === "object" ? l.target.id : l.target;
  return sId === id || tId === id;
}

// ─── Dynamic 3D highlight refresh ───────────────────────────────────────────
function refresh3DHighlights() {
  nodeObjects3D.forEach((group) => {
    const { coreMat, innerMat, spriteMat, sprite, ringMat, ring, color, nodeId } = group.userData;
    const isHovered = hoveredNode.value?.id === nodeId;
    const isDimmed = highlightNodes.size > 0 && !highlightNodes.has(nodeId);

    // --- Hovered node ---
    if (isHovered) {
      coreMat.color.set("#ffffff");
      coreMat.opacity = 1;
      innerMat.color.set("#ffffff");
      innerMat.opacity = 1;
      sprite.scale.set(12, 12, 1);
      spriteMat.opacity = 1;
      spriteMat.color.set("#ffffff");
      sprite.visible = true;
      ringMat.color.set("#6c5ce7");
      ringMat.opacity = 1;
      ring.scale.set(1, 1, 1);
      ring.visible = true;
      return;
    }

    // --- Not hovered: default appearance (no dimming in 3D) ---
    coreMat.color.set("#ffffff");
    coreMat.opacity = 1;
    innerMat.color.set(color);
    innerMat.opacity = 0.7;
    sprite.scale.set(6, 6, 1);
    spriteMat.opacity = 0.9;
    spriteMat.color.set(color);
    sprite.visible = true;
    ring.visible = false;
  });
}

// ─── Initialize 3D Graph ────────────────────────────────────────────────────
function init3D(wrapper, data) {
  const isPerf = perfMode.value;

  const instance = ForceGraph3D()(wrapper)
    .graphData({ nodes: [], links: [] })
    .backgroundColor(graphBg.value)
    .nodeThreeObject((node) => {
      if (isPerf) {
        // Performance mode: single sphere, no glow
        const geom = new THREE.SphereGeometry(1, 12, 12);
        const mat = new THREE.MeshBasicMaterial({ color: node.color });
        return new THREE.Mesh(geom, mat);
      }
      return buildNodeObject3D(node);
    })
    .nodeThreeObjectExtend(true)
    .nodeRelSize(isPerf ? 2.5 : 3)
    .linkColor((l) => {
      if (hoveredNode.value) {
        return isLinkHovered(l) ? "#ffffff" : "rgba(255,255,255,0.12)";
      }
      const src = typeof l.source === "object" ? l.source : null;
      return src?.color || "#888888";
    })
    .linkWidth(0.3)
    .linkCurvature(0)
    .linkDirectionalArrowLength(isPerf ? 0 : 2)
    .linkDirectionalArrowRelPos(0.99)
    .linkDirectionalParticles(isPerf ? 0 : 1)
    .linkDirectionalParticleSpeed(0.01)
    .linkDirectionalParticleWidth(1.5)
    .linkDirectionalParticleColor((l) => {
      const src = typeof l.source === "object" ? l.source : null;
      return src?.color || "#6c5ce7";
    })
    .d3AlphaDecay(0.05)
    .d3VelocityDecay(0.4)
    .showPointerCursor((d) => !!d)
    .onNodeHover(null)
    .onNodeClick((node) => {
      updateHighlight(node);
      if (node) showTooltip(node);
    })
    .onBackgroundClick(() => {
      highlightNodes.clear();
      hoveredNode.value = null;
      if (dimension.value === "3d") refresh3DHighlights();
      else forceRender2D();
    })
    .onEngineStop(() => {
      try { instance.zoomToFit(400, 40); } catch {}
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
    .backgroundColor(graphBg.value)
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
    .showPointerCursor((d) => !!d)
    .onNodeHover(null)
    .onNodeClick((node) => {
      updateHighlight(node);
      if (node) showTooltip(node);
    })
    .onBackgroundClick(() => {
      highlightNodes.clear();
      hoveredNode.value = null;
      if (dimension.value === "3d") refresh3DHighlights();
      else forceRender2D();
    })
    .onEngineStop(() => {
      try { instance.zoomToFit(400, 40); } catch {}
    });

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
    ctx.strokeStyle = isDimmed ? "rgba(255,255,255,0.1)" : (props.dark ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.3)");
    ctx.lineWidth = isDimmed ? 0.5 : 1.5;
    ctx.stroke();

    // Label
    if (showNodeLabels.value && !isDimmed && globalScale > 0.5) {
      const fontSize = Math.max(10, 12 / globalScale);
      ctx.font = `${fontSize}px "Inter", sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = props.dark ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.75)";
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

    // Explicitly set renderer size to container dimensions — on first mount
    // the wrapper might not have its final layout width yet, causing zoomToFit
    // to calculate offsets based on a too-narrow viewport.
    if (containerRef.value?.clientWidth > 0) {
      graphInstance.width(containerRef.value.clientWidth);
      graphInstance.height(containerRef.value.clientHeight);
    }

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
  // Dispose GPU resources before clearing references
  nodeObjects3D.forEach((group) => {
    group.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (child.material.map) child.material.map.dispose();
        child.material.dispose();
      }
    });
  });
  nodeObjects3D.clear();
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
    // Clear hover state before graphData() — force-graph does not fire
    // onNodeHover(null) after data replacement due to shadow canvas
    // throttling (800ms) and color registry index collision, leaving a
    // stale highlight on the canvas.
    hoveredNode.value = null;
    highlightNodes.clear();
    hideTooltip();

    if (graphInstance) {
      nodeObjects3D.clear();
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

// Update graph background and 3D label colors when theme changes
watch(() => props.dark, () => {
  if (graphInstance) graphInstance.backgroundColor(graphBg.value);
  const labelColor = props.dark ? "rgba(255,255,255,0.9)" : "rgba(0,0,0,0.85)";
  nodeObjects3D.forEach((group) => {
    if (group.userData.label) group.userData.label.color = labelColor;
  });
});

// Toggle 3D node labels
watch(showNodeLabels, (v) => {
  nodeObjects3D.forEach((group) => {
    if (group.userData.label) group.userData.label.visible = v;
  });
});

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

    <!-- Search bar -->
    <div v-if="hasData && showSearch" class="graph-search">
      <el-input
        v-model="searchQuery"
        placeholder="搜索节点名称..."
        size="small"
        clearable
        autofocus
        @keydown.esc="showSearch = false; searchQuery = ''"
      />
      <div v-if="searchResults.length > 0" class="search-results">
        <div
          v-for="n in searchResults"
          :key="n.id"
          class="search-result-item"
          @click="focusNode(n)"
        >
          <span class="search-result-name">{{ n.name }}</span>
          <span class="search-result-label">{{ primaryLabel(n.labels) }}</span>
        </div>
      </div>
      <div v-else-if="searchQuery && searchResults.length === 0" class="search-results">
        <div class="search-result-empty">未找到匹配节点</div>
      </div>
    </div>

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
      <!-- Search -->
      <button
        v-if="hasData"
        :title="showSearch ? '关闭搜索' : '搜索节点'"
        :class="{ active: showSearch }"
        @click="showSearch = !showSearch"
      >S</button>
      <!-- Label toggle -->
      <button
        v-if="hasData"
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
        :title="showPropPanel ? '隐藏面板' : '显示面板'"
        :class="{ active: showPropPanel }"
        @click="showPropPanel = !showPropPanel"
      >P</button>
      <div v-if="hasData" class="ctrl-sep" />
      <button
        v-if="hasData"
        title="AI 总结"
        class="ai-ctrl-btn"
        @click="$emit('toggleAiSummary')"
      >AI</button>
    </div>

    <!-- Floating panel: legend with inline property selector -->
    <div v-if="hasData && showPropPanel" class="prop-panel">
      <div class="prop-panel-header">
        图例
        <span class="prop-panel-close" @click="showPropPanel = false">✕</span>
      </div>
      <div class="legend-merged">
        <div v-for="item in legendWithProps" :key="item.label" class="legend-merged-row">
          <span class="legend-merged-swatch" :style="{ background: item.color }" />
          <span class="legend-merged-label" :title="item.label">{{ item.label }}</span>
          <el-select
            :model-value="labelProps[item.label] || ''"
            size="small"
            class="legend-merged-select"
            @change="$emit('update:labelProps', { ...labelProps, [item.label]: $event })"
          >
            <el-option label="默认" value="" />
            <el-option v-for="p in item.props" :key="p" :label="p" :value="p" />
          </el-select>
        </div>
      </div>
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

    <!-- Tooltip (persistent info panel) -->
    <div v-if="tooltipNode" class="tooltip">
      <div class="tooltip-header">
        <h4>{{ tooltipNode.name || primaryLabel(tooltipNode.labels) }}</h4>
        <span class="tooltip-close" @click="hideTooltip">✕</span>
      </div>
      <span class="label-tag">{{ primaryLabel(tooltipNode.labels) }}</span>
      <table>
        <tr v-for="(v, k) in tooltipNode.properties" :key="k">
          <td>{{ k }}</td>
          <td>
            <img
              v-if="isImageUrl(v)"
              :src="extractMediaUrl(v)"
              class="prop-media"
              @error="$event.target.style.display = 'none'"
            />
            <video v-else-if="isVideoUrl(v)" :src="extractMediaUrl(v)" controls class="prop-media" />
            <a v-else-if="isHttpUrl(v)" :href="extractMediaUrl(v)" target="_blank" rel="noopener">{{ v }}</a>
            <template v-else>{{ String(v) }}</template>
          </td>
        </tr>
      </table>
    </div>

    <!-- Hint -->
    <div v-if="hasData" class="graph-hint">
      滚轮缩放 · 拖拽平移 · 悬停查看属性
    </div>
  </div>
</template>
