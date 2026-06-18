<template>
  <aside class="fm-nav-pane">
    <button
      class="fm-nav-item"
      :class="{ 'fm-nav-item-active': currentFolderId === 0 && !isRecycleBin }"
      type="button"
      @click="$emit('go-root')"
    >
      <span class="fm-nav-icon">🏠</span>
      <span class="fm-nav-label">桌面</span>
    </button>
    <button
      class="fm-nav-item"
      :class="{ 'fm-nav-item-active': isRecycleBin }"
      type="button"
      @click="$emit('open-recycle')"
    >
      <span class="fm-nav-icon">🗑</span>
      <span class="fm-nav-label">回收站</span>
    </button>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  currentFolderId: number
  isRecycleBin: boolean
}>()

defineEmits<{
  (e: 'go-root'): void
  (e: 'open-recycle'): void
}>()
</script>

<style scoped>
.fm-nav-pane {
  padding: 12px 8px;
  border-right: 1px solid #d9e2ec;
  background: linear-gradient(180deg, #f8fbff, #edf3f9);
}

.fm-nav-item {
  width: 100%;
  height: 34px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  color: #243244;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
}

.fm-nav-item:hover,
.fm-nav-item-active {
  background: rgba(255, 255, 255, 0.86);
  border-color: rgba(148, 163, 184, 0.45);
}

.fm-nav-icon {
  font-size: 16px;
  line-height: 1;
  flex-shrink: 0;
}

.fm-nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
