<template>
  <span
    class="app-icon"
    :class="{ 'app-icon-sm': size <= 22, 'app-icon-lg': size >= 40 }"
    :style="styleObject"
    :data-app-icon-key="profile.key"
    aria-hidden="true"
  >
    <component
      :is="profile.glyph"
      class="app-icon-glyph"
      :size="glyphSize"
      :stroke-width="glyphStroke"
      :color="glyphColor"
    />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getAppIconProfile } from './app-icon-catalog'

const props = withDefaults(defineProps<{ icon: string; appKey?: string; size?: number }>(), { size: 20, appKey: '' })

const profile = computed(() => getAppIconProfile(props.appKey, props.icon))
/** 参考 Dock：glyph 约占方块 58% */
const glyphSize = computed(() => Math.max(11, Math.round(props.size * (props.size >= 40 ? 0.58 : 0.52))))
const glyphStroke = computed(() => (props.size >= 40 ? 1.8 : 1.9))
const glyphColor = computed(() => profile.value.accent || '#ffffff')
const styleObject = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  '--app-icon-from': profile.value.from,
  '--app-icon-to': profile.value.to,
  '--app-icon-accent': profile.value.accent,
}))
</script>

<style scoped>
/* 系统 Dock 图标：满格圆角渐变 + 居中线标，不要多层 sheen/rim 假玻璃 */
.app-icon {
  position: relative;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  overflow: hidden;
  border-radius: 22.37%;
  color: var(--app-icon-accent, #fff);
  background: linear-gradient(180deg, var(--app-icon-from), var(--app-icon-to));
  box-shadow:
    inset 0 0.5px 0 rgba(255, 255, 255, 0.35),
    0 1px 2px rgba(0, 0, 0, 0.18);
  transform: translateZ(0);
}
.app-icon-glyph {
  width: 58%;
  height: 58%;
  color: var(--app-icon-accent, #fff);
  stroke: currentColor;
  filter: none;
}
.app-icon-sm {
  border-radius: 6px;
  box-shadow: inset 0 0.5px 0 rgba(255, 255, 255, 0.3), 0 1px 1px rgba(0, 0, 0, 0.14);
}
.app-icon-sm .app-icon-glyph {
  width: 54%;
  height: 54%;
}
.app-icon-lg {
  box-shadow:
    inset 0 0.5px 0 rgba(255, 255, 255, 0.38),
    0 1px 2px rgba(0, 0, 0, 0.2),
    0 4px 10px rgba(0, 0, 0, 0.12);
}
</style>
