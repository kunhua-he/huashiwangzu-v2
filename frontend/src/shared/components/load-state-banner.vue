<template>
  <div v-if="visible" class="load-state-banner" :class="`load-state-banner-${variant}`">
    <div class="load-state-banner-copy">
      <span class="load-state-banner-title">{{ title }}</span>
      <span v-if="message" class="load-state-banner-message">{{ message }}</span>
      <span v-if="backendMessage && backendMessage !== message" class="load-state-banner-detail">{{ backendMessage }}</span>
    </div>
    <button v-if="showRetry" class="load-state-banner-action" type="button" @click="emit('retry')">
      <el-icon :size="14"><Refresh /></el-icon>
      <span>重试</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import type { ApiErrorInfo } from '@/shared/api/response-transform'

const props = withDefaults(defineProps<{
  status: 'idle' | 'loading' | 'ready' | 'error' | 'stale'
  error?: ApiErrorInfo | null
  staleText?: string
  errorText?: string
  showRetry?: boolean
}>(), {
  staleText: '数据可能不是最新',
  errorText: '加载失败',
  showRetry: true,
})

const emit = defineEmits<{
  retry: []
}>()

const visible = computed(() => props.status === 'error' || props.status === 'stale')
const variant = computed(() => props.status === 'stale' ? 'stale' : 'error')
const title = computed(() => props.status === 'stale' ? props.staleText : props.errorText)
const message = computed(() => props.error?.userMessage || props.error?.error || '')
const backendMessage = computed(() => props.error?.backendMessage || '')
</script>

<style scoped>
.load-state-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 10px;
  border-radius: 6px;
  border: 1px solid #f2d18b;
  background: #fff8e6;
  color: #8a4f00;
  font-size: 12px;
}

.load-state-banner-error {
  border-color: #fecaca;
  background: #fff1f2;
  color: #991b1b;
}

.load-state-banner-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.load-state-banner-title {
  font-weight: 700;
}

.load-state-banner-message,
.load-state-banner-detail {
  line-height: 1.35;
}

.load-state-banner-detail {
  color: #6b7280;
}

.load-state-banner-action {
  flex: none;
  height: 28px;
  border: 1px solid currentColor;
  border-radius: 6px;
  background: #fff;
  color: inherit;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 0 9px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.load-state-banner-action:hover {
  background: rgba(255, 255, 255, 0.72);
}
</style>
