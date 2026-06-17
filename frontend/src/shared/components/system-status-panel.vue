<template>
  <div class="system-status-panel">
    <div v-if="加载中" class="status-loading">加载系统状态中...</div>
    <div v-else-if="错误" class="status-error">{{ 错误 }}</div>
    <template v-else>
      <div v-if="!显示详情 && !全部正常" class="status-warning-bar">
        ⚠️ 系统部分服务异常，请联系管理员
      </div>
      <div v-if="显示详情" class="status-detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="(值, 键) in 系统状态" :key="键" :label="键">
            <el-tag :type="值.status ? 'success' : 'danger'" size="small">
              {{ 值.status ? '正常' : '异常' }}
            </el-tag>
            <span class="status-message">{{ 值.message }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/shared/api'
import type { SystemStatus, SystemStatusEntry } from '@/shared/api/types'

const props = withDefaults(defineProps<{ 显示详情?: boolean }>(), { 显示详情: false })

const 系统状态 = ref<SystemStatus | null>(null)
const 加载中 = ref(false)
const 错误 = ref('')

const 全部正常 = computed(() => {
  if (!系统状态.value) return true
  return Object.values(系统状态.value).every((v: SystemStatusEntry) => v.status)
})

async function 加载状态() {
  加载中.value = true
  错误.value = ''
  try {
    const res = await api.get('/system/status')
    const r = res.data
    if (r.success) {
      系统状态.value = r.data
    } else {
      错误.value = r.error || '加载失败'
    }
  } catch (e: unknown) {
    错误.value = (e as {error?: string})?.error || '系统状态加载失败'
  } finally {
    加载中.value = false
  }
}

defineExpose({ 加载状态 })
onMounted(() => { 加载状态() })
</script>

<style scoped>
.system-status-panel { margin-bottom: 12px; }
.status-loading { color: var(--文字信息); padding: 8px 0; font-size: 14px; }
.status-error { color: var(--el-color-danger); padding: 8px 0; }
.status-warning-bar { background: var(--el-color-warning-light-9); color: var(--el-color-warning); padding: 8px 16px; border-radius: 4px; font-size: 14px; margin-bottom: 8px; }
.status-message { margin-left: 8px; font-size: 13px; color: var(--文字次要); }
</style>
