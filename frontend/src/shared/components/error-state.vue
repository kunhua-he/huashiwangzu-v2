<template>
  <div class="error-state" :class="[类型]">
    <el-icon :size="图标大小" color="#f56c6c"><WarningFilled /></el-icon>
    <p class="error-message">{{ 消息 || '系统开小差了' }}</p>
    <p v-if="说明" class="error-description">{{ 说明 }}</p>
    <div v-if="可重试" class="error-actions">
      <el-button type="primary" size="small" @click="$emit('重试')">重新加载</el-button>
      <el-button size="small" @click="$emit('返回')">返回首页</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { WarningFilled } from '@element-plus/icons-vue'

withDefaults(defineProps<{
  类型?: 'full' | 'card' | 'inline'
  消息?: string
  说明?: string
  图标大小?: number
  可重试?: boolean
}>(), {
  类型: 'full',
  图标大小: 48,
  可重试: true,
})

defineEmits<{
  重试: []
  返回: []
}>()
</script>

<style scoped>
.error-state { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 12px; }
.full { min-height: 300px; padding: 60px 20px; }
.card { min-height: 200px; padding: 40px 20px; background: #fff5f5; border-radius: 8px; }
.inline { padding: 20px; }
.error-message { margin: 0; font-size: 14px; color: #606266; }
.error-description { margin: 0; font-size: 12px; color: #909399; }
.error-actions { display: flex; gap: 12px; margin-top: 8px; }
</style>
