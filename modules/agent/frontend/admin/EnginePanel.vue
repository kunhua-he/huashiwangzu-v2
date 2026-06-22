<template>
  <div class="engine-panel">
    <header class="ep-header">
      <h2 class="ep-title">🔧 引擎调优面板</h2>
      <span class="ep-subtitle">只读观测 · 仅管理员可见</span>
    </header>

    <div v-if="loading" class="ep-loading">加载中...</div>
    <div v-else-if="error" class="ep-error">{{ error }}</div>
    <template v-else>
      <!-- 记忆 / 经验 概览 -->
      <section class="ep-section">
        <h3 class="ep-section-title">
          记忆 &amp; 经验
          <span class="ep-manual-ref">调优手册第2/5/6条</span>
        </h3>
        <div class="ep-card-grid">
          <div class="ep-card">
            <div class="ep-card-value">{{ data.memory?.total_count ?? '-' }}</div>
            <div class="ep-card-label">记忆总数</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.memory?.with_embedding ?? '-' }}</div>
            <div class="ep-card-label">已向量化</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.memory?.avg_confidence ?? '-' }}</div>
            <div class="ep-card-label">平均置信度</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.memory?.avg_recency_score ?? '-' }}</div>
            <div class="ep-card-label">平均时效分</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.memory?.link_count ?? '-' }}</div>
            <div class="ep-card-label">记忆链边数</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.memory?.owner_count ?? '-' }}</div>
            <div class="ep-card-label">记忆所属用户</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.experience?.total_count ?? '-' }}</div>
            <div class="ep-card-label">经验总数</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.experience?.active_count ?? '-' }} / {{ data.experience?.inactive_count ?? '-' }}</div>
            <div class="ep-card-label">启用 / 停用</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.experience?.avg_success_weight ?? '-' }}</div>
            <div class="ep-card-label">平均成功权重</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.experience?.total_fail_count ?? '-' }}</div>
            <div class="ep-card-label">累计失败次数</div>
          </div>
        </div>
        <p class="ep-hint">异常：记忆置信度过低 → 调优手册第2条提阈值；经验失败偏高 → 第6条调净值公式</p>
      </section>

      <!-- 预算 / 压缩 概览 -->
      <section class="ep-section">
        <h3 class="ep-section-title">
          预算 &amp; 压缩
          <span class="ep-manual-ref">调优手册第1/7条</span>
        </h3>
        <div class="ep-card-grid">
          <div class="ep-card">
            <div class="ep-card-value">{{ data.conversations?.conversation_count ?? '-' }}</div>
            <div class="ep-card-label">对话数（有事件）</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.conversations?.total_events ?? '-' }}</div>
            <div class="ep-card-label">事件总数</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.conversations?.user_msg_count ?? '-' }}</div>
            <div class="ep-card-label">用户消息</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.conversations?.tool_call_count ?? '-' }}</div>
            <div class="ep-card-label">工具调用</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.conversations?.avg_events_per_conversation ?? '-' }}</div>
            <div class="ep-card-label">平均每对话事件</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.compression?.compaction_count ?? '-' }}</div>
            <div class="ep-card-label">压缩次数</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.compression?.total_folded_events ?? '-' }}</div>
            <div class="ep-card-label">累计折叠事件</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.compression?.hard_truncate_count ?? '-' }}</div>
            <div class="ep-card-label">硬截断次数</div>
          </div>
        </div>
        <p class="ep-hint">异常：压缩频繁 / 硬截断多 → 调优手册第1条调大 budget 或第7条调保留头尾轮数</p>
      </section>

      <!-- 成本 / 用量 概览 -->
      <section class="ep-section">
        <h3 class="ep-section-title">
          模型成本 &amp; 用量
          <span class="ep-manual-ref">今日</span>
        </h3>
        <div v-if="costError" class="ep-error">{{ costError }}</div>
        <div v-else class="ep-card-grid">
          <div class="ep-card" style="border-left: 3px solid #f0b240;">
            <div class="ep-card-value">{{ costData.today_total ?? '-' }}</div>
            <div class="ep-card-label">今日总花费 (¥)</div>
          </div>
        </div>
        <div v-if="costData.by_model?.length" style="margin-top:12px;">
          <div style="font-size:12px;font-weight:600;margin-bottom:6px;">按模型：</div>
          <table style="width:100%;font-size:11px;border-collapse:collapse;">
            <thead><tr style="background:#e8f6fb;"><th style="padding:4px 8px;text-align:left;">模型</th><th style="padding:4px 8px;text-align:right;">调用</th><th style="padding:4px 8px;text-align:right;">输入tok</th><th style="padding:4px 8px;text-align:right;">输出tok</th><th style="padding:4px 8px;text-align:right;">花费 ¥</th></tr></thead>
            <tbody>
              <tr v-for="m in costData.by_model" :key="m.model_key" style="border-bottom:1px solid #eee;">
                <td style="padding:3px 8px;">{{ m.model_key }}</td>
                <td style="padding:3px 8px;text-align:right;">{{ m.calls }}</td>
                <td style="padding:3px 8px;text-align:right;">{{ m.prompt_tokens }}</td>
                <td style="padding:3px 8px;text-align:right;">{{ m.completion_tokens }}</td>
                <td style="padding:3px 8px;text-align:right;">{{ m.cost }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="costData.by_module?.length" style="margin-top:8px;">
          <div style="font-size:12px;font-weight:600;margin-bottom:6px;">按模块：</div>
          <table style="width:100%;font-size:11px;border-collapse:collapse;">
            <thead><tr style="background:#e8f6fb;"><th style="padding:4px 8px;text-align:left;">模块</th><th style="padding:4px 8px;text-align:right;">调用</th><th style="padding:4px 8px;text-align:right;">花费 ¥</th></tr></thead>
            <tbody>
              <tr v-for="m in costData.by_module" :key="m.module" style="border-bottom:1px solid #eee;">
                <td style="padding:3px 8px;">{{ m.module }}</td>
                <td style="padding:3px 8px;text-align:right;">{{ m.calls }}</td>
                <td style="padding:3px 8px;text-align:right;">{{ m.cost }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="costData.last_7_days?.length" class="ep-hint" style="margin-top:8px;">
          近7天趋势：{{ costData.last_7_days.map(d => d.date + ' ¥' + d.cost).join(' → ') }}
        </p>
      </section>

      <!-- 降级 / 粘滞 概览 -->
      <section class="ep-section">
        <h3 class="ep-section-title">
          降级 &amp; 粘滞
          <span class="ep-manual-ref">调优手册第8/9条</span>
        </h3>
        <div class="ep-card-grid">
          <div class="ep-card">
            <div class="ep-card-value">{{ data.degradation?.degradation_count ?? '-' }}</div>
            <div class="ep-card-label">降级触发次数</div>
          </div>
          <div class="ep-card">
            <div class="ep-card-value">{{ data.sticky?.stuck_detection_count ?? '-' }}</div>
            <div class="ep-card-label">粘滞打断次数</div>
          </div>
        </div>
        <p class="ep-hint">异常：降级频繁 → 调优手册第8条换更稳的主档或调整链顺序；粘滞误杀 → 第9条放宽阈值</p>
      </section>

      <!-- 对话重放查看器 -->
      <section class="ep-section ep-section-replay">
        <h3 class="ep-section-title">会话重放查看器</h3>
        <div class="ep-replay-input-row">
          <input
            v-model="replayConvId"
            type="number"
            placeholder="输入 conversation_id"
            class="ep-input"
            @keyup.enter="loadReplay"
          />
          <button class="ep-btn" @click="loadReplay" :disabled="replayLoading">查看重放</button>
        </div>
        <ReplayViewer :rounds="replayData?.rounds ?? []" :loading="replayLoading" :error="replayError" />
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { apiGet } from '../../runtime'
import ReplayViewer from './ReplayViewer.vue'

interface OverviewMemory { total_count: number; with_embedding: number; avg_confidence: number; avg_recency_score: number; link_count: number; owner_count: number }
interface OverviewExperience { total_count: number; active_count: number; inactive_count: number; avg_success_weight: number; total_fail_count: number }
interface OverviewConversations { conversation_count: number; total_events: number; user_msg_count: number; tool_call_count: number; avg_events_per_conversation: number }
interface OverviewCompression { compaction_count: number; total_folded_events: number; hard_truncate_count: number }
interface OverviewDegradation { degradation_count: number }
interface OverviewSticky { stuck_detection_count: number }
interface CostModelItem { model_key: string; calls: number; prompt_tokens: number; completion_tokens: number; cost: number }
interface CostModuleItem { module: string; calls: number; cost: number }
interface Cost7DayItem { date: string; cost: number }
interface OverviewCost { today_total: number; by_model: CostModelItem[]; by_module: CostModuleItem[]; last_7_days: Cost7DayItem[] }
/** Runtime union: the cost endpoint may return either cost data or an error object */
type OverviewCostResult = OverviewCost | { error: string }
interface OverviewData {
  memory?: OverviewMemory
  experience?: OverviewExperience
  conversations?: OverviewConversations
  compression?: OverviewCompression
  degradation?: OverviewDegradation
  sticky?: OverviewSticky
  cost?: OverviewCostResult
}

interface ReplayRound {
  user_input?: string
  assembly_diag?: Record<string, unknown>
  assistant_msg?: string
  tool_calls?: Array<{ id: string; name: string; arguments: Record<string, unknown> }>
  tool_results?: Array<{ tool_call_id: string; name: string; result: Record<string, unknown> }>
  compaction?: { folded_count: number; summary_preview: string; compression_ratio: number }
  degradation?: { from_profile: string; to_profile: string; reason: string }
}

const loading = ref(true)
const error = ref('')
const data = ref<OverviewData>({})
const emptyCostData: OverviewCost = { today_total: 0, by_model: [], by_module: [], last_7_days: [] }
const costData = computed<OverviewCost>(() => {
  const cost = data.value.cost
  if (!cost || 'error' in cost) return emptyCostData
  return cost
})
const costError = computed(() => { const c = data.value.cost; return c && 'error' in c ? (c as { error: string }).error : '' })

const replayConvId = ref('')
const replayData = ref<{ rounds: ReplayRound[] } | null>(null)
const replayLoading = ref(false)
const replayError = ref('')

async function loadOverview() {
  loading.value = true; error.value = ''
  try {
    data.value = await apiGet<OverviewData>('/agent/admin/overview')
  } catch (e: unknown) {
    error.value = String((e as Error).message || e)
  } finally {
    loading.value = false
  }
}

async function loadReplay() {
  const id = parseInt(replayConvId.value)
  if (!id) return
  replayLoading.value = true; replayError.value = ''
  try {
    replayData.value = await apiGet<{ rounds: ReplayRound[] }>(`/agent/admin/replay/${id}`)
  } catch (e: unknown) {
    replayError.value = String((e as Error).message || e)
  } finally {
    replayLoading.value = false
  }
}

onMounted(loadOverview)
</script>

<style scoped>
.engine-panel {
  --ep-primary: #2395bc;
  --ep-primary-light: #e8f6fb;
  --ep-bg: #f7f9fa;
  --ep-card-bg: #ffffff;
  --ep-text: #1a1a1a;
  --ep-text-secondary: #5e5e5e;
  --ep-border: #e2e6e9;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  font-size: 13px;
  color: var(--ep-text);
  background: var(--ep-bg);
  height: 100%;
  overflow-y: auto;
  padding: 20px 24px;
}
.ep-header { margin-bottom: 20px; display: flex; align-items: baseline; gap: 12px; }
.ep-title { font-size: 18px; font-weight: 600; margin: 0; color: var(--ep-text); }
.ep-subtitle { font-size: 12px; color: var(--ep-text-secondary); }
.ep-loading, .ep-error { padding: 40px; text-align: center; color: var(--ep-text-secondary); }
.ep-error { color: #f56c6c; }

.ep-section { margin-bottom: 24px; }
.ep-section-title { font-size: 14px; font-weight: 600; margin: 0 0 12px; display: flex; align-items: center; gap: 8px; }
.ep-manual-ref { font-size: 11px; font-weight: 400; color: var(--ep-primary); background: var(--ep-primary-light); padding: 2px 8px; border-radius: 3px; }

.ep-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
.ep-card {
  background: var(--ep-card-bg);
  border: 1px solid var(--ep-border);
  border-radius: 6px;
  padding: 12px 14px;
  transition: box-shadow 0.15s;
}
.ep-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.ep-card-value { font-size: 20px; font-weight: 700; color: var(--ep-primary); line-height: 1.2; }
.ep-card-label { font-size: 11px; color: var(--ep-text-secondary); margin-top: 4px; }

.ep-hint { font-size: 11px; color: var(--ep-text-secondary); margin: 10px 0 0; padding: 6px 10px; background: #fffbe6; border-radius: 4px; border-left: 3px solid #e6a23c; }

/* Replay */
.ep-section-replay { border-top: 1px solid var(--ep-border); padding-top: 20px; }
.ep-replay-input-row { display: flex; gap: 8px; margin-bottom: 12px; }
.ep-input {
  flex: 1;
  max-width: 240px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--ep-border);
  border-radius: 4px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}
.ep-input:focus { border-color: var(--ep-primary); }
.ep-btn {
  height: 32px;
  padding: 0 16px;
  background: var(--ep-primary);
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.ep-btn:hover { background: #1a8aaa; }
.ep-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
