<template>
  <div class="knowledge-progress">
    <div class="progress-row">
      <el-progress :percentage="progress?.percent ?? 0" :stroke-width="8" :status="status" class="progress-bar" />
      <b class="progress-value">{{ progress?.percent ?? 0 }}%</b>
    </div>
    <div v-if="!compact" class="phase-bar">
      <span v-for="item in progress?.phase_list || []" :key="item.name" :class="`phase-${item.status}`">{{ item.name }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeProgress } from '@/shared/api/types'

const props = defineProps<{ progress?: KnowledgeProgress; compact?: boolean }>()
const status = computed(() => {
  const list = props.progress?.phase_list || []
  if (list.some(item => item.status === 'failed')) return 'exception'
  if ((props.progress?.percent || 0) >= 100) return 'success'
  return undefined
})
</script>

<style scoped>
.knowledge-progress { min-width: 180px; }
.progress-row { display:flex; align-items:center; gap:10px; }
.progress-bar { flex:1; min-width:0; }
.progress-value { font-size:13px; color:#0f172a; white-space:nowrap; flex-shrink:0; }
.phase-bar { margin-top:6px; display:flex; flex-wrap:wrap; gap:4px; }
.phase-bar span { font-size:11px; line-height:1; padding:4px 6px; border-radius:7px; background:#f1f5f9; color:#64748b; }
.phase-bar .phase-done { color:#047857; background:#ecfdf5; }
.phase-bar .phase-running { color:#1d4ed8; background:#eff6ff; }
.phase-bar .phase-failed { color:#b91c1c; background:#fef2f2; }
</style>
