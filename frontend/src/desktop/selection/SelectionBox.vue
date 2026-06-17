<template>
  <div
    v-if="valid"
    class="selection-box-rect"
    :style="{
      left: rect.x + 'px',
      top: rect.y + 'px',
      width: rect.w + 'px',
      height: rect.h + 'px',
    }"
  />
</template>

<script setup lang="ts">
import { isBoxSelectionValid, selectionRect } from './selection-box-state'
const valid = isBoxSelectionValid
const rect = selectionRect
</script>

<style scoped>
.selection-box-rect {
  position: fixed;
  background: rgba(0, 120, 215, 0.12);
  border: 1px solid rgba(0, 120, 215, 0.5);
  pointer-events: none;
  z-index: 9999;
}
</style>
