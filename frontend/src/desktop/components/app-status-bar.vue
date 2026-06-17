<template>
  <div class="app-status-bar">
    <slot />
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.app-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 24px;
  min-height: 24px;
  padding: 0 12px;
  font-size: 11px;
  color: var(--text-info, #909399);
  border-top: 1px solid var(--border-color, #e4e7ed);
  box-sizing: border-box;
  background: transparent;
  flex-shrink: 0;
}
</style>
