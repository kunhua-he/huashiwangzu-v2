<template>
  <span class="app-icon" :style="styleObject">
    <img v-if="imageUrl" class="app-icon-image" :src="imageUrl" :alt="icon" />
    <span v-else v-html="svgSource" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getAppSVG, getAppImage } from '@/shared/icons/app-icon-assets'

const props = withDefaults(defineProps<{ icon: string; size?: number }>(), { size: 20 })

const svgSource = computed(() => getAppSVG(props.icon))
const imageUrl = computed(() => getAppImage(props.icon))
const styleObject = computed(() => ({ width: `${props.size}px`, height: `${props.size}px` }))
</script>

<style scoped>
.app-icon { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; }
.app-icon-image { width: 100%; height: 100%; display: block; object-fit: contain; image-rendering: auto; }
.app-icon :deep(svg) { width: 100%; height: 100%; display: block; }
.app-icon :deep(path[fill='currentColor']) { fill: #e2e8f0; }
.app-icon :deep(path[fill='#212121']), .app-icon :deep(path[fill='black']), .app-icon :deep(path[fill='#000']) { fill: #dbeafe; }
</style>
