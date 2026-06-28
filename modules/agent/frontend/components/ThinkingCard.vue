<template>
  <div class="thinking-row">
    <button class="th-toggle" @click="isOpen = !isOpen">
      <span class="th-dot" :class="{ running: running }"></span>
      <span>思维过程</span>
      <span v-if="durationText" class="th-duration">{{ durationText }}</span>
      <svg class="th-chevron" :class="{ rotated: isOpen }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
        <path d="M4 3l4 3-4 3"/>
      </svg>
    </button>
    <div v-show="isOpen" class="th-body">
      <span v-if="running && !displayedContent" class="th-waiting">思考中…</span>
      <template v-else>{{ displayedContent }}<span v-if="running" class="th-cursor">|</span></template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'

const props = defineProps<{ content: string; running?: boolean; collapsed?: boolean; durationMs?: number }>()
const isOpen = ref(!props.collapsed)

let typeRaf: number | null = null
const displayedContent = ref('')
let targetContent = ''

function normalize(text: string): string {
  return text.replace(/[\n\r]+/g, '').replace(/[ \t]{2,}/g, ' ').trim()
}

function startTyping() {
  if (typeRaf) return
  const step = () => {
    const pos = displayedContent.value.length
    if (pos < targetContent.length) {
      displayedContent.value = targetContent.slice(0, pos + 1)
      typeRaf = requestAnimationFrame(step)
    } else {
      typeRaf = null
    }
  }
  typeRaf = requestAnimationFrame(step)
}

function stopTyping() {
  if (typeRaf) { cancelAnimationFrame(typeRaf); typeRaf = null }
}

watch(
  () => props.content,
  (newVal) => {
    const normalized = normalize(newVal || '')
    if (normalized.length <= (targetContent || '').length) {
      // 内容回缩（工具调用截断清洗）：直接跳到清洗后的内容
      stopTyping()
      targetContent = normalized
      displayedContent.value = targetContent
      return
    }
    targetContent = normalized
    if (!props.running) {
      stopTyping()
      displayedContent.value = targetContent
      return
    }
    // 流式追加
    startTyping()
  },
  { immediate: true }
)

watch(
  () => props.running,
  (r) => {
    if (!r) {
      stopTyping()
      displayedContent.value = targetContent || normalize(props.content || '')
    }
  }
)

onUnmounted(() => stopTyping())

const durationText = computed(() => {
  if (props.running) return ''
  if (!props.durationMs) return ''
  if (props.durationMs < 1000) return `· ${props.durationMs}ms`
  const sec = props.durationMs / 1000
  if (sec < 60) return `· ${Number(sec.toFixed(sec < 10 ? 1 : 0))}秒`
  return `· ${Math.floor(sec / 60)}分${Math.round(sec % 60)}秒`
})
</script>

<style scoped>
.thinking-row {
  flex-shrink: 0;
  align-self: flex-start;
  max-width: 85%;
  margin-bottom: var(--ag-space-sm);
  animation: msgSlideUp 0.25s ease-out;
}
@keyframes msgSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.th-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-tertiary);
  padding: 2px 0;
  transition: color var(--ag-transition-fast);
}
.th-toggle:hover { color: var(--ag-text-secondary); }

.th-duration { font-size: 11px; color: var(--ag-text-disabled); }

.th-dot {
  width: 6px; height: 6px;
  border-radius: var(--ag-radius-full);
  background: var(--ag-warning);
  flex-shrink: 0;
}
.th-dot.running { animation: thPulse 1.6s ease-out infinite; }
@keyframes thPulse {
  0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; }
}

.th-chevron { transition: transform var(--ag-transition-base); }
.th-chevron.rotated { transform: rotate(90deg); }

.th-body {
  margin-top: var(--ag-space-xs);
  padding: var(--ag-space-sm) var(--ag-space-md);
  background: var(--ag-bg-page);
  border-radius: var(--ag-radius-md);
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-secondary);
  line-height: var(--ag-line-height-base);
  white-space: pre-wrap;
  word-break: break-word;
}
.th-waiting { color: var(--ag-text-disabled); font-style: italic; }
.th-cursor { animation: thBlink 1s step-end infinite; color: var(--ag-primary); }
@keyframes thBlink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
</style>
