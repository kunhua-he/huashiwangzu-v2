<template>
  <span class="file-visual-icon" :style="styleObject" v-html="svgSource" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  kind: 'file' | 'folder'
  size?: number
  extension?: string
}>(), {
  size: 20,
  extension: '',
})

function folderSvg() {
  return `
<svg viewBox="0 0 64 52" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="f1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8ec8ff"/>
      <stop offset="100%" stop-color="#4d9dff"/>
    </linearGradient>
    <linearGradient id="f2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#69b4ff"/>
      <stop offset="100%" stop-color="#2f86f0"/>
    </linearGradient>
  </defs>
  <path d="M6 14c0-3.2 2.5-5.8 5.7-5.8h11.2l4.2 4.1h24.2c3.2 0 5.7 2.6 5.7 5.8v3.2H6V14z" fill="url(#f1)"/>
  <path d="M4 19.2c0-3.1 2.5-5.6 5.6-5.6h44.8c3.1 0 5.6 2.5 5.6 5.6V38c0 4.1-3.3 7.4-7.4 7.4H11.4C7.3 45.4 4 42.1 4 38V19.2z" fill="url(#f2)"/>
  <path d="M8 22.5h48v2.4H8z" fill="#d7ebff" opacity=".55"/>
</svg>`
}

function docSvg(ext: string, accent: string, labelColor = '#6e6e73') {
  const label = (ext || 'DOC').slice(0, 4).toUpperCase()
  return `
<svg viewBox="0 0 48 60" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="p" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#f2f2f5"/>
    </linearGradient>
  </defs>
  <path d="M8 2h22l12 12v40c0 2.2-1.8 4-4 4H8c-2.2 0-4-1.8-4-4V6c0-2.2 1.8-4 4-4z" fill="url(#p)" stroke="rgba(0,0,0,0.12)" stroke-width="1"/>
  <path d="M30 2v10c0 1.1.9 2 2 2h10" fill="#eef0f4"/>
  <path d="M30 2l12 12" stroke="rgba(0,0,0,0.08)" stroke-width="1"/>
  <path d="M12 28h24M12 35h24M12 42h16" stroke="${accent}" stroke-width="2.2" stroke-linecap="round" opacity=".55"/>
  <text x="24" y="22" text-anchor="middle" font-size="8" font-weight="700" font-family="-apple-system,BlinkMacSystemFont,Arial,sans-serif" fill="${labelColor}">${label}</text>
</svg>`
}

function iconFor(extRaw: string) {
  const ext = (extRaw || '').toLowerCase()
  if (['doc', 'docx'].includes(ext)) return docSvg(ext, '#185abd', '#185abd')
  if (['xls', 'xlsx', 'csv'].includes(ext)) return docSvg(ext, '#107c41', '#107c41')
  if (['ppt', 'pptx'].includes(ext)) return docSvg(ext, '#c43e1c', '#c43e1c')
  if (ext === 'pdf') return docSvg('pdf', '#d70015', '#d70015')
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return docSvg(ext, '#0a84ff', '#0a84ff')
  if (['zip', 'rar', '7z'].includes(ext)) return docSvg(ext, '#ff9f0a', '#b86e00')
  if (['md', 'txt', 'log', 'json', 'yaml', 'yml', 'xml'].includes(ext)) return docSvg(ext || 'txt', '#8e8e93', '#636366')
  return docSvg(ext || 'file', '#8e8e93', '#636366')
}

const svgSource = computed(() => (props.kind === 'folder' ? folderSvg() : iconFor(props.extension || '')))
const styleObject = computed(() => ({ width: `${props.size}px`, height: `${props.size}px` }))
</script>

<style scoped>
.file-visual-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}
.file-visual-icon :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}
</style>
