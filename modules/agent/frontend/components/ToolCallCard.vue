<template>
  <div
    class="tool-card"
    :class="[message.eventType === 'tool_call' ? 'calling' : 'result']"
  >
    <div class="tc-header">
      <span class="tc-icon">
        <svg v-if="message.eventType === 'tool_call'" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" width="14" height="14">
          <circle cx="8" cy="8" r="6"/>
          <path d="M8 5v3l2 2"/>
        </svg>
        <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" width="14" height="14">
          <path d="M14 8A6 6 0 112 8a6 6 0 0112 0z"/>
          <path d="M5.5 8l2 2 3-4"/>
        </svg>
      </span>
      <span class="tc-name">
        <template v-if="message.eventType === 'tool_call'">
          正在调用 <strong>{{ message.toolName }}</strong>
          <span class="tc-dots">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </span>
        </template>
        <template v-else>
          <strong>{{ message.toolName }}</strong> 返回结果
        </template>
      </span>
      <button class="tc-toggle" @click="isOpen = !isOpen" :title="isOpen ? '收起' : '展开详情'">
        <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
          <path d="M4 3l4 3-4 3"/>
        </svg>
      </button>
    </div>
    <div v-show="isOpen && message.eventType === 'tool_result'" class="tc-body">
      <pre>{{ formatResult(message.toolResult) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

 defineProps<{
   message: {
     eventType?: string
     toolName?: string
     toolResult?: unknown
   }
 }>()

const isOpen = ref(false)

function formatResult(r: unknown): string {
  if (typeof r === 'string') return r
  try { return JSON.stringify(r, null, 2) } catch { return String(r) }
}
</script>

<style scoped>
.tool-card {
  align-self: flex-start;
  max-width: 85%;
  margin-bottom: var(--ag-space-lg);
  border-radius: var(--ag-radius-lg);
  overflow: hidden;
  animation: msgSlideUp 0.25s ease-out;
}
@keyframes msgSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.tool-card.calling {
  background: #F0F7FF;
  border: 1px solid #BAE0FF;
}
.tool-card.result {
  background: var(--ag-bg-page);
  border: 1px solid var(--ag-border-light);
}

.tc-header {
  display: flex;
  align-items: center;
  gap: var(--ag-space-sm);
  padding: var(--ag-space-sm) var(--ag-space-md);
}
.tc-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.tool-card.calling .tc-icon { color: #1677FF; }
.tool-card.result .tc-icon { color: var(--ag-success); }

.tc-name {
  flex: 1;
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.tc-name strong { color: var(--ag-text-primary); }

.tc-dots { display: inline-flex; gap: 2px; margin-left: 2px; }
.tc-dots .dot {
  width: 4px; height: 4px; border-radius: var(--ag-radius-full);
  background: #1677FF;
  animation: toolDot 1.2s ease-in-out infinite;
}
.tc-dots .dot:nth-child(2) { animation-delay: 0.2s; }
.tc-dots .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes toolDot { 0%, 100% { opacity: 0.3; transform: scale(1); } 50% { opacity: 1; transform: scale(1.3); } }

.tc-toggle {
  border: none; background: none; cursor: pointer;
  padding: 2px; color: var(--ag-text-tertiary);
  transition: color var(--ag-transition-fast);
  display: flex; align-items: center;
}
.tc-toggle:hover { color: var(--ag-text-secondary); }

.tc-body {
  padding: 0 var(--ag-space-md) var(--ag-space-md);
}
.tc-body pre {
  white-space: pre-wrap; word-break: break-all;
  max-height: 200px; overflow: auto;
  background: var(--ag-bg-base);
  padding: var(--ag-space-sm) var(--ag-space-md);
  border-radius: var(--ag-radius-md);
  font-size: var(--ag-font-size-sm);
  font-family: var(--ag-font-mono);
  color: var(--ag-text-secondary);
  margin: 0;
}
</style>
