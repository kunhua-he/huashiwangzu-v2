<template>
  <div class="sandbox-app">
    <div class="sandbox-badge" style="display:none;">sandbox</div>
    <ExcelEditor />
  </div>
</template>

<script setup lang="ts">
import ExcelEditor from '@modules/excel-engine/frontend/index.vue'
</script>

<style>
body { margin: 0; padding: 0; height: 100vh; overflow: hidden; }
#app { height: 100vh; }
.sandbox-app { height: 100vh; }
</style>
