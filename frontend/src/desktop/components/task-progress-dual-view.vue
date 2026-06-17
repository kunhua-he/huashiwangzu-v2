<template>
  <div>
    <CommonState v-if="!activeTasks.length && !recentLogs.length" state="empty" message="No pending tasks" />
    <template v-else>
      <el-table :data="activeTasks" class="knowledge-table" stripe>
        <el-table-column label="File" min-width="180" show-overflow-tooltip>
          <template #default="{ row }"><span class="file-link" @click="emit('openFile', row.file_id)">{{ row.file_name || `File ${row.file_id}` }}</span></template>
        </el-table-column>
        <el-table-column label="Progress" min-width="180">
          <template #default="{ row }"><KnowledgeProgress :progress="row.progress" compact /></template>
        </el-table-column>
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
      </el-table>
      <div v-if="recentLogs.length" class="activity-log">
        <div class="log-title">Live Activity</div>
        <div class="log-list">
          <div v-for="(log, i) in recentLogs" :key="i" class="log-row">
            <span class="log-time">{{ log.time?.slice(11, 19) || '' }}</span>
            <span :class="['log-status', `log-status-${log.status}`]">{{ log.status === 'pending' ? 'Queued' : 'Processing' }}</span>
            <span class="log-file">{{ log.file_name }}</span>
            <span class="log-step">{{ log.current_step }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeTaskEntry } from '@/shared/api/types'
import KnowledgeProgress from '@/shared/components/knowledge-progress.vue'
import CommonState from '@/shared/components/common-state.vue'

const props = defineProps<{
  taskList: KnowledgeTaskEntry[]
  recentLogs: Array<{ time: string; file_id: number; file_name: string; status: string; current_step: string; percent: number }>
  statusType: (status: string) => string
}>()
const emit = defineEmits<{ openFile: [fileId: number] }>()
const activeTasks = computed(() => props.taskList.filter(t => t.status === 'pending' || t.status === 'running'))
</script>

<style scoped>
.file-link { color:#0f172a; cursor:pointer; font-weight:600; padding:2px 6px; border-radius:6px; transition:background .15s ease; display:inline-block; }
.file-link:hover { background:rgba(15,23,42,.06); }
.activity-log { margin-top:14px; border:1px solid #e2e8f0; border-radius:12px; overflow:hidden; }
.log-title { padding:8px 12px; font-size:12px; font-weight:700; color:#475569; background:#f8fafc; border-bottom:1px solid #e2e8f0; }
.log-list { max-height:160px; overflow-y:auto; padding:4px 0; }
.log-row { display:flex; align-items:center; gap:8px; padding:4px 12px; font-size:12px; font-family:monospace; }
.log-row:nth-child(even) { background:#f8fafc; }
.log-time { color:#94a3b8; flex-shrink:0; }
.log-status { font-size:11px; padding:1px 5px; border-radius:4px; flex-shrink:0; }
.log-status-pending { background:#fef3c7; color:#d97706; }
.log-status-running { background:#dbeafe; color:#2563eb; }
.log-file { color:#0f172a; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; flex:1; }
.log-step { color:#64748b; flex-shrink:0; }
</style>
