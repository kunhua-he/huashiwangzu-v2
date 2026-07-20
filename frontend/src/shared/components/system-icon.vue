<template>
  <component
    :is="resolvedIcon"
    v-if="resolvedIcon"
    :size="size"
    :stroke-width="strokeWidth"
    :class="className"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'
import {
  Archive,
  ArrowDownToLine,
  ArrowLeft,
  ArrowUp,
  ArrowUpRight,
  Check,
  CheckSquare,
  Clipboard,
  Copy,
  Download,
  ExternalLink,
  FilePlus2,
  FileText,
  Folder,
  FolderOpen,
  Grid2X2,
  Grid3X3,
  Image,
  Info,
  LayoutGrid,
  List,
  ListFilter,
  Menu,
  MoreVertical,
  Move,
  Package,
  Pencil,
  Pin,
  RefreshCw,
  RotateCcw,
  Rows3,
  Scissors,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Square,
  Tag,
  Trash2,
  Upload,
} from '@/shared/icons/lucide'
import type { SystemIconName } from '@/shared/icons/contracts'

const props = withDefaults(defineProps<{
  icon?: SystemIconName | string
  size?: number
  strokeWidth?: number
  className?: string
}>(), {
  icon: '',
  size: 15,
  strokeWidth: 1.8,
  className: '',
})

const SEMANTIC_ICONS: Record<SystemIconName, Component> = {
  archive: Archive,
  check: Check,
  copy: Copy,
  delete: Trash2,
  details: Info,
  download: Download,
  folder: Folder,
  'folder-open': FolderOpen,
  image: Image,
  list: List,
  menu: Menu,
  open: ExternalLink,
  refresh: RefreshCw,
  settings: SlidersHorizontal,
  upload: Upload,
}

const ICONS: Record<string, Component> = {
  '↗': ArrowUpRight,
  '⌖': FolderOpen,
  '⬇': Download,
  '📂': FolderOpen,
  '📁': Folder,
  '📄': FileText,
  '📕': FileText,
  '📘': FileText,
  '📗': FileText,
  '📙': FileText,
  '⬆': Upload,
  '✂': Scissors,
  '📋': Clipboard,
  '❐': Copy,
  '⎘': ExternalLink,
  '🏷': Tag,
  'ⓘ': Info,
  '📦': Package,
  '✎': Pencil,
  '🗑': Trash2,
  '🧹': Sparkles,
  '📌': Pin,
  '⊞': LayoutGrid,
  '▦': Grid2X2,
  '≣': List,
  '▥': Rows3,
  '▤': Image,
  '⇅': ListFilter,
  '↻': RefreshCw,
  '☑': CheckSquare,
  '☰': Menu,
  '⋮': MoreVertical,
  '⌗': Grid3X3,
  '⚙️': Settings,
  '✅': Check,
  '🖼': Image,
  '🖼️': Image,
  '↩': RotateCcw,
  '+': FilePlus2,
  '−': Move,
  '⬇️': ArrowDownToLine,
  '←': ArrowLeft,
  '□': Square,
  ...SEMANTIC_ICONS,
}

const resolvedIcon = computed(() => ICONS[props.icon] || null)
</script>
