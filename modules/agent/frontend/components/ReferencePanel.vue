<template>
  <aside class="ref-panel">
    <div class="ref-header">
      <h4 class="ref-title">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" width="14" height="14">
          <path d="M2 2h3l2 2v10H4a2 2 0 01-2-2V2z"/>
          <path d="M7 4h5v10H7V4z"/>
        </svg>
        引用来源
      </h4>
      <span class="ref-count">{{ references.length }}</span>
    </div>

    <div v-if="references.length === 0" class="ref-empty">
      <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1" width="24" height="24" class="ref-empty-icon">
        <path d="M4 6h24v20H4V6z"/>
        <path d="M4 12h24"/>
      </svg>
      <p>暂无引用</p>
    </div>

    <div class="ref-list">
      <article
        v-for="(r, idx) in references" :key="idx"
        class="ref-card"
        :class="{ active: r === activeRef }"
        @click="$emit('select', r)"
      >
        <div class="ref-card-header">
          <span class="ref-card-type">{{ r.type }}</span>
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" width="12" height="12" class="ref-card-icon">
            <path d="M6 4L2 8l4 4M10 4l4 4-4 4"/>
          </svg>
        </div>
        <strong class="ref-card-title">{{ r.title || r.source }}</strong>
        <p class="ref-card-excerpt" v-if="r.excerpt">{{ r.excerpt }}</p>
      </article>
    </div>
  </aside>
</template>

<script setup lang="ts">
 defineProps<{
   references: RefItem[]
   activeRef: RefItem | null
 }>()

 defineEmits<{
   select: [ref: RefItem]
 }>()

 interface RefItem { type: string; title: string; source: string; excerpt: string }
</script>

<style scoped>
.ref-panel {
  position: absolute;
  top: 56px;
  right: var(--ag-space-md);
  width: 280px;
  max-height: calc(100% - 140px);
  background: var(--ag-bg-base);
  border: 1px solid var(--ag-border-light);
  border-radius: var(--ag-radius-lg);
  box-shadow: var(--ag-shadow-lg);
  display: flex;
  flex-direction: column;
  z-index: 20;
  overflow: hidden;
}

.ref-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ag-space-md) var(--ag-space-lg);
  border-bottom: 1px solid var(--ag-border-light);
  flex-shrink: 0;
}
.ref-title {
  display: flex;
  align-items: center;
  gap: var(--ag-space-sm);
  margin: 0;
  font-size: var(--ag-font-size-md);
  font-weight: 600;
  color: var(--ag-text-primary);
}
.ref-title svg { color: var(--ag-primary); }
.ref-count {
  font-size: var(--ag-font-size-xs);
  background: var(--ag-bg-page);
  color: var(--ag-text-tertiary);
  padding: 1px 7px;
  border-radius: 10px;
}

.ref-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--ag-text-tertiary);
  gap: var(--ag-space-sm);
}
.ref-empty-icon { opacity: 0.3; }
.ref-empty p { margin: 0; font-size: var(--ag-font-size-sm); }

.ref-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--ag-space-sm);
}

.ref-card {
  padding: var(--ag-space-md);
  border: 1px solid var(--ag-border-light);
  border-radius: var(--ag-radius-md);
  margin-bottom: var(--ag-space-sm);
  cursor: pointer;
  transition: all var(--ag-transition-fast);
}
.ref-card:hover {
  border-color: var(--ag-primary);
  box-shadow: var(--ag-shadow-sm);
}
.ref-card.active {
  border-color: var(--ag-primary);
  background: var(--ag-primary-light);
}

.ref-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--ag-space-xs);
}
.ref-card-type {
  font-size: var(--ag-font-size-xs);
  color: var(--ag-text-tertiary);
  text-transform: uppercase;
}
.ref-card-icon { color: var(--ag-text-tertiary); }
.ref-card.active .ref-card-icon { color: var(--ag-primary); }

.ref-card-title {
  display: block;
  font-size: var(--ag-font-size-base);
  color: var(--ag-text-primary);
  margin-bottom: var(--ag-space-xs);
  line-height: var(--ag-line-height-tight);
}
.ref-card-excerpt {
  margin: 0;
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-secondary);
  line-height: var(--ag-line-height-base);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
