<template>
  <div class="fm-recycle-view">
    <div class="rv-toolbar">
      <span class="rv-title">回收站</span>
      <el-button size="small" :icon="Refresh" @click="loadList">刷新</el-button>
      <el-button size="small" :disabled="!canWrite || items.length === 0" @click="emptyTrash">清空回收站</el-button>
    </div>
    <section class="rv-file-list" @contextmenu.prevent="handleBlankMenu">
      <div v-if="loading" class="rv-state">加载中...</div>
      <div v-else-if="items.length === 0" class="rv-state">回收站为空</div>
      <div v-else class="rv-content-list">
        <button
          v-for="item in items"
          :key="item.id"
          class="rv-entry"
          type="button"
          @contextmenu.prevent.stop="handleItemMenu(item, $event)"
        >
          <span class="rv-entry-icon">{{ item.item_type === 'folder' ? '📁' : '📄' }}</span>
          <span class="rv-entry-name">{{ item.name }}</span>
          <span class="rv-entry-date">{{ formatDate(item.deleted_at) }}</span>
          <span class="rv-entry-action">
            <el-button v-if="canWrite" size="small" text type="primary" @click.stop="restoreItem(item)">还原</el-button>
            <el-button v-if="canWrite" size="small" text type="danger" @click.stop="permanentDelete(item)">彻底删除</el-button>
          </span>
        </button>
      </div>
    </section>
    <div class="rv-status-bar">
      <span>{{ items.length }} 个项目</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { fetchRecycleBinList, restoreRecycleBinEntry, permanentlyDeleteEntry, emptyRecycleBinRequest } from '@/shared/api/desktop'
import type { RecycleBinEntry } from '@/shared/api/types'
import { usePermission } from '@/shared/composables/use-permission'
import emitter from '@/desktop/events'

const emit = defineEmits<{
  (e: 'context-menu-blank', event: MouseEvent, options: { key: string; label: string; icon?: string; danger?: boolean }[]): void
  (e: 'context-menu-item', event: MouseEvent, item: RecycleBinEntry, options: { key: string; label: string; icon?: string; danger?: boolean }[]): void
}>()

const { isEditorOrAbove } = usePermission()
const canWrite = ref(false)
const items = ref<RecycleBinEntry[]>([])
const loading = ref(false)

onMounted(() => { canWrite.value = isEditorOrAbove.value; void loadList() })

async function loadList() {
  loading.value = true
  try { const res = await fetchRecycleBinList(); if (res.success) items.value = res.data || [] }
  finally { loading.value = false }
}

async function restoreItem(item: RecycleBinEntry) {
  try { await restoreRecycleBinEntry(item.item_type, item.id); ElMessage.success('已还原'); await loadList(); emitter.emit('refresh:file-list', { folderId: 0 } as never) }
  catch { ElMessage.warning('还原失败') }
}

async function permanentDelete(item: RecycleBinEntry) {
  try { await ElMessageBox.confirm('确定彻底删除？', '确认', { type: 'warning' }) } catch { return }
  try { await permanentlyDeleteEntry(item.item_type, item.id); ElMessage.success('已删除'); await loadList(); emitter.emit('refresh:file-list', { folderId: 0 } as never) }
  catch { ElMessage.warning('删除失败') }
}

async function emptyTrash() {
  try { await ElMessageBox.confirm('确定清空回收站？', '确认', { type: 'warning' }) } catch { return }
  try { await emptyRecycleBinRequest(); ElMessage.success('已清空'); await loadList(); emitter.emit('refresh:file-list', { folderId: 0 } as never) }
  catch { ElMessage.warning('清空失败') }
}

function handleBlankMenu(e: MouseEvent) {
  emit('context-menu-blank', e, items.value.length > 0 && canWrite.value ? [
    { key: 'empty-recycle-bin', label: '清空回收站', icon: '🧹', danger: true },
  ] : [])
}

function handleItemMenu(item: RecycleBinEntry, e: MouseEvent) {
  emit('context-menu-item', e, item, canWrite.value ? [
    { key: 'restore', label: '还原', icon: '↩' },
    { key: 'delete-permanently', label: '彻底删除', icon: '🗑', danger: true },
  ] : [])
}

function formatDate(d: string): string {
  try { return new Date(d).toLocaleString() } catch { return d }
}
</script>

<style scoped>
.fm-recycle-view { height: 100%; display: flex; flex-direction: column; background: #f8fafc; }
.rv-toolbar { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-bottom: 1px solid #dbe4ee; background: #f1f5f9; flex-shrink: 0; }
.rv-title { flex: 1; font-weight: 600; font-size: 14px; color: #1f2937; }
.rv-file-list { flex: 1; overflow: auto; min-height: 0; background: #f8fafc; }
.rv-state { min-height: 100%; display: grid; place-items: center; color: #64748b; font-size: 13px; padding: 40px; }
.rv-content-list { display: grid; align-content: start; gap: 4px; padding: 4px 0; }
.rv-entry { display: grid; grid-template-columns: 28px minmax(0, 1fr) 140px auto; align-items: center; gap: 8px; padding: 4px 10px; min-width: 0; border: 1px solid transparent; border-radius: 7px; background: transparent; color: #243244; cursor: pointer; user-select: none; text-align: left; }
.rv-entry:hover { background: rgba(219, 234, 254, 0.82); border-color: rgba(96, 165, 250, 0.56); }
.rv-entry-icon { font-size: 18px; text-align: center; }
.rv-entry-name { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rv-entry-date { font-size: 12px; color: #64748b; }
.rv-entry-action { display: flex; gap: 4px; }
.rv-status-bar { display: flex; align-items: center; padding: 4px 12px; border-top: 1px solid #dbe4ee; background: #f1f5f9; font-size: 12px; color: #64748b; flex-shrink: 0; }
</style>
