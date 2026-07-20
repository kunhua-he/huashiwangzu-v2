<template>
  <aside class="fm-nav-pane">
    <section class="fm-nav-section">
      <div class="fm-nav-section-label">个人收藏</div>
      <button
        type="button"
        class="fm-nav-item"
        data-folder="0"
        :class="{ active: currentKey === 'desktop' && !activeTag, 'fm-nav-drop': dragOverId === '0' }"
        @click="$emit('go-root')"
      >
        <Monitor class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">桌面</span>
      </button>
      <button
        type="button"
        class="fm-nav-item"
        :data-folder="documentsFolderId != null ? String(documentsFolderId) : undefined"
        :class="{ active: currentKey === 'documents' && !activeTag, 'fm-nav-drop': documentsFolderId != null && dragOverId === String(documentsFolderId) }"
        @click="$emit('open-named', 'documents')"
      >
        <FileText class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">文稿</span>
      </button>
      <button
        type="button"
        class="fm-nav-item"
        :data-folder="downloadsFolderId != null ? String(downloadsFolderId) : undefined"
        :class="{ active: currentKey === 'downloads' && !activeTag, 'fm-nav-drop': downloadsFolderId != null && dragOverId === String(downloadsFolderId) }"
        @click="$emit('open-named', 'downloads')"
      >
        <Download class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">下载</span>
      </button>
    </section>

    <section class="fm-nav-section">
      <div class="fm-nav-section-label">位置</div>
      <button
        type="button"
        class="fm-nav-item"
        :class="{ active: currentKey === 'recycle' && !activeTag }"
        @click="$emit('open-recycle')"
      >
        <Trash2 class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">回收站</span>
      </button>
      <button
        type="button"
        class="fm-nav-item"
        data-folder="0"
        :class="{ active: currentKey === 'desktop' && !activeNamed && !activeTag, 'fm-nav-drop': dragOverId === '0' }"
        @click="$emit('go-root')"
      >
        <HardDrive class="fm-nav-icon" :size="16" :stroke-width="2" />
        <span class="fm-nav-label">本机</span>
      </button>
    </section>

    <section class="fm-nav-section">
      <div class="fm-nav-section-label">
        <span>标签</span>
        <button type="button" class="fm-nav-edit-tags" title="自定义标签名" @click.stop="editLabels">编辑</button>
      </div>
      <button
        v-for="tag in tags"
        :key="tag.key"
        type="button"
        class="fm-nav-item"
        :class="{ active: activeTag === tag.key }"
        :title="`筛选 ${tag.name}`"
        @click="$emit('filter-tag', activeTag === tag.key ? null : tag.key)"
      >
        <span class="fm-tag-dot" :style="{ background: tag.color }" />
        <span class="fm-nav-label">{{ tag.name }}</span>
      </button>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { showPrompt } from '@/desktop/feedback/desktop-feedback'
import { Download, FileText, HardDrive, Monitor, Trash2 } from 'lucide-vue-next'
import {
  listTagsWithCustomNames,
  loadCustomTagLabels,
  saveCustomTagLabels,
  type FinderTagColor,
  type FinderTagDef,
} from './finder-tags'
import { dragState } from '@/desktop/drag-drop/drag-state'

const props = defineProps<{
  currentFolderId: number
  isRecycleBin: boolean
  activeNamed?: 'documents' | 'downloads' | null
  activeTag?: FinderTagColor | null
  documentsFolderId?: number | null
  downloadsFolderId?: number | null
}>()

defineEmits<{
  (e: 'go-root'): void
  (e: 'open-recycle'): void
  (e: 'open-named', key: 'documents' | 'downloads'): void
  (e: 'filter-tag', tag: FinderTagColor | null): void
}>()

const currentKey = computed(() => {
  if (props.isRecycleBin) return 'recycle'
  if (props.activeNamed === 'documents') return 'documents'
  if (props.activeNamed === 'downloads') return 'downloads'
  if (props.currentFolderId === 0) return 'desktop'
  return 'folder'
})

const labelTick = ref(0)
loadCustomTagLabels()
const tags = computed<FinderTagDef[]>(() => {
  void labelTick.value
  return listTagsWithCustomNames()
})

async function editLabels() {
  // one-by-one prompts are more reliable than a multi-line dialog
  const current = listTagsWithCustomNames()
  const next: Partial<Record<FinderTagColor, string>> = {}
  for (const tag of current) {
    const value = await showPrompt(
      `标签「${tag.key}」显示名（留空恢复默认「${tag.name}」）`,
      '自定义标签名',
      {
        defaultValue: tag.name,
        confirmText: '下一个',
        cancelText: '完成',
      },
    )
    if (value === null) break
    const name = String(value || '').trim()
    if (name) next[tag.key] = name.slice(0, 16)
  }
  if (Object.keys(next).length) {
    saveCustomTagLabels(next)
    labelTick.value += 1
  }
}

const dragOverId = computed(() => (dragState.isDragging ? dragState.dragOverId : null))
const documentsFolderId = computed(() => props.documentsFolderId ?? null)
const downloadsFolderId = computed(() => props.downloadsFolderId ?? null)
</script>

<style scoped>
.fm-nav-pane {
  height: calc(100% - 20px);
  margin: 10px 0 10px 10px;
  padding: 8px 0 12px;
  border-radius: 11px;
  box-sizing: border-box;
  overflow: auto;
  background: color-mix(in srgb, rgba(236, 236, 240, 0.72) 70%, rgba(255, 255, 255, 0.55));
  box-shadow:
    inset 0 0 0 0.5px rgba(255, 255, 255, 0.5),
    0 0 0 0.5px rgba(60, 60, 67, 0.08);
  backdrop-filter: blur(30px) saturate(170%);
  -webkit-backdrop-filter: blur(30px) saturate(170%);
}

.fm-nav-section + .fm-nav-section {
  margin-top: 14px;
}

.fm-nav-section-label {
  padding: 0 12px 4px;
  font: 600 11px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  color: rgba(60, 60, 67, 0.58);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.fm-nav-edit-tags {
  border: 0;
  background: transparent;
  color: rgba(10, 132, 255, 0.9);
  font: 500 11px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  cursor: pointer;
  padding: 0;
}

.fm-nav-item {
  width: calc(100% - 8px);
  height: 28px;
  margin: 0 4px 1px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 7px;
  color: rgba(29, 29, 31, 0.92);
  text-align: left;
  cursor: pointer;
  font: 400 13px/1.2 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
}

.fm-nav-item:hover {
  background: rgba(0, 0, 0, 0.05);
}

.fm-nav-item.active {
  background: rgba(10, 132, 255, 0.18);
}

.fm-nav-item.active .fm-nav-icon {
  color: var(--mac-app-accent, #0a84ff);
}

.fm-nav-icon {
  flex-shrink: 0;
  color: rgba(60, 60, 67, 0.62);
}

.fm-nav-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-tag-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: inset 0 0 0 0.5px rgba(0, 0, 0, 0.22);
  flex-shrink: 0;
}

.fm-nav-item.fm-nav-drop {
  background: color-mix(in srgb, rgba(0, 122, 255, 0.18) 80%, rgba(255, 255, 255, 0.4));
  box-shadow: inset 0 0 0 1px rgba(0, 122, 255, 0.35);
}
</style>
