<template>
  <div class="thinking-card" :class="{ open: isOpen }">
    <button class="th-header" @click="isOpen = !isOpen">
      <span class="th-indicator" :class="{ running: running }">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12">
          <circle cx="7" cy="7" r="6"/>
          <path d="M7 4v3l2 2"/>
        </svg>
      </span>
      <span class="th-label">{{ running ? '正在思考' : '思考完成' }}</span>
      <span class="th-status" v-if="!isOpen && !running">点击展开</span>
      <svg class="th-chevron" :class="{ rotated: isOpen }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
        <path d="M4 3l4 3-4 3"/>
      </svg>
    </button>
    <div v-show="isOpen" class="th-body">
      <p>{{ content }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ content: string; running?: boolean; collapsed?: boolean }>()
const isOpen = ref(!props.collapsed)
</script>

<style scoped>
.thinking-card {
  flex-shrink: 0;
  align-self: flex-start;
  max-width: 85%;
  margin-bottom: var(--ag-space-lg);
  border: 1px solid var(--ag-border-light);
  border-radius: var(--ag-radius-lg);
  background: var(--ag-bg-base);
  overflow: hidden;
  animation: msgSlideUp 0.25s ease-out;
  box-shadow: var(--ag-shadow-sm);
}
@keyframes msgSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.th-header {
  display: flex;
  align-items: center;
  gap: var(--ag-space-sm);
  width: 100%;
  padding: var(--ag-space-sm) var(--ag-space-md);
  border: none;
  background: none;
  cursor: pointer;
  color: #92400E;
  font-size: var(--ag-font-size-sm);
  transition: background var(--ag-transition-fast);
}
.th-header:hover { background: var(--ag-bg-hover); }

.th-indicator { color: #F59E0B; display: flex; }
.th-indicator.running { animation: thPulse 1.6s ease-out infinite; }
@keyframes thPulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}
.th-label { font-weight: 500; }
.th-status { margin-left: auto; font-size: var(--ag-font-size-xs); color: var(--ag-text-tertiary); opacity: 0.6; }
.th-chevron { transition: transform var(--ag-transition-base); margin-left: 4px; }
.th-chevron.rotated { transform: rotate(90deg); }

.th-body {
  padding: 0 var(--ag-space-md) var(--ag-space-md);
  border-left: 3px solid var(--ag-warning);
  margin: 0 var(--ag-space-md) var(--ag-space-sm);
  padding-left: var(--ag-space-sm);
}
	.th-body p {
	  margin: 0;
	  font-size: var(--ag-font-size-sm);
	  color: var(--ag-text-secondary);
	  line-height: var(--ag-line-height-base);
	}
</style>
