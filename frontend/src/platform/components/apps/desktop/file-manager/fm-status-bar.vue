<template>
  <footer class="fm-status-bar">
    <div class="fm-status-left">
      <template v-if="searchKeyword">
        找到 {{ filteredCount }} 个结果
      </template>
      <template v-else>
        <span>{{ itemCount }} 个项目</span>
        <span v-if="selectedItem">已选择 {{ displayName(selectedItem) }}</span>
        <span v-if="selectedItem && !selectedItem.is_folder">({{ selectedSize }})</span>
      </template>
    </div>
    <div class="fm-status-right">
      <button
        class="fm-view-btn"
        :class="{ 'fm-view-btn-active': viewMode === 'list' }"
        type="button"
        title="列表"
        @click="$emit('update:viewMode', 'list')"
      >
        ≣
      </button>
      <button
        class="fm-view-btn"
        :class="{ 'fm-view-btn-active': viewMode === 'grid' }"
        type="button"
        title="图标"
        @click="$emit('update:viewMode', 'grid')"
      >
        ▦
      </button>
    </div>
  </footer>
</template>

<script setup lang="ts">
import type { FileEntry } from '@/shared/api/types'

defineProps<{
  itemCount: number
  folderCount: number
  fileCount: number
  selectedItem: FileEntry | null
  selectedSize: string
  viewMode: 'grid' | 'list'
  searchKeyword: string
  filteredCount: number
  displayName: (file: FileEntry) => string
}>()

defineEmits<{
  (e: 'update:viewMode', mode: 'grid' | 'list'): void
}>()
</script>

<style scoped>
.fm-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 30px;
  padding: 0 14px;
  border-top: 1px solid #d7e0ea;
  background: rgba(250, 252, 255, 0.92);
  font-size: 12px;
  color: #64748b;
}

.fm-status-left {
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-status-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.fm-view-btn {
  width: 28px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.fm-view-btn:hover {
  background: #eaf0f6;
  border-color: #d4dce8;
}

.fm-view-btn-active {
  color: #2563eb;
  background: #edf6ff;
  border-color: #8bb8ee;
}
</style>
