<template>
  <el-dialog
    :model-value="visible"
    :title="item ? displayName(item) : '属性'"
    width="420px"
    :close-on-click-modal="true"
    @update:model-value="$emit('update:visible', $event)"
  >
    <template v-if="item">
      <div class="prop-row">
        <span class="prop-label">名称</span>
        <span class="prop-value">{{ displayName(item) }}</span>
      </div>
      <div class="prop-row">
        <span class="prop-label">类型</span>
        <span class="prop-value">{{ item.is_folder ? '文件夹' : (item.format?.toUpperCase() || '文件') }}</span>
      </div>
      <div class="prop-row">
        <span class="prop-label">大小</span>
        <span class="prop-value">{{ item.is_folder ? '-' : formatSize(item.file_size) }}</span>
      </div>
      <div class="prop-row">
        <span class="prop-label">创建时间</span>
        <span class="prop-value">{{ item.created_at || '-' }}</span>
      </div>
    </template>
    <div v-else class="prop-empty">请选择一个文件或文件夹</div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { FileEntry } from '@/shared/api/types'

defineProps<{
  visible: boolean
  item: FileEntry | null
  displayName: (file: FileEntry) => string
  formatSize: (size: number) => string
}>()

defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()
</script>

<style scoped>
.prop-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid #f1f5f9;
}

.prop-row:last-child {
  border-bottom: none;
}

.prop-label {
  width: 80px;
  flex-shrink: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
}

.prop-value {
  font-size: 13px;
  color: #1e293b;
  line-height: 1.6;
  word-break: break-word;
}

.prop-empty {
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}
</style>
