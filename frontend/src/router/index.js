import { createRouter, createWebHistory } from "vue-router";
import GraphPage from "../views/GraphPage.vue";
import SettingsPage from "../views/SettingsPage.vue";

const routes = [
  {
    path: "/",
    name: "graph",
    component: GraphPage,
  },
  {
    path: "/settings",
    name: "settings",
    component: SettingsPage,
  },
];

// Auto-detect deployment subpath from current URL.
// If the last path segment is a known Vue route, it's part of routing
// and the base is everything before it. Otherwise the whole path IS the base.
// Examples:
//   /graphvi/settings → last="settings" (route) → base = /graphvi/
//   /graphvi          → last="graphvi" (not route) → base = /graphvi/
//   /settings         → last="settings" (route) → base = /
//   /                 → last="" (route) → base = /
const detectedBase = (() => {
  const knownRoutes = new Set(["", "settings"]);
  const segments = window.location.pathname.replace(/\/$/, "").split("/");
  const last = segments[segments.length - 1] || "";
  if (knownRoutes.has(last)) {
    // Last segment is a route → base is everything before it
    return segments.slice(0, -1).join("/") + "/";
  }
  // Last segment is the deployment prefix itself
  return window.location.pathname.replace(/\/+$/, "") + "/";
})();

const router = createRouter({
  history: createWebHistory(detectedBase),
  routes,
});

// Expose API base to all components (strip trailing / for clean path joining)
window.__API_BASE__ = detectedBase === "/" ? "" : detectedBase.replace(/\/$/, "");

export default router;
