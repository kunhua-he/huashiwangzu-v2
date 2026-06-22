<template>
  <div class="excel-toolbar">
    <button class="tb-btn" @click="$emit('action', 'undo')" title="撤销 (Ctrl+Z)">↩</button>
    <button class="tb-btn" @click="$emit('action', 'redo')" title="恢复 (Ctrl+Y)">↪</button>
    <span class="tb-sep"></span>
    <button class="tb-btn" @click="$emit('action', 'save')" title="保存">💾</button>
    <button class="tb-btn" @click="$emit('action', 'export')" title="导出 XLSX">📥</button>
    <span class="tb-sep"></span>
    <button class="tb-btn" :class="{ active: activeStyles.bold }" @click="$emit('action', 'bold')" title="加粗 (Ctrl+B)"><b>B</b></button>
    <button class="tb-btn" :class="{ active: activeStyles.italic }" @click="$emit('action', 'italic')" title="倾斜 (Ctrl+I)"><i>I</i></button>
    <button class="tb-btn" :class="{ active: activeStyles.underline }" @click="$emit('action', 'underline')" title="下划线 (Ctrl+U)"><u>U</u></button>
    <button class="tb-btn" :class="{ active: activeStyles.strikethrough }" @click="$emit('action', 'strikethrough')" title="删除线">S̶</button>
    <span class="tb-sep"></span>
    <button class="tb-btn" :class="{ active: activeStyles.align === '左' }" @click="$emit('action', 'align_left')" title="左对齐">≡</button>
    <button class="tb-btn" :class="{ active: activeStyles.align === '居中' }" @click="$emit('action', 'align_center')" title="居中">≡</button>
    <button class="tb-btn" :class="{ active: activeStyles.align === '右' }" @click="$emit('action', 'align_right')" title="右对齐">≡</button>
    <span class="tb-sep"></span>
    <select class="tb-select" :value="activeStyles.fontName || '宋体'" @change="onFontChange" title="字体">
      <option v-for="f in fonts" :key="f" :value="f">{{ f }}</option>
    </select>
    <select class="tb-select" :value="activeStyles.fontSize || 11" @change="onFontSizeChange" title="字号" style="width: 56px;">
      <option v-for="s in fontSizes" :key="s" :value="s">{{ s }}</option>
    </select>
    <span class="tb-sep"></span>
    <div class="tb-color-wrap">
      <span style="padding: 0 4px; font-size: 11px;">🎨</span>
      <input type="color" :value="activeStyles.fillColor || '#ffffff'" @input="onFillColorChange" title="填充颜色" />
    </div>
    <div class="tb-color-wrap">
      <span style="padding: 0 4px; font-size: 11px;">A</span>
      <input type="color" :value="activeStyles.color || '#000000'" @input="onFontColorChange" title="字体颜色" />
    </div>
    <span class="tb-sep"></span>
    <button class="tb-btn" @click="$emit('action', 'merge')" title="合并单元格">🔗</button>
    <button class="tb-btn" :class="{ active: activeStyles.wrapText }" @click="$emit('action', 'wrap_text')" title="自动换行">↩</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  activeStyles: Record<string, unknown>
}>()

const emit = defineEmits<{
  action: [action: string]
  'style-change': [method: string, params: Record<string, unknown>]
}>()

const fonts = ['宋体', '微软雅黑', 'Arial', 'Times New Roman', 'Courier New', 'Verdana', 'Georgia']
const fontSizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 28, 36, 48, 72]

function onFontChange(e: Event) {
  emit('style-change', 'font', { value: (e.target as HTMLSelectElement).value })
}

function onFontSizeChange(e: Event) {
  emit('style-change', 'font_size', { value: parseFloat((e.target as HTMLSelectElement).value) })
}

function onFillColorChange(e: Event) {
  emit('style-change', 'fill_color', { color: (e.target as HTMLInputElement).value })
}

function onFontColorChange(e: Event) {
  emit('style-change', 'font_color', { color: (e.target as HTMLInputElement).value })
}
</script>

<style scoped>
.excel-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1px;
  padding: 4px 6px;
  background: linear-gradient(180deg, #f8f9fa 0%, #eef0f2 100%);
  border-bottom: 1px solid #c0c0c0;
  flex-shrink: 0;
}
.tb-sep {
  display: inline-block;
  width: 1px;
  height: 20px;
  background: #c8c8c8;
  margin: 0 4px;
}
.tb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  color: #444;
  transition: background 0.1s;
}
.tb-btn:hover { background: #dde1e6; border-color: #bbb; }
.tb-btn:active { background: #c8ccd0; }
.tb-btn.active { background: #d4d8dc; border-color: #999; }
.tb-select {
  height: 24px;
  border: 1px solid #c0c0c0;
  border-radius: 3px;
  font-size: 11px;
  padding: 0 4px;
  color: #333;
  background: #fff;
  cursor: pointer;
  outline: none;
}
.tb-select:hover { border-color: #888; }
.tb-color-wrap {
  display: inline-flex;
  align-items: center;
  border: 1px solid #c0c0c0;
  border-radius: 3px;
  overflow: hidden;
  cursor: pointer;
  height: 24px;
}
.tb-color-wrap:hover { border-color: #888; }
.tb-color-wrap input[type="color"] {
  width: 20px;
  height: 22px;
  padding: 0;
  border: none;
  cursor: pointer;
}
</style>
