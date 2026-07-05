<template>
  <div class="image-gen-app">
    <div class="toolbar">
      <div class="toolbar-row">
        <label class="field-label">模板</label>
        <select v-model="templateKey" class="tpl-select" @change="onTemplateChange">
          <option v-for="t in templates" :key="t.key" :value="t.key">
            {{ t.label }}
          </option>
        </select>
        <span v-if="templateAvailable === false" class="badge badge-warn">无凭据</span>
        <span v-else-if="templateAvailable === true" class="badge badge-ok">就绪</span>
        <span v-if="selectedTemplate?.fallback" class="badge badge-info">降级到 {{ selectedTemplate.fallback }}</span>
      </div>
      <div v-if="selectedTemplate" class="template-meta">
        Provider: {{ selectedTemplate.provider }} · Prompt: {{ selectedTemplate.prompt_language }}
      </div>
      <div class="toolbar-row">
        <label class="field-label">提示词</label>
        <textarea
          v-model="prompt"
          class="prompt-input"
          placeholder="描述想要生成的图片内容，如：护肤品精华液电商主图，磨砂玻璃瓶，清新蓝底"
          rows="3"
        />
      </div>
      <div class="toolbar-row">
        <label class="field-label">尺寸</label>
        <div class="size-group">
          <button
            v-for="s in sizeOptions"
            :key="s.key"
            :class="['size-btn', { active: aspectRatio === s.key }]"
            @click="aspectRatio = s.key"
          >
            {{ s.label }}
          </button>
        </div>
      </div>
      <div class="toolbar-row">
        <label class="field-label">数量</label>
        <div class="num-control">
          <button class="num-btn" :disabled="count <= 1" @click="count = Math.max(1, count - 1)">−</button>
          <span class="num-value">{{ count }}</span>
          <button class="num-btn" :disabled="count >= 4" @click="count = Math.min(4, count + 1)">+</button>
        </div>
        <button class="gen-btn" :disabled="!canSubmit" @click="doGenerate">
          {{ generating ? '生成中…' : '生成图片' }}
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

    <div v-if="generating" class="progress-hint">正在生成图片，请稍候…</div>

    <div v-if="results.length" class="results-grid">
      <div v-for="img in results" :key="img.file_id" class="result-card">
        <img :src="imageUrls[img.file_id] || ''" :alt="img.name" class="result-img" />
        <div class="result-meta">
          <span v-if="img.placeholder" class="badge badge-warn">占位图</span>
          <span v-else class="badge badge-ok">真实生成</span>
          <span class="file-size">{{ (img.size / 1024).toFixed(1) }} KB</span>
        </div>
        <div v-if="img.explanation" class="result-note">{{ img.explanation }}</div>
      </div>
    </div>

    <div v-if="lastResponse" class="status-bar">
      状态: {{ statusLabel(lastResponse.status) }} · Provider: {{ lastResponse.provider }}
      <span v-if="lastResponse.degraded_reason"> · {{ lastResponse.degraded_reason }}</span>
    </div>

    <div v-if="costInfo" class="cost-bar">
      积分消耗: {{ costInfo.points_cost ?? '—' }} | 余额: {{ costInfo.balance ?? '—' }}
    </div>

    <section class="history-section">
      <div class="section-head">
        <h2>生成历史</h2>
        <button class="refresh-btn" :disabled="loadingHistory" @click="loadHistory">
          {{ loadingHistory ? '刷新中…' : '刷新' }}
        </button>
      </div>
      <div v-if="!history.length" class="empty-state">暂无生成记录</div>
      <div v-else class="history-list">
        <article v-for="item in history" :key="item.id" class="history-item">
          <img
            v-if="firstFileId(item) && historyUrls[firstFileId(item)]"
            :src="historyUrls[firstFileId(item)]"
            class="history-thumb"
            alt="history preview"
          />
          <div v-else class="history-thumb history-thumb-empty">无预览</div>
          <div class="history-body">
            <div class="history-topline">
              <span :class="['badge', statusBadgeClass(item.status)]">{{ statusLabel(item.status) }}</span>
              <span>{{ item.template }}</span>
              <span>{{ item.provider || 'unknown' }}</span>
            </div>
            <p class="history-prompt">{{ item.prompt }}</p>
            <p v-if="item.error_msg || item.degraded_reason" class="history-error">
              {{ item.error_msg || item.degraded_reason }}
            </p>
            <div class="history-meta">
              <span>图片: {{ item.image_count }}</span>
              <span>文件: {{ item.file_ids.join(', ') || '—' }}</span>
              <span>积分: {{ item.points_cost ?? '—' }}</span>
              <span>{{ item.created_at || '' }}</span>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { apiGet, apiPost, authHeaders, getApiUrl } from '../runtime'

interface TemplateItem {
  key: string
  label: string
  provider: string
  configured: boolean
  available: boolean
  can_generate: boolean
  fallback: string | null
  prompt_language: string
  cost_tracking: boolean
}

interface ImageResult {
  type: string
  file_id: number
  name: string
  size: number
  placeholder: boolean
  explanation?: string
}

interface GenerateResponse {
  task?: {
    request_id: string
    record_id: number | null
  }
  images: ImageResult[]
  placeholder: boolean
  degraded: boolean
  status: string
  template: string
  provider: string
  requested_provider?: string
  degraded_reason?: string | null
  points_cost?: number
  balance?: number
  error?: string
  detail?: string
}

interface HistoryRecord {
  id: number
  request_id?: string | null
  template: string
  provider?: string | null
  prompt: string
  image_count: number
  file_ids: number[]
  points_cost?: number | null
  balance_after?: number | null
  status: string
  error_msg?: string | null
  degraded_reason?: string | null
  created_at?: string | null
}

const templates = ref<TemplateItem[]>([])
const templateKey = ref('')
const templateAvailable = ref<boolean | null>(null)
const prompt = ref('')
const aspectRatio = ref('square')
const count = ref(1)
const generating = ref(false)
const results = ref<ImageResult[]>([])
const imageUrls = ref<Record<number, string>>({})
const historyUrls = ref<Record<number, string>>({})
const errorMsg = ref('')
const costInfo = ref<{ points_cost?: number; balance?: number } | null>(null)
const lastResponse = ref<GenerateResponse | null>(null)
const history = ref<HistoryRecord[]>([])
const loadingHistory = ref(false)

const sizeOptions = [
  { key: 'square', label: '1:1' },
  { key: 'portrait', label: '3:4' },
  { key: 'landscape', label: '16:9' },
]

const selectedTemplate = computed(() => templates.value.find(x => x.key === templateKey.value) ?? null)
const canSubmit = computed(() => Boolean(prompt.value.trim() && templateKey.value && !generating.value))

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

async function downloadImageBlob(fileId: number): Promise<Blob> {
  const resp = await fetch(getApiUrl(`/files/download/${fileId}`), { headers: authHeaders() })
  if (!resp.ok) throw new Error(`Download failed: ${resp.status}`)
  return resp.blob()
}

function revokeUrlMap(urls: Record<number, string>) {
  for (const url of Object.values(urls)) {
    URL.revokeObjectURL(url)
  }
}

function firstFileId(item: HistoryRecord): number {
  return item.file_ids[0] ?? 0
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    success: '成功',
    degraded: '降级',
    placeholder: '占位',
    partial: '部分成功',
    failed: '失败',
  }
  return labels[status] ?? status
}

function statusBadgeClass(status: string): string {
  if (status === 'success') return 'badge-ok'
  if (status === 'failed') return 'badge-error'
  return 'badge-warn'
}

async function loadTemplates() {
  try {
    const data = await apiGet<{ templates: TemplateItem[] }>('/image-gen/templates')
    templates.value = data.templates
    if (data.templates.length && !data.templates.some(item => item.key === templateKey.value)) {
      templateKey.value = data.templates[0].key
    }
    updateAvailable()
  } catch (e: unknown) {
    console.warn('Failed to load templates:', e)
  }
}

function updateAvailable() {
  const t = selectedTemplate.value
  templateAvailable.value = t ? t.available : null
}

function onTemplateChange() {
  updateAvailable()
}

async function doGenerate() {
  if (!prompt.value.trim() || generating.value) return
  generating.value = true
  errorMsg.value = ''
  results.value = []
  lastResponse.value = null
  costInfo.value = null
  revokeUrlMap(imageUrls.value)
  imageUrls.value = {}

  try {
    const data = await apiPost<GenerateResponse>('/image-gen/generate', {
      prompt: prompt.value,
      aspect_ratio: aspectRatio.value,
      count: count.value,
      template: templateKey.value,
      steps: 30,
    })
    if (data.error) {
      errorMsg.value = data.error
    }
    if (data.degraded_reason) {
      errorMsg.value = data.degraded_reason
    }
    lastResponse.value = data
    results.value = data.images || []
    for (const img of results.value) {
      try {
        const blob = await downloadImageBlob(img.file_id)
        imageUrls.value[img.file_id] = URL.createObjectURL(blob)
      } catch (e) {
        console.warn('Failed to load image', img.file_id, e)
      }
    }
    if (data.points_cost != null || data.balance != null) {
      costInfo.value = { points_cost: data.points_cost, balance: data.balance }
    }
    await loadHistory()
  } catch (e: unknown) {
    errorMsg.value = errorMessage(e, '生成失败')
  } finally {
    generating.value = false
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const data = await apiGet<{ records: HistoryRecord[] }>('/image-gen/history?limit=20')
    history.value = data.records
    revokeUrlMap(historyUrls.value)
    historyUrls.value = {}
    for (const item of history.value) {
      const fileId = firstFileId(item)
      if (!fileId) continue
      try {
        const blob = await downloadImageBlob(fileId)
        historyUrls.value[fileId] = URL.createObjectURL(blob)
      } catch (e) {
        console.warn('Failed to load history image', fileId, e)
      }
    }
  } catch (e: unknown) {
    console.warn('Failed to load history:', e)
  } finally {
    loadingHistory.value = false
  }
}

onMounted(() => {
  loadTemplates()
  loadHistory()
})

onBeforeUnmount(() => {
  revokeUrlMap(imageUrls.value)
  revokeUrlMap(historyUrls.value)
})
</script>

<style scoped>
.image-gen-app {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  background: var(--bg-page, #f5f6f8);
  font-family: "苹方","微软雅黑","宋体",sans-serif;
  font-size: 14px;
  color: #333;
  overflow-y: auto;
}

.toolbar {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 12px;
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.toolbar-row:last-child {
  margin-bottom: 0;
}

.template-meta {
  margin: -4px 0 10px 58px;
  color: #667085;
  font-size: 12px;
}

.field-label {
  min-width: 48px;
  font-weight: 500;
  color: #555;
  font-size: 13px;
}

.tpl-select {
  padding: 6px 10px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  min-width: 220px;
}

.prompt-input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 13px;
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
}

.size-group {
  display: flex;
  gap: 4px;
}

.size-btn {
  padding: 5px 14px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: #555;
}
.size-btn.active {
  background: #2395bc;
  color: #fff;
  border-color: #2395bc;
}

.num-control {
  display: flex;
  align-items: center;
  gap: 6px;
}

.num-btn {
  width: 28px;
  height: 28px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  background: #fff;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #555;
}
.num-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.num-value {
  min-width: 20px;
  text-align: center;
  font-weight: 600;
}

.gen-btn {
  margin-left: auto;
  padding: 7px 22px;
  background: #2395bc;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
}
.gen-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.badge-ok {
  background: #e6f7e6;
  color: #389e0d;
}
.badge-warn {
  background: #fff7e6;
  color: #d48806;
}
.badge-info {
  background: #e6f4ff;
  color: #0958d9;
}
.badge-error {
  background: #fff1f0;
  color: #cf1322;
}

.error-bar {
  background: #fff1f0;
  color: #cf1322;
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 13px;
}

.progress-hint {
  text-align: center;
  padding: 24px;
  color: #888;
  font-size: 14px;
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.result-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.result-img {
  width: 100%;
  display: block;
  aspect-ratio: 1;
  object-fit: cover;
}

.result-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  font-size: 12px;
  color: #888;
}

.result-note {
  padding: 0 10px 8px;
  color: #d48806;
  font-size: 12px;
}

.file-size {
  color: #aaa;
}

.status-bar {
  background: #fffbe6;
  color: #874d00;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 12px;
}

.cost-bar {
  background: #f0f5ff;
  color: #1d39c4;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 13px;
}

.history-section {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  margin-top: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.section-head h2 {
  margin: 0;
  font-size: 15px;
  color: #333;
}

.refresh-btn {
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  background: #fff;
  color: #555;
  padding: 5px 12px;
  cursor: pointer;
}
.refresh-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.empty-state {
  padding: 20px;
  text-align: center;
  color: #98a2b3;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 12px;
  border: 1px solid #eaecf0;
  border-radius: 8px;
  padding: 10px;
}

.history-thumb {
  width: 92px;
  height: 92px;
  border-radius: 6px;
  object-fit: cover;
  background: #f2f4f7;
}

.history-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #98a2b3;
  font-size: 12px;
}

.history-body {
  min-width: 0;
}

.history-topline,
.history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: #667085;
  font-size: 12px;
}

.history-prompt {
  margin: 8px 0 6px;
  color: #333;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.history-error {
  margin: 0 0 6px;
  color: #cf1322;
  font-size: 12px;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .toolbar-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .field-label {
    width: 100%;
  }
  .template-meta {
    margin-left: 0;
  }
  .history-item {
    grid-template-columns: 72px 1fr;
  }
  .history-thumb {
    width: 72px;
    height: 72px;
  }
}
</style>
