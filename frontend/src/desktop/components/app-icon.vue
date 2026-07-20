<template>
  <img
    v-if="profile.imageUrl"
    class="app-icon-native-image"
    :src="profile.imageUrl"
    :style="styleObject"
    :data-app-icon-key="profile.key"
    alt=""
    draggable="false"
    aria-hidden="true"
  >
  <span
    v-else
    class="app-icon"
    :class="{
      'app-icon-sm': size <= 22,
      'app-icon-lg': size >= 40,
    }"
    :style="styleObject"
    :data-app-icon-key="profile.key"
    aria-hidden="true"
  >
    <span class="app-icon-fill" />
    <span class="app-icon-gloss" />
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
/** macOS 彩色方块上 SF Symbol 大约 52–58% */
const glyphSize = computed(() => Math.max(11, Math.round(props.size * (props.size >= 40 ? 0.56 : 0.52))))
const glyphStroke = computed(() => (props.size >= 40 ? 1.85 : 1.95))
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
/*
  更接近 Apple 图标语言：
  - squircle 圆角（~22.37%）
  - 竖向渐变底色
  - 顶部轻微 gloss（不是假玻璃多层）
  - 居中白线标
*/
.app-icon {
  position: relative;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  overflow: hidden;
  border-radius: 22.37%;
  color: var(--app-icon-accent, #fff);
  isolation: isolate;
  transform: translateZ(0);
  box-shadow:
    0 0.5px 0.5px rgba(0, 0, 0, 0.12),
    0 2px 6px rgba(0, 0, 0, 0.16);
}
.app-icon-fill {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, var(--app-icon-from) 0%, var(--app-icon-to) 100%);
  box-shadow:
    inset 0 0.6px 0 rgba(255, 255, 255, 0.42),
    inset 0 -1px 1.5px rgba(0, 0, 0, 0.14);
}
/* 顶部柔光：系统图标常见的轻微镜面，不是网页 sheen 条 */
.app-icon-gloss {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background:
    radial-gradient(120% 70% at 50% -10%, rgba(255, 255, 255, 0.38), transparent 52%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.18), transparent 42%);
  pointer-events: none;
  mix-blend-mode: soft-light;
}
.app-icon-native-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
  background: transparent;
}
.app-icon-glyph {
  position: relative;
  z-index: 1;
  width: 56%;
  height: 56%;
  color: var(--app-icon-accent, #fff);
  stroke: currentColor;
  filter: drop-shadow(0 0.5px 0.5px rgba(0, 0, 0, 0.18));
}
.app-icon-sm {
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.14);
}
.app-icon-sm .app-icon-glyph {
  width: 54%;
  height: 54%;
  filter: none;
}
.app-icon-sm .app-icon-gloss {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.16), transparent 50%);
  mix-blend-mode: normal;
}
.app-icon-lg {
  box-shadow:
    0 0.5px 0.5px rgba(0, 0, 0, 0.1),
    0 3px 8px rgba(0, 0, 0, 0.18),
    0 8px 18px rgba(0, 0, 0, 0.1);
}
</style>
