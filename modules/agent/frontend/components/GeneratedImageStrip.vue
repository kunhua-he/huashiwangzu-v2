<template>
  <div class="generated-images">
    <button
      v-for="image in images"
      :key="image.file_id"
      type="button"
      class="generated-image-button"
      :title="image.name || `file #${image.file_id}`"
      @click="openImage(image)"
    >
      <img
        v-if="imageUrls[image.file_id]"
        :src="imageUrls[image.file_id]"
        class="generated-image"
        :alt="image.name || '生成图片'"
      />
      <span v-else class="generated-image-loading">加载中</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { apiFetchRaw } from '../api'
import { openDesktopFile } from '../utils/desktopFileOpen'

export interface GeneratedImageEntry {
  type?: string
  file_id: number
  name?: string
  format?: string
  [key: string]: unknown
}

const props = defineProps<{
  images: GeneratedImageEntry[]
}>()

const imageUrls = ref<Record<number, string>>({})

function revokeUrls() {
  for (const url of Object.values(imageUrls.value)) {
    URL.revokeObjectURL(url)
  }
  imageUrls.value = {}
}

async function loadImages() {
  revokeUrls()
  const nextUrls: Record<number, string> = {}
  await Promise.all(props.images.map(async image => {
    try {
      const response = await apiFetchRaw(`/files/download/${image.file_id}`)
      if (!response.ok) throw new Error(`文件下载接口返回 ${response.status}`)
      const blob = await response.blob()
      nextUrls[image.file_id] = URL.createObjectURL(blob)
    } catch (error) {
      console.warn('[agent] load generated image failed', image.file_id, error)
    }
  }))
  imageUrls.value = nextUrls
}

function openImage(image: GeneratedImageEntry) {
  if (openDesktopFile({
    fileId: image.file_id,
    fileName: image.name || '',
    format: image.format || image.name?.split('.').pop() || 'png',
  })) return
  const url = imageUrls.value[image.file_id]
  if (!url) return
  window.open(url, '_blank', 'noopener')
}

watch(
  () => props.images.map(image => image.file_id).join(','),
  () => { void loadImages() },
  { immediate: true },
)

onBeforeUnmount(revokeUrls)
</script>

<style scoped>
.generated-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.generated-image-button {
  width: min(320px, 100%);
  min-height: 120px;
  padding: 0;
  border: 1px solid var(--ag-border-light, #e5e5e5);
  border-radius: 6px;
  background: #f8f8f8;
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.generated-image-button:hover {
  transform: scale(1.02);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.generated-image {
  display: block;
  width: 100%;
  max-height: 260px;
  object-fit: contain;
}

.generated-image-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  color: var(--ag-text-tertiary);
  font-size: var(--ag-font-size-sm);
}
</style>
