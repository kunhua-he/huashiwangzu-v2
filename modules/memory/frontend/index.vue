<template>
  <div class="mem-stub">
    <div class="stub-card">
      <svg viewBox="0 0 48 48" fill="none" stroke="#2395bc" stroke-width="1.5" width="48" height="48">
        <path d="M24 6c-7 0-12 4-12 10 0 3 1 5 3 7-1 2-2 4-2 6 0 4 4 7 11 7s11-3 11-7c0-2-1-4-2-6 2-2 3-4 3-7 0-6-5-10-11-10z"/>
        <path d="M18 20h12M18 26h8"/>
      </svg>
      <h3>{{ copy.title }}</h3>
      <p>{{ copy.description }}</p>
      <span class="stub-hint">{{ copy.hint }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMemoryOverview } from './composables/useMemoryOverview'

const { copy } = useMemoryOverview()
</script>

<style scoped>
.mem-stub { display: flex; align-items: center; justify-content: center; height: 100%; background: var(--bg-page, #f5f6f8); }
.stub-card { text-align: center; padding: 48px; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); max-width: 360px; }
.stub-card h3 { margin: 16px 0 8px; font-size: 18px; color: #333; }
.stub-card p { margin: 0 0 12px; color: #666; font-size: 14px; }
.stub-hint { font-size: 12px; color: #999; }
</style>
