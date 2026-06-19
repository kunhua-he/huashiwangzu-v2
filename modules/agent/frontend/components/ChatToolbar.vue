<template>
  <header class="chat-toolbar">
    <div class="toolbar-left">
      <div class="model-selector">
        <label class="model-label">模型</label>
        <select :value="profileKey" class="model-select" @change="$emit('update:profileKey', ($event.target as HTMLSelectElement).value)">
          <option v-for="m in profiles" :key="m.key" :value="m.key">{{ m.name || m.key }}</option>
        </select>
      </div>
      <div class="toolbar-divider"></div>
      <button
        class="toolbar-item"
        :class="{ active: refPanelVisible }"
        @click="$emit('toggleRef')"
        title="引用来源面板"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" width="15" height="15">
          <path d="M3 2v12h10V2H3zM6 2v12M3 7h10M3 11h10"/>
        </svg>
        <span>引用</span>
      </button>
    </div>
    <div class="toolbar-right">
      <button class="toolbar-item primary" @click="$emit('newConv')" title="新建对话">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" width="15" height="15">
          <path d="M8 3v10M3 8h10"/>
        </svg>
        <span>新对话</span>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  profiles: ModelProfile[]
  profileKey: string
  refPanelVisible: boolean
}>()

const emit = defineEmits<{
  'update:profileKey': [key: string]
  toggleRef: []
  newConv: []
}>()

interface ModelProfile { key: string; name: string; provider: string; model: string }
</script>

<style scoped>
.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ag-space-sm) var(--ag-space-lg);
  background: var(--ag-bg-base);
  border-bottom: 1px solid var(--ag-border-light);
  flex-shrink: 0;
  gap: var(--ag-space-md);
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--ag-space-sm);
}
.model-selector {
  display: flex;
  align-items: center;
  gap: var(--ag-space-sm);
}
.model-label {
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-tertiary);
  white-space: nowrap;
}
.model-select {
  height: 30px;
  padding: 0 28px 0 10px;
  border: 1px solid var(--ag-border-base);
  border-radius: var(--ag-radius-md);
  background: var(--ag-bg-input) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none' stroke='%239B9B9B' stroke-width='1.5'%3E%3Cpath d='M1 1l4 4 4-4'/%3E%3C/svg%3E") no-repeat right 10px center;
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-primary);
  cursor: pointer;
  outline: none;
  appearance: none;
  transition: border-color var(--ag-transition-fast);
  min-width: 120px;
}
.model-select:focus {
  border-color: var(--ag-primary);
  background-color: var(--ag-bg-base);
}

.toolbar-divider {
  width: 1px;
  height: 18px;
  background: var(--ag-border-light);
  margin: 0 var(--ag-space-xs);
}

.toolbar-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: 1px solid transparent;
  border-radius: var(--ag-radius-md);
  background: none;
  color: var(--ag-text-secondary);
  cursor: pointer;
  font-size: var(--ag-font-size-sm);
  transition: all var(--ag-transition-fast);
  white-space: nowrap;
}
.toolbar-item:hover { background: var(--ag-bg-hover); color: var(--ag-text-primary); }
.toolbar-item.active {
  background: var(--ag-primary-light);
  color: var(--ag-primary);
  border-color: var(--ag-primary);
}
.toolbar-item.primary {
  background: var(--ag-primary);
  color: var(--ag-text-white);
}
.toolbar-item.primary:hover { background: var(--ag-primary-dark); }
</style>
