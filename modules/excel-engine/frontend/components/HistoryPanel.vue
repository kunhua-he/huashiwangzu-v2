<template>
  <div class="history-panel">
    <div class="history-header">
      <span>操作历史</span>
      <button class="history-close" @click="$emit('close')">✕</button>
    </div>
    <div class="history-list">
      <div v-for="item in list" :key="item.id" class="history-item"
        @click="$emit('preview', item.id)">
        <span class="history-icon">{{ icon(item.action) }}</span>
        <div class="history-info">
          <div class="history-action">{{ item.action }}</div>
          <div class="history-desc">{{ item.description || item.cell_addr }}</div>
        </div>
        <span class="history-time">{{ time(item.created_at) }}</span>
      </div>
      <div v-if="list.length === 0" class="history-empty">暂无操作记录</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  list: any[]
}>()

defineEmits<{
  close: []
  preview: [id: number]
}>()

const ICONS: Record<string, string> = {
  '输入': '✏️', '批量填充': '📝', '清除': '🗑️', '超链接': '🔗', '设置格式': '📐',
  '加粗': '𝐁', '倾斜': '𝐼', '下划线': 'U̲', '删除线': 'S̶',
  '左对齐': '≡', '居中': '≡', '右对齐': '≡',
  '设置字体': '🔤', '设置字号': '🔡', '填充色': '🎨', '字体色': '🎨',
  '换行': '↩️', '边框': '🔲', '粘贴': '📋', '合并': '🔗', '排序': '↕️',
  '删除行': '➖', '删除列': '︱', '插入行上': '🔼', '插入行下': '🔽',
  '插入列左': '◀️', '插入列右': '▶️', '保存版本': '💾',
}

function icon(action: string): string {
  return ICONS[action] || '⚡'
}

function time(isoStr: string): string {
  return isoStr ? isoStr.replace('T', ' ').substring(0, 16) : ''
}
</script>

<style scoped>
.history-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 240px;
  height: 100%;
  background: #f8f9fa;
  border-left: 1px solid #d0d0d0;
  display: flex;
  flex-direction: column;
  z-index: 100;
  box-shadow: -2px 0 8px rgba(0,0,0,0.1);
}
.history-header {
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #333;
  border-bottom: 1px solid #e0e0e0;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: #999;
  padding: 2px;
}
.history-close:hover { color: #333; }
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  margin: 2px 0;
  border-radius: 5px;
  cursor: pointer;
  font-size: 11px;
  background: #fff;
  border: 1px solid #eee;
  transition: background 0.15s, border-color 0.15s;
}
.history-item:hover { background: #e8f0fe; border-color: #4a90d9; }
.history-icon { font-size: 12px; flex-shrink: 0; }
.history-info { flex: 1; min-width: 0; }
.history-action { font-weight: 500; color: #333; }
.history-desc { color: #666; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-time { font-size: 9px; color: #aaa; flex-shrink: 0; }
.history-empty { padding: 12px; text-align: center; color: #999; font-size: 11px; }
</style>
