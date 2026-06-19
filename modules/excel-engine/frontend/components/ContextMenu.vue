<template>
  <div v-if="visible" class="context-menu" :style="{ left: x + 'px', top: y + 'px' }">
    <div class="cm-section">
      <div class="cm-item" @click="$emit('action', 'cut')">剪切</div>
      <div class="cm-item" @click="$emit('action', 'copy')">复制</div>
      <div class="cm-item" @click="$emit('action', 'paste')">粘贴</div>
    </div>
    <div class="cm-section">
      <div class="cm-item cm-has-sub" @mouseenter="subMenu = 'clear'">
        清除
        <div v-if="subMenu === 'clear'" class="cm-sub">
          <div class="cm-item" @click="$emit('action', 'clear_all')">清除全部</div>
          <div class="cm-item" @click="$emit('action', 'clear_format')">清除格式</div>
          <div class="cm-item" @click="$emit('action', 'clear_content')">清除内容</div>
        </div>
      </div>
    </div>
    <div class="cm-section">
      <div class="cm-item" @click="$emit('action', 'merge')">合并单元格</div>
      <div class="cm-item" @click="$emit('action', 'unmerge')">取消合并</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  visible: boolean
  x: number
  y: number
}>()

defineEmits<{
  action: [action: string]
}>()

const subMenu = ref('')
</script>

<style scoped>
.context-menu {
  position: fixed;
  z-index: 1000;
  background: #fff;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  box-shadow: 2px 2px 12px rgba(0,0,0,0.12);
  min-width: 160px;
  padding: 4px 0;
}
.cm-section { padding: 2px 0; border-bottom: 1px solid #eee; }
.cm-section:last-child { border-bottom: none; }
.cm-item {
  padding: 6px 14px;
  font-size: 12px;
  color: #333;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
}
.cm-item:hover { background: #e8f0fe; }
.cm-has-sub { position: relative; }
.cm-sub {
  position: absolute;
  left: 100%;
  top: -4px;
  background: #fff;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
  min-width: 120px;
  z-index: 1001;
}
</style>
