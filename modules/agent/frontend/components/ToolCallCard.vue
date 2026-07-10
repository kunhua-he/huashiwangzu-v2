<template>
  <div class="tool-row">
	    <button class="tool-toggle" @click="isOpen = !isOpen">
	      <span class="tool-dot" :class="toolState"></span>
	      <template v-if="message.eventType === 'tool_call'">
	        <span>正在调用</span>
	        <span class="tool-name" :title="message.toolName">{{ displayToolName }}</span>
        <span class="tool-calling-dots">
          <span class="cdot"></span><span class="cdot"></span><span class="cdot"></span>
        </span>
	      </template>
		      <template v-else>
		        <span>{{ statusText }}</span>
		        <span class="tool-name" :title="message.toolName">{{ displayToolName }}</span>
		        <span v-if="durationText" class="tool-duration">{{ durationText }}</span>
	        <svg class="tool-chevron" :class="{ rotated: isOpen }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
          <path d="M4 3l4 3-4 3"/>
        </svg>
      </template>
	    </button>
    <div v-show="isOpen && message.eventType === 'tool_result'" class="tool-body">
      <div v-if="errorText" class="tool-error">{{ errorText }}</div>
      <div class="tool-summary" :class="`tool-summary--${resultSummary.status}`">
        <div class="tool-summary-main">
          <span class="tool-summary-mark" aria-hidden="true"></span>
          <div class="tool-summary-copy">
            <div class="tool-summary-title">{{ resultSummary.title }}</div>
            <div v-if="resultSummary.description" class="tool-summary-desc">{{ resultSummary.description }}</div>
          </div>
        </div>
        <div v-if="referenceSummary" class="tool-summary-ref">{{ referenceSummary }}</div>
      </div>
      <div v-if="resultSummary.skills?.length" class="tool-table tool-table--skills">
        <div class="tool-table-head">
          <span>名称</span>
          <span>工具标识</span>
          <span>说明</span>
        </div>
        <div v-for="skill in resultSummary.skills" :key="skill.name" class="tool-table-row">
          <span class="tool-cell-strong">{{ skill.displayName }}</span>
          <span class="tool-cell-code" :title="skill.name">{{ skill.name }}</span>
          <span>{{ skill.brief || '-' }}</span>
        </div>
      </div>
      <div v-if="resultSummary.parameters?.length" class="tool-table tool-table--params">
        <div class="tool-table-head">
          <span>参数</span>
          <span>类型</span>
          <span>必填</span>
          <span>说明</span>
        </div>
        <div v-for="param in resultSummary.parameters" :key="param.name" class="tool-table-row">
          <span class="tool-cell-code" :title="param.name">{{ param.name }}</span>
          <span>{{ param.type }}</span>
          <span>{{ param.required ? '是' : '否' }}</span>
          <span>{{ param.description || '-' }}</span>
        </div>
      </div>
      <div v-else-if="resultSummary.fields?.length && resultSummary.kind !== 'file-open'" class="tool-kv-list">
        <div v-for="field in resultSummary.fields" :key="field.label" class="tool-kv-item">
          <span>{{ field.label }}</span>
          <strong :title="field.value">{{ field.value }}</strong>
        </div>
      </div>
      <details v-if="showReferenceActions" class="tool-reference-details">
        <summary>查看引用操作</summary>
        <EvidenceReferenceList :references="referenceList" dense class="tool-refs" />
      </details>
      <template v-if="hasImage(message.toolResult)">
        <GeneratedImageStrip :images="extractImages(message.toolResult)" />
      </template>
      <details v-if="showRawResult" class="tool-raw-details">
        <summary>查看原始 JSON</summary>
        <pre>{{ formatResult(message.toolResult) }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import EvidenceReferenceList from './EvidenceReferenceList.vue'
import GeneratedImageStrip from './GeneratedImageStrip.vue'
import {
  compactReferenceText,
  displayToolName as formatToolName,
  isFailureResult,
  isRecord,
  resultPayload,
  summarizeToolResult,
} from './toolDisplay'
import {
  collectEvidenceReferences,
  type EvidenceReference,
} from './evidenceReferences'

const props = defineProps<{
  message: {
	    eventType?: string
	    toolName?: string
	    toolResult?: unknown
	    toolStatus?: string
	    toolError?: string
	    toolReferences?: EvidenceReference[]
	    durationMs?: number
	  }
		}>()

const isOpen = ref(hasImage(props.message.toolResult))

const displayToolName = computed(() => {
  const name = props.message.toolName || ''
  return formatToolName(name)
})

const durationText = computed(() => {
  if (props.message.eventType !== 'tool_result') return ''
  const ms = props.message.durationMs
  if (!ms) return ''
  if (ms < 1000) return `· ${ms}ms`
  const sec = ms / 1000
  if (sec < 60) return `· ${Number(sec.toFixed(sec < 10 ? 1 : 0))}秒`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `· ${m}分${s}秒`
})

interface ImageEntry {
  type?: string
  file_id: number
  name?: string
  [key: string]: unknown
}

function hasImage(r: unknown): boolean {
  const payload = resultPayload(r)
  if (!payload || typeof payload !== 'object') return false
  const obj = payload as Record<string, unknown>
  if (Array.isArray(obj.images) && obj.images.some(isImageEntry)) return true
  if (isImageEntry(obj)) return true
  return false
}

function extractImages(r: unknown): ImageEntry[] {
  const payload = resultPayload(r)
  if (!payload || typeof payload !== 'object') return []
  const obj = payload as Record<string, unknown>
  if (Array.isArray(obj.images)) {
    return obj.images.filter(isImageEntry)
  }
  if (isImageEntry(obj)) {
    return [obj]
  }
  return []
}

function isImageEntry(value: unknown): value is ImageEntry {
  if (!isRecord(value)) return false
  if (value.type !== undefined && value.type !== 'image') return false
  return typeof value.file_id === 'number'
}

const toolState = computed(() => {
  if (props.message.eventType === 'tool_call') return 'calling'
  return isFailureResult(props.message.toolResult, props.message.toolStatus) ? 'failed' : 'done'
})

watch(
  () => props.message.toolResult,
  result => {
    if (hasImage(result)) isOpen.value = true
  },
  { immediate: true },
)

const statusText = computed(() => {
  if (props.message.eventType === 'tool_call') return '正在调用'
  return toolState.value === 'failed' ? '工具失败' : '工具完成'
})

const resultSummary = computed(() => summarizeToolResult(props.message.toolName || '', props.message.toolResult, props.message.toolStatus))
const referenceSummary = computed(() => compactReferenceText(referenceList.value))
const showReferenceActions = computed(() => referenceList.value.length > 0 && resultSummary.value.kind !== 'file-open')

const showRawResult = computed(() => {
  if (resultSummary.value.kind === 'empty') return false
  if (resultSummary.value.kind === 'file-open') return false
  if (hasImage(props.message.toolResult)) return false
  return true
})

const errorText = computed(() => {
  if (toolState.value !== 'failed') return ''
  if (props.message.toolError) return props.message.toolError
  const result = props.message.toolResult
  if (!isRecord(result)) return ''
  const inner = resultPayload(result)
  const message = result.error || result.message || (isRecord(inner) ? (inner.error || inner.message) : '')
  return typeof message === 'string' ? message : ''
})

const referenceList = computed<EvidenceReference[]>(() => {
  if (props.message.toolReferences?.length) return props.message.toolReferences
  return collectEvidenceReferences(props.message.toolResult, {
    sourceTool: props.message.toolName,
    status: props.message.toolStatus,
  })
})

function formatResult(r: unknown): string {
  if (typeof r === 'string') return r
  try { return JSON.stringify(r, null, 2) } catch { return String(r) }
}

</script>

<style scoped>
	.tool-row {
	  flex-shrink: 0;
	  align-self: flex-start;
	  max-width: 95%;
	  margin-bottom: var(--ag-space-sm);
	  animation: msgSlideUp 0.25s ease-out;
	}
	@keyframes msgSlideUp {
	  from { opacity: 0; transform: translateY(10px); }
	  to { opacity: 1; transform: translateY(0); }
	}

	.tool-toggle {
	  display: flex;
	  align-items: center;
	  gap: 5px;
	  white-space: nowrap;
	  border: none;
  background: none;
  cursor: pointer;
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-tertiary);
  padding: 2px 0;
  transition: color var(--ag-transition-fast);
}
.tool-toggle:hover { color: var(--ag-text-secondary); }

.tool-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--ag-radius-full);
  flex-shrink: 0;
  background: var(--ag-text-disabled);
}
.tool-dot.calling {
  background: #1677FF;
  animation: toolPulse 1.6s ease-out infinite;
}
.tool-dot.done {
  background: var(--ag-success);
}
.tool-dot.failed {
  background: var(--ag-error);
}
@keyframes toolPulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.tool-name {
  color: var(--ag-text-primary);
  font-family: var(--ag-font-mono);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-duration { font-size: 11px; color: var(--ag-text-disabled); flex-shrink: 0; }

.tool-calling-dots { display: inline-flex; gap: 2px; align-items: center; }
.tool-calling-dots .cdot {
  width: 3px; height: 3px; border-radius: var(--ag-radius-full);
  background: #1677FF;
  animation: toolDot 1.2s ease-in-out infinite;
}
.tool-calling-dots .cdot:nth-child(2) { animation-delay: 0.2s; }
.tool-calling-dots .cdot:nth-child(3) { animation-delay: 0.4s; }
@keyframes toolDot { 0%, 100% { opacity: 0.3; transform: scale(1); } 50% { opacity: 1; transform: scale(1.3); } }

.tool-chevron {
  transition: transform var(--ag-transition-base);
  flex-shrink: 0;
}
.tool-chevron.rotated { transform: rotate(90deg); }

.tool-body {
  display: grid;
  gap: var(--ag-space-sm);
  margin-top: var(--ag-space-xs);
  padding: var(--ag-space-sm) var(--ag-space-md);
  background: var(--ag-bg-page);
  border-radius: var(--ag-radius-md);
}
.tool-error {
  color: var(--ag-error);
  font-size: var(--ag-font-size-sm);
  line-height: var(--ag-line-height-base);
  word-break: break-word;
}
.tool-summary {
  display: grid;
  gap: 4px;
  padding: var(--ag-space-sm);
  border: 1px solid var(--ag-border-light);
  border-radius: var(--ag-radius-md);
  background: var(--ag-bg-base);
}
.tool-summary--failed {
  border-color: rgba(245, 108, 108, 0.32);
  background: #fff7f7;
}
.tool-summary-main {
  display: flex;
  gap: var(--ag-space-sm);
  align-items: flex-start;
  min-width: 0;
}
.tool-summary-mark {
  width: 6px;
  height: 6px;
  margin-top: 7px;
  border-radius: var(--ag-radius-full);
  background: var(--ag-success);
  flex-shrink: 0;
}
.tool-summary--failed .tool-summary-mark { background: var(--ag-error); }
.tool-summary-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.tool-summary-title {
  color: var(--ag-text-primary);
  font-size: var(--ag-font-size-sm);
  font-weight: 600;
  line-height: var(--ag-line-height-base);
}
.tool-summary-desc,
.tool-summary-ref {
  color: var(--ag-text-secondary);
  font-size: var(--ag-font-size-sm);
  line-height: var(--ag-line-height-base);
  word-break: break-word;
}
.tool-summary-ref {
  padding-left: 14px;
  color: var(--ag-text-tertiary);
  font-size: var(--ag-font-size-xs);
}
.tool-table {
  display: grid;
  border: 1px solid var(--ag-border-light);
  border-radius: var(--ag-radius-md);
  overflow: hidden;
  background: var(--ag-bg-base);
}
.tool-table-head,
.tool-table-row {
  display: grid;
  gap: var(--ag-space-sm);
  align-items: center;
  padding: 6px var(--ag-space-sm);
  min-width: 0;
  font-size: var(--ag-font-size-xs);
}
.tool-table-head {
  background: var(--ag-bg-sidebar);
  color: var(--ag-text-tertiary);
  font-weight: 600;
}
.tool-table-row {
  border-top: 1px solid var(--ag-border-light);
  color: var(--ag-text-secondary);
}
.tool-table--skills .tool-table-head,
.tool-table--skills .tool-table-row {
  grid-template-columns: minmax(88px, 0.8fr) minmax(120px, 1fr) minmax(120px, 1.4fr);
}
.tool-table--params .tool-table-head,
.tool-table--params .tool-table-row {
  grid-template-columns: minmax(82px, 0.9fr) 64px 42px minmax(140px, 1.6fr);
}
.tool-table-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-cell-strong {
  color: var(--ag-text-primary);
  font-weight: 600;
}
.tool-cell-code {
  font-family: var(--ag-font-mono);
  color: var(--ag-text-primary);
}
.tool-kv-list {
  display: grid;
  gap: 4px;
  max-width: 520px;
}
.tool-kv-item {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: var(--ag-space-sm);
  align-items: center;
  min-height: 22px;
  color: var(--ag-text-secondary);
  font-size: var(--ag-font-size-xs);
}
.tool-kv-item strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ag-text-primary);
  font-family: var(--ag-font-mono);
  font-weight: 500;
}
.tool-reference-details,
.tool-raw-details {
  font-size: var(--ag-font-size-xs);
  color: var(--ag-text-tertiary);
}
.tool-reference-details summary,
.tool-raw-details summary {
  width: fit-content;
  cursor: pointer;
  user-select: none;
}
.tool-reference-details summary:hover,
.tool-raw-details summary:hover { color: var(--ag-text-secondary); }
.tool-refs { margin-top: var(--ag-space-xs); }
.tool-body pre {
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow: auto;
  font-size: var(--ag-font-size-sm);
  font-family: var(--ag-font-mono);
  color: var(--ag-text-secondary);
  margin: 0;
}

</style>
