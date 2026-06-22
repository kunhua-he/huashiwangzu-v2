<template>
  <div class="replay-viewer">
    <div v-if="loading" class="rv-status">加载中...</div>
    <div v-else-if="error" class="rv-status rv-error">{{ error }}</div>
    <div v-else-if="rounds.length === 0" class="rv-status rv-empty">暂无重放数据</div>
    <div v-else class="rv-timeline">
      <div
        v-for="(round, ri) in rounds"
        :key="ri"
        class="rv-round"
        :class="{ 'rv-round-expanded': expandedRounds.has(ri) }"
      >
        <div class="rv-round-header" @click="toggleRound(ri)">
          <span class="rv-round-num">#{{ ri + 1 }}</span>
          <span class="rv-round-preview">{{ round.user_input ? round.user_input.slice(0, 60) : '(压缩/系统事件)' }}</span>
          <span class="rv-round-toggle">{{ expandedRounds.has(ri) ? '▾' : '▸' }}</span>
        </div>
        <div v-if="expandedRounds.has(ri)" class="rv-round-body">
          <!-- 用户输入 -->
          <div v-if="round.user_input" class="rv-step">
            <span class="rv-step-label">用户输入</span>
            <div class="rv-step-content">{{ round.user_input }}</div>
          </div>

          <!-- 装配诊断 -->
          <div v-if="round.assembly_diag" class="rv-step rv-step-diag">
            <span class="rv-step-label">装配诊断</span>
            <div class="rv-diag-grid">
              <div class="rv-diag-item" v-if="round.assembly_diag.total_estimated">总 token: {{ round.assembly_diag.total_estimated }}</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.budget">预算: {{ round.assembly_diag.budget }}</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.system_tokens">系统: {{ round.assembly_diag.system_tokens }}</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.input_tokens">输入: {{ round.assembly_diag.input_tokens }}</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.recent_tokens">近期: {{ round.assembly_diag.recent_tokens }}</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.experience_injection">经验: {{ round.assembly_diag.experience_injection }}</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.dropped_recent_count != null">丢弃: {{ round.assembly_diag.dropped_recent_count }} 条</div>
              <div class="rv-diag-item rv-diag-warn" v-if="round.assembly_diag.budget_exceeded">⚠ 超出预算</div>
              <div class="rv-diag-item" v-if="round.assembly_diag.is_unlimited">无限制预算</div>
            </div>
          </div>

          <!-- 压缩 -->
          <div v-if="round.compaction" class="rv-step rv-step-compact">
            <span class="rv-step-label">压缩</span>
            <div class="rv-step-content">
              折叠 {{ round.compaction.folded_count }} 条 · 压缩比 {{ round.compaction.compression_ratio }}%
              <div class="rv-compact-summary">摘要：{{ round.compaction.summary_preview }}</div>
            </div>
          </div>

          <!-- 降级 -->
          <div v-if="round.degradation" class="rv-step rv-step-degrade">
            <span class="rv-step-label">降级</span>
            <div class="rv-step-content">
              {{ round.degradation.from_profile }} → {{ round.degradation.to_profile }}
              <div class="rv-degrade-reason">原因：{{ round.degradation.reason }}</div>
            </div>
          </div>

          <!-- 工具调用 -->
          <div v-if="round.tool_calls && round.tool_calls.length" class="rv-step">
            <span class="rv-step-label">工具调用 ({{ round.tool_calls.length }})</span>
            <div v-for="(tc, tci) in round.tool_calls" :key="tci" class="rv-tool-item">
              <span class="rv-tool-name">{{ tc.name || tc.id }}</span>
              <span class="rv-tool-args">{{ JSON.stringify(tc.arguments).slice(0, 120) }}</span>
            </div>
          </div>

          <!-- 工具结果 -->
          <div v-if="round.tool_results && round.tool_results.length" class="rv-step">
            <span class="rv-step-label">工具结果 ({{ round.tool_results.length }})</span>
            <div v-for="(tr, tri) in round.tool_results" :key="tri" class="rv-tool-item">
              <span class="rv-tool-name">{{ tr.name }}</span>
              <span class="rv-tool-args">{{ JSON.stringify(tr.result).slice(0, 120) }}</span>
            </div>
          </div>

          <!-- AI 回复 -->
          <div v-if="round.assistant_msg" class="rv-step">
            <span class="rv-step-label">AI 回复</span>
            <div class="rv-step-content rv-assistant">{{ round.assistant_msg.slice(0, 300) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface ReplayRound {
  user_input?: string
  assembly_diag?: Record<string, unknown>
  assistant_msg?: string
  tool_calls?: Array<{ id: string; name: string; arguments: Record<string, unknown> }>
  tool_results?: Array<{ tool_call_id: string; name: string; result: Record<string, unknown> }>
  compaction?: { folded_count: number; summary_preview: string; compression_ratio: number }
  degradation?: { from_profile: string; to_profile: string; reason: string }
}

defineProps<{
  rounds: ReplayRound[]
  loading: boolean
  error: string
}>()

const expandedRounds = ref(new Set<number>())

function toggleRound(ri: number) {
  if (expandedRounds.value.has(ri)) expandedRounds.value.delete(ri)
  else expandedRounds.value.add(ri)
}
</script>

<style scoped>
.replay-viewer { margin-top: 4px; }
.rv-status { padding: 20px; text-align: center; color: #909399; font-size: 13px; }
.rv-error { color: #f56c6c; }
.rv-empty { color: #909399; }

.rv-timeline { display: flex; flex-direction: column; gap: 6px; }

.rv-round {
  border: 1px solid #e2e6e9;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}
.rv-round-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  transition: background 0.12s;
}
.rv-round-header:hover { background: #f0f5f7; }
.rv-round-num {
  font-weight: 600;
  font-size: 12px;
  color: #2395bc;
  background: #e8f6fb;
  padding: 1px 8px;
  border-radius: 3px;
  white-space: nowrap;
}
.rv-round-preview { flex: 1; font-size: 13px; color: #5e5e5e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rv-round-toggle { font-size: 12px; color: #909399; }

.rv-round-body { padding: 0 14px 12px; border-top: 1px solid #f0f0f0; }

.rv-step { margin-top: 10px; }
.rv-step-label {
  font-size: 11px;
  font-weight: 600;
  color: #2395bc;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block;
  margin-bottom: 4px;
}
.rv-step-content { font-size: 13px; color: #1a1a1a; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }

.rv-diag-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.rv-diag-item {
  font-size: 12px;
  background: #f5f7fa;
  border: 1px solid #e8e8e8;
  border-radius: 3px;
  padding: 3px 8px;
  color: #5e5e5e;
}
.rv-diag-warn { background: #fff5e6; border-color: #e6a23c; color: #e6a23c; }

.rv-tool-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 8px;
  background: #fafbfc;
  border-radius: 3px;
  margin-top: 4px;
  font-size: 12px;
}
.rv-tool-name { font-weight: 600; color: #2395bc; white-space: nowrap; font-family: monospace; }
.rv-tool-args { color: #5e5e5e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; font-size: 11px; }

.rv-assistant { color: #1a1a1a; }

.rv-compact-summary { margin-top: 4px; font-size: 12px; color: #909399; font-style: italic; }
.rv-degrade-reason { margin-top: 4px; font-size: 12px; color: #e6a23c; }

.rv-step-compact .rv-step-label { color: #e6a23c; }
.rv-step-degrade .rv-step-label { color: #f56c6c; }
.rv-step-diag .rv-step-label { color: #52b95b; }
</style>
