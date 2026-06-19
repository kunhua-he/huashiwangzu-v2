<template>
  <div class="desktop-tools-panel">
    <h3>Desktop Tools</h3>
    <p class="text-muted">Background service: exposes desktop/file capabilities to Agent via skill discovery.</p>
  </div>
</template>

<script setup lang="ts">
// Desktop Tools is a backend-only module — the frontend is a placeholder.
// All functionality is exposed via cross-module capabilities.
</script>

<style scoped>
.desktop-tools-panel {
  padding: 20px;
}
.text-muted {
  color: #999;
  font-size: 14px;
}
</style>
