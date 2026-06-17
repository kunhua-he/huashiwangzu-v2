<template>
  <div class="tray-launcher-wrapper">
    <button v-for="app in appList" :key="app.appKey" class="tray-launcher-button" type="button" :title="app.appName" @click="emit('openApp', app.appKey)">
      <AppIcon :icon="app.icon" :size="18" />
    </button>
  </div>
</template>

<script setup lang="ts">
import AppIcon from '@/desktop/components/app-icon.vue'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'

const props = defineProps<{ appList: AppRegistryEntry[] }>()
const emit = defineEmits<{ (e: 'openApp', appKey: string): void }>()
</script>

<style scoped>
.tray-launcher-wrapper { display: flex; align-items: center; gap: 2px; }
.tray-launcher-button {
  width: 24px; height: 24px; border: none; background: transparent; color: #dbeafe;
  cursor: pointer; border-radius: 4px; display: flex; align-items: center; justify-content: center;
  opacity: .82; transition: background .12s, opacity .12s;
}
.tray-launcher-button:hover { background: rgba(255,255,255,.08); opacity: 1; }
</style>
