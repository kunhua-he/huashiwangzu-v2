<template>
  <div class="common-state" :class="[type]">
    <div v-if="state === 'loading'" class="state-content">
      <el-icon class="is-loading" :size="iconSize"><Loading /></el-icon>
      <p v-if="message" class="message-text">{{ message }}</p>
    </div>
    <div v-else-if="state === 'error'" class="state-content">
      <el-icon :size="iconSize" color="var(--danger-color, #f56c6c)"><WarningFilled /></el-icon>
      <p class="message-text">{{ message || 'System encountered an error' }}</p>
      <el-button v-if="retryable" type="primary" size="small" @click="emit('retry')">Retry</el-button>
    </div>
    <div v-else-if="state === 'empty'" class="state-content">
      <el-icon :size="iconSize" color="#c0c4cc"><component :is="emptyIcon || 'FolderOpened'" /></el-icon>
      <p class="message-text">{{ message || 'No content' }}</p>
      <slot name="guide" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loading, WarningFilled, FolderOpened } from '@element-plus/icons-vue'

withDefaults(defineProps<{
  state: 'loading' | 'error' | 'empty' | 'normal'
  type?: 'full' | 'card' | 'inline'
  message?: string
  iconSize?: number
  emptyIcon?: string
  retryable?: boolean
}>(), {
  type: 'full',
  iconSize: 48,
  retryable: true
})

const emit = defineEmits<{
  (e: 'retry'): void
}>()
</script>

<style scoped>
.common-state { display: flex; align-items: center; justify-content: center; width: 100%; }
.full { min-height: 300px; padding: 40px; }
.card { min-height: 200px; padding: 20px; background: #fafafa; border-radius: 8px; }
.inline { padding: 12px; }
.state-content { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
.message-text { margin: 0; font-size: 14px; color: #909399; line-height: 1.6; }
</style>
