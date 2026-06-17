<template>
  <div class="empty-state" :class="[类型]">
    <el-icon :size="图标大小" color="#c0c4cc"><component :is="图标组件" /></el-icon>
    <p class="empty-message">{{ 消息 || '暂时没有内容' }}</p>
    <p v-if="说明" class="empty-description">{{ 说明 }}</p>
    <slot name="操作" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { FolderOpened, Search, ChatDotRound, Document } from '@element-plus/icons-vue'

const 图标映射: Record<string, Component> = {
  folder: FolderOpened,
  search: Search,
  chat: ChatDotRound,
  document: Document,
}

const props = withDefaults(defineProps<{
	类型?: 'full' | 'card' | 'inline'
	消息?: string
	说明?: string
	图标?: string
	图标大小?: number
}>(), {
	类型: 'full',
	图标: 'folder',
	图标大小: 48,
})

const 图标组件 = computed(() => 图标映射[props.图标] || FolderOpened)
</script>

<style scoped>
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #909399; gap: 8px; }
.full { min-height: 300px; padding: 60px 20px; }
.card { min-height: 200px; padding: 40px 20px; background: #fafafa; border-radius: 8px; }
.inline { padding: 20px; }
.empty-message { margin: 0; font-size: 14px; color: #909399; }
.empty-description { margin: 0; font-size: 12px; color: #c0c4cc; }
</style>
