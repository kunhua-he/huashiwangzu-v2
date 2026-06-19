<template>
  <div class="thinking-row">
    <button class="th-toggle" @click="isOpen = !isOpen">
      <span class="th-dot" :class="{ running: running }"></span>
      <span>思维过程</span>
      <svg class="th-chevron" :class="{ rotated: isOpen }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
        <path d="M4 3l4 3-4 3"/>
      </svg>
    </button>
    <div v-show="isOpen" class="th-body">{{ normalizedContent }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{ content: string; running?: boolean; collapsed?: boolean }>()
const isOpen = ref(!props.collapsed)

/** 去掉换行符，压缩连续空格，不引入新空格 */
function normalize(text: string): string {
  return text.replace(/[\n\r]+/g, '').replace(/[ \t]{2,}/g, ' ').trim()
}

const normalizedContent = computed(() => normalize(props.content || ''))
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

.th-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--ag-radius-full);
  background: var(--ag-warning);
  flex-shrink: 0;
}
.th-dot.running {
  animation: thPulse 1.6s ease-out infinite;
}
@keyframes thPulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.th-chevron {
  transition: transform var(--ag-transition-base);
}
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
</style>
