<template>
  <Teleport to="body">
    <div v-if="show" class="right-sidebar-overlay" @click.self="emit('close')">
      <aside class="right-sidebar-panel">
        <div class="right-sidebar-header"><span>📌 {{ currentTitle }}</span><button class="right-sidebar-close" type="button" @click="emit('close')">✕</button></div>
        <div class="right-sidebar-shortcuts">
          <button v-for="app in appList" :key="app.appKey" class="right-sidebar-shortcut" :class="{ 'right-sidebar-shortcut-active': app.appKey === currentAppKey }" type="button" @click="emit('switch', app.appKey)"><AppIcon :icon="app.icon" :size="18" /><span>{{ app.appName }}</span></button>
        </div>
        <iframe class="right-sidebar-preview" :src="currentPath" title="桌面右侧功能栏预览" />
        <div class="right-sidebar-footer"><button class="right-sidebar-open-button" type="button" @click="emit('open-window', currentAppKey)">在窗口打开</button></div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import AppIcon from '@/desktop/components/app-icon.vue'

const props = defineProps<{ show: boolean; currentPath: string; currentAppKey: string; appList: AppRegistryEntry[] }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'switch', appKey: string): void; (e: 'open-window', appKey: string): void }>()
const currentTitle = computed(() => props.appList.find(x => x.appKey === props.currentAppKey)?.appName || '快捷面板')
</script>

<style scoped>
.right-sidebar-overlay{position:fixed;inset:0;z-index:10001;background:rgba(15,23,42,.12);display:flex;justify-content:flex-end}
.right-sidebar-panel{width:min(520px,48vw);height:calc(100vh - 40px);margin-top:0;background:#0f172a;border-left:1px solid rgba(255,255,255,.1);box-shadow:-12px 0 36px rgba(0,0,0,.35);display:flex;flex-direction:column}
.right-sidebar-header{height:38px;display:flex;align-items:center;justify-content:space-between;color:#dbeafe;font-size:12px;padding:0 10px;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(15,23,42,.95)}
.right-sidebar-close{border:none;background:transparent;color:#cbd5e1;font-size:14px;cursor:pointer}.right-sidebar-shortcuts{display:flex;gap:6px;padding:10px;border-bottom:1px solid rgba(255,255,255,.08);overflow-x:auto}
.right-sidebar-shortcut{display:flex;align-items:center;gap:6px;padding:6px 10px;border-radius:8px;border:1px solid transparent;background:rgba(255,255,255,.04);color:#dbeafe;cursor:pointer;white-space:nowrap}.right-sidebar-shortcut-active{background:rgba(59,130,246,.16);border-color:rgba(59,130,246,.25)}
.right-sidebar-preview{width:100%;flex:1;border:none;background:#fff}.right-sidebar-footer{padding:10px;border-top:1px solid rgba(255,255,255,.08);display:flex;justify-content:flex-end}.right-sidebar-open-button{border:none;background:#2563eb;color:#fff;border-radius:8px;padding:8px 12px;cursor:pointer}
</style>
