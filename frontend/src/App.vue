<script setup>
import { watch } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const isDark = localStorage.getItem("theme") !== "light";
document.documentElement.classList.toggle("dark", isDark);

router.afterEach(() => {
  const dark = localStorage.getItem("theme") !== "light";
  document.documentElement.classList.toggle("dark", dark);
});
</script>

<template>
  <router-view v-slot="{ Component }">
    <keep-alive>
      <component :is="Component" />
    </keep-alive>
  </router-view>
</template>
