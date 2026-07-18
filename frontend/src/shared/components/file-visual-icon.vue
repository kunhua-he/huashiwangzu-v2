<template>
  <span class="file-visual-icon" :class="[`is-${kind}`]" :style="styleObject" aria-hidden="true">
    <!-- macOS-like folder: rounded body + raised tab, soft depth -->
    <svg v-if="kind === 'folder'" class="fv-svg" viewBox="0 0 64 52" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient :id="ids.tab" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#A8D8FF" />
          <stop offset="100%" stop-color="#7EC0FF" />
        </linearGradient>
        <linearGradient :id="ids.body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#7EBEFF" />
          <stop offset="55%" stop-color="#4EA3FF" />
          <stop offset="100%" stop-color="#2F86F0" />
        </linearGradient>
        <linearGradient :id="ids.sheen" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#FFFFFF" stop-opacity=".38" />
          <stop offset="40%" stop-color="#FFFFFF" stop-opacity="0" />
        </linearGradient>
        <filter :id="ids.shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1.2" stdDeviation="1.1" flood-color="#0B3A6E" flood-opacity=".22" />
        </filter>
      </defs>
      <!-- tab -->
      <path
        :filter="`url(#${ids.shadow})`"
        d="M7.5 15.2c0-2.6 2.1-4.7 4.7-4.7h12.1c1.1 0 2.1.4 2.9 1.2l2.6 2.5c.5.5 1.2.8 1.9.8h18.1c2.6 0 4.7 2.1 4.7 4.7v1.6H7.5v-6.1z"
        :fill="`url(#${ids.tab})`"
      />
      <!-- body -->
      <rect
        x="5"
        y="17.2"
        width="54"
        height="28.5"
        rx="6.2"
        :fill="`url(#${ids.body})`"
        :filter="`url(#${ids.shadow})`"
      />
      <rect x="5" y="17.2" width="54" height="28.5" rx="6.2" :fill="`url(#${ids.sheen})`" />
      <path d="M9 21.2h46" stroke="#E8F4FF" stroke-opacity=".55" stroke-width="1.6" stroke-linecap="round" />
    </svg>

    <!-- macOS-like document: white paper, dog-ear, type glyph, bottom extension -->
    <span v-else class="fv-doc" :style="docStyle">
      <span class="fv-doc-paper">
        <span class="fv-doc-glyph" v-html="typeGlyph" />
        <span class="fv-doc-ext">{{ extLabel }}</span>
      </span>
      <span class="fv-doc-ear" aria-hidden="true" />
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  kind: 'file' | 'folder'
  size?: number
  extension?: string
}>(), {
  size: 40,
  extension: '',
})

// Unique gradient/filter ids per instance (avoid SVG id collisions across grid cells)
const uid = `fv${Math.random().toString(36).slice(2, 9)}`
const ids = {
  tab: `${uid}-tab`,
  body: `${uid}-body`,
  sheen: `${uid}-sheen`,
  shadow: `${uid}-shadow`,
}

const styleObject = computed(() => {
  if (props.kind === 'folder') {
    return {
      width: `${props.size}px`,
      height: `${Math.round(props.size * 0.82)}px`,
    }
  }
  // document aspect closer to mac paper (about 0.78 w/h)
  const h = props.size
  const w = Math.round(props.size * 0.78)
  return {
    width: `${w}px`,
    height: `${h}px`,
    '--fv-ear': `${Math.max(6, Math.round(props.size * 0.22))}px`,
    '--fv-ext-size': `${Math.max(7, Math.round(props.size * 0.16))}px`,
  } as Record<string, string>
})

const docStyle = computed(() => ({
  width: '100%',
  height: '100%',
}))

const ext = computed(() => (props.extension || '').toLowerCase().replace(/^\./, ''))
const extLabel = computed(() => (ext.value || 'file').slice(0, 4).toUpperCase())

/** Compact monochrome glyphs (stroke), closer to SF/Lucide than brand tiles. */
const typeGlyph = computed(() => {
  const e = ext.value
  const common = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'heic'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m4.5 17 4.2-4.2a1.4 1.4 0 0 1 2 0L16 18"/><path d="m14 14 1.6-1.6a1.4 1.4 0 0 1 2 0L20 16"/></svg>`
  }
  if (['mp4', 'mov', 'mkv', 'webm', 'avi'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/></svg>`
  }
  if (['mp3', 'wav', 'aac', 'm4a', 'flac'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M9 18V6l10-2v12"/><circle cx="7" cy="18" r="2.2"/><circle cx="17" cy="16" r="2.2"/></svg>`
  }
  if (['zip', 'rar', '7z', 'gz', 'tar'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M8 3h5l5 5v12a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M13 3v5h5"/><path d="M10 8h2M10 11h2M10 14h2"/></svg>`
  }
  if (['pdf'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M8.5 16.5c.9-2.6 2.4-3.9 4.5-3.9 1.3 0 2 .5 2 1.4 0 1.8-2.5 1.6-3.6 2.4-.7.5-.9 1.2-.6 1.9"/></svg>`
  }
  if (['doc', 'docx', 'rtf', 'odt'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M8 13h8M8 16h6"/></svg>`
  }
  if (['xls', 'xlsx', 'csv', 'numbers'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 16h6M12 12v6"/></svg>`
  }
  if (['ppt', 'pptx', 'key'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><circle cx="12" cy="15" r="3"/></svg>`
  }
  if (['md', 'txt', 'log', 'json', 'yaml', 'yml', 'xml', 'ts', 'js', 'vue', 'py', 'go'].includes(e)) {
    return `<svg viewBox="0 0 24 24" ${common}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 16h4"/></svg>`
  }
  return `<svg viewBox="0 0 24 24" ${common}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/></svg>`
})
</script>

<style scoped>
.file-visual-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  line-height: 0;
}

.fv-svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

/* Document paper stack — matches reference FileIcon proportions */
.fv-doc {
  position: relative;
  display: block;
}

.fv-doc-paper {
  position: absolute;
  inset: 0;
  border-radius: 5px;
  background: linear-gradient(180deg, #ffffff 0%, #f2f2f5 100%);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.22),
    inset 0 0 0 0.5px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 18%;
  color: rgba(60, 60, 67, 0.72);
  overflow: hidden;
}

.fv-doc-glyph {
  width: 42%;
  height: 42%;
  display: grid;
  place-items: center;
  opacity: 0.88;
}

.fv-doc-glyph :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

.fv-doc-ext {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 9%;
  text-align: center;
  font: 700 var(--fv-ext-size, 8px)/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(60, 60, 67, 0.48);
  pointer-events: none;
}

/* Dog-ear fold (top-right) — same geometry as reference Finder FileIcon */
.fv-doc-ear {
  position: absolute;
  top: 0;
  right: 0;
  width: 0;
  height: 0;
  border-left: var(--fv-ear, 11px) solid transparent;
  border-top: var(--fv-ear, 11px) solid rgba(0, 0, 0, 0.1);
  border-radius: 0 5px 0 0;
  pointer-events: none;
}
</style>
