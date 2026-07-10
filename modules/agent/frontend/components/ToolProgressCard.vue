<template>
  <div class="tool-progress-row">
    <button class="tool-progress-toggle" @click="isOpen = !isOpen">
      <span class="tool-progress-dot" :class="stateClass"></span>
      <span class="tool-progress-title">{{ title }}</span>
      <span v-if="durationText" class="tool-progress-duration">{{ durationText }}</span>
      <svg class="tool-progress-chevron" :class="{ rotated: isOpen }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
        <path d="M4 3l4 3-4 3" />
      </svg>
    </button>
    <div v-show="isOpen" class="tool-progress-body">
      <div v-if="steps.length" class="tool-progress-steps">
        <div v-for="step in steps" :key="step.key" class="tool-progress-step">
          <span class="tool-progress-step-dot" :class="step.status"></span>
          <span class="tool-progress-step-name" :title="step.rawName">{{ step.name }}</span>
          <span class="tool-progress-step-status">{{ step.statusLabel }}</span>
          <span v-if="step.elapsedMs" class="tool-progress-step-time">{{ formatDuration(step.elapsedMs) }}</span>
        </div>
      </div>
      <div v-else class="tool-progress-empty">等待工具节点返回</div>
      <button v-if="nodes.length" type="button" class="tool-progress-detail-toggle" @click="detailsOpen = !detailsOpen">
        <span>{{ detailsOpen ? '收起底层事件' : `查看底层事件 ${nodes.length} 条` }}</span>
        <svg class="tool-progress-chevron" :class="{ rotated: detailsOpen }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
          <path d="M4 3l4 3-4 3" />
        </svg>
      </button>
      <div v-show="detailsOpen" class="tool-progress-nodes">
        <div v-for="(node, index) in nodes" :key="`${node.toolCallId || node.toolName || index}-${node.node}-${node.status}`" class="tool-progress-node" :class="{ muted: isLowLevelNode(node) }">
          <span class="tool-progress-node-dot" :class="node.status"></span>
          <span class="tool-progress-node-name">{{ rawNodeTitle(node) }}</span>
          <span class="tool-progress-node-status">{{ statusText(node.status) }}</span>
          <span v-if="node.elapsedMs" class="tool-progress-node-time">{{ formatDuration(node.elapsedMs) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  displayToolName,
  effectiveToolName,
  formatDuration,
  isLowLevelNode,
  semanticNodeName,
  statusText,
} from './toolDisplay'

type ToolInfo = {
  name?: string
  effective_tool_name?: string
  tool_call_id?: string
}

type ToolProgressMessage = {
  executionMode?: string
  groupIndex?: number
  groupCount?: number
  toolCount?: number
  toolName?: string
  toolCallId?: string
  toolNodes?: ToolProgressMessage[]
  node?: string
  status?: string
  targetTool?: string
  elapsedMs?: number
  durationMs?: number
  tools?: ToolInfo[]
}

type StepInfo = {
  key: string
  name: string
  rawName: string
  status: string
  statusLabel: string
  elapsedMs: number
}

const props = defineProps<{
  message: ToolProgressMessage
}>()

const isOpen = ref(true)
const detailsOpen = ref(false)

const tools = computed<ToolInfo[]>(() => props.message.tools || [])
const nodes = computed<ToolProgressMessage[]>(() => props.message.toolNodes || [])
const meaningfulNodes = computed(() => nodes.value.filter(node => !isLowLevelNode(node)))

const steps = computed<StepInfo[]>(() => {
  const latestByKey = new Map<string, StepInfo>()
  for (const node of meaningfulNodes.value) {
    const rawName = semanticNodeName(node)
    const status = node.status || 'started'
    latestByKey.set(`${node.toolCallId || rawName}:${rawName}`, {
      key: `${node.toolCallId || rawName}:${rawName}`,
      name: displayToolName(rawName),
      rawName,
      status,
      statusLabel: statusText(status),
      elapsedMs: Number(node.elapsedMs) || 0,
    })
  }
  if (latestByKey.size) return [...latestByKey.values()]
  return tools.value.map((tool, index) => {
    const rawName = effectiveToolName(tool)
    const status = stateClass.value === 'running' ? 'started' : stateClass.value === 'failed' ? 'failed' : 'completed'
    return {
      key: tool.tool_call_id || `${rawName}:${index}`,
      name: displayToolName(rawName),
      rawName,
      status,
      statusLabel: statusText(status),
      elapsedMs: 0,
    }
  })
})

const title = computed(() => {
  const mode = props.message.executionMode === 'parallel' ? '并行执行' : '工具执行'
  const count = props.message.toolCount || tools.value.length || 1
  const state = stateClass.value === 'running' ? '进行中' : stateClass.value === 'failed' ? '有异常' : '已完成'
  const indexText = props.message.groupIndex && props.message.groupCount && props.message.groupCount > 1
    ? ` ${props.message.groupIndex}/${props.message.groupCount}`
    : ''
  return `${mode}${indexText} · ${state} · ${count} 个工具`
})

const stateClass = computed(() => {
  if (nodes.value.some(node => node.status === 'timeout' || node.status === 'failed')) return 'failed'
  if (nodes.value.some(node => node.status === 'started')) return 'running'
  return 'ready'
})

const durationText = computed(() => {
  const ms = props.message.durationMs || props.message.elapsedMs || 0
  return ms ? `· ${formatDuration(ms)}` : ''
})

watch(
  () => [props.message.executionMode, nodes.value.length, stateClass.value, steps.value.length],
  () => { isOpen.value = props.message.executionMode === 'parallel' || stateClass.value === 'failed' || steps.value.length > 0 },
  { immediate: true },
)

function rawNodeTitle(node: ToolProgressMessage): string {
  const toolName = node.targetTool || node.toolName || ''
  const nodeName = node.node || 'tool_node'
  if (toolName && toolName !== node.toolName) return `${nodeName} · ${toolName}`
  return nodeName
}
</script>

<style scoped>
.tool-progress-row {
  flex-shrink: 0;
  align-self: flex-start;
  max-width: 95%;
  margin-bottom: var(--ag-space-sm);
}

.tool-progress-toggle {
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
.tool-progress-toggle:hover { color: var(--ag-text-secondary); }

.tool-progress-dot,
.tool-progress-step-dot,
.tool-progress-node-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--ag-radius-full);
  flex-shrink: 0;
}
.tool-progress-dot.ready { background: var(--ag-text-disabled); }
.tool-progress-dot.running {
  background: var(--ag-primary);
  animation: toolProgressPulse 1.6s ease-out infinite;
}
.tool-progress-dot.failed { background: var(--ag-error); }
@keyframes toolProgressPulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.tool-progress-title {
  color: var(--ag-text-secondary);
  font-weight: 500;
}
.tool-progress-duration,
.tool-progress-step-time,
.tool-progress-node-time {
  font-size: 11px;
  color: var(--ag-text-disabled);
}
.tool-progress-chevron {
  transition: transform var(--ag-transition-base);
  flex-shrink: 0;
}
.tool-progress-chevron.rotated { transform: rotate(90deg); }

.tool-progress-body {
  margin-top: var(--ag-space-xs);
  padding: var(--ag-space-xs) 0 var(--ag-space-xs) var(--ag-space-md);
  border-left: 1px solid var(--ag-border-light);
}
.tool-progress-steps,
.tool-progress-nodes {
  display: grid;
  gap: 4px;
}
.tool-progress-detail-toggle + .tool-progress-nodes { margin-top: var(--ag-space-xs); }
.tool-progress-step,
.tool-progress-node {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 18px;
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-secondary);
}
.tool-progress-step-name {
  color: var(--ag-text-primary);
  font-weight: 500;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-progress-step-status {
  flex-shrink: 0;
  color: var(--ag-text-tertiary);
}
.tool-progress-step-dot {
  width: 5px;
  height: 5px;
  background: var(--ag-text-disabled);
  opacity: 0.85;
}
.tool-progress-step-dot.started { background: var(--ag-primary); }
.tool-progress-step-dot.completed { background: var(--ag-success); }
.tool-progress-step-dot.timeout,
.tool-progress-step-dot.failed,
.tool-progress-step-dot.blocked { background: var(--ag-error); }
.tool-progress-node-dot {
  width: 5px;
  height: 5px;
  background: var(--ag-text-disabled);
  opacity: 0.7;
}
.tool-progress-node-dot.started { background: var(--ag-primary); }
.tool-progress-node-dot.completed { background: var(--ag-success); }
.tool-progress-node-dot.timeout,
.tool-progress-node-dot.failed,
.tool-progress-node-dot.blocked { background: var(--ag-error); }
.tool-progress-node-name {
  font-family: var(--ag-font-mono);
  color: var(--ag-text-primary);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-progress-node-status {
  color: var(--ag-text-tertiary);
  flex-shrink: 0;
}
.tool-progress-node.muted {
  opacity: 0.66;
}
.tool-progress-node-time { margin-left: auto; }
.tool-progress-step-time { margin-left: auto; }
.tool-progress-detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: fit-content;
  margin-top: var(--ag-space-xs);
  padding: 0;
  border: none;
  background: none;
  color: var(--ag-text-tertiary);
  cursor: pointer;
  font-size: var(--ag-font-size-xs);
}
.tool-progress-detail-toggle:hover { color: var(--ag-text-secondary); }
.tool-progress-empty {
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-disabled);
}
</style>
