<template>
  <div class="recycle-bin-container">
    <div class="recycle-bin-toolbar">
      <el-button size="small" @click="关闭回收站"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <span class="recycle-bin-title">回收站</span>
      <span style="flex:1" />
      <el-button v-if="可业务写" size="small" type="danger" plain @click="emit('清空')" :disabled="回收站列表.length === 0">
        <el-icon><Delete /></el-icon> 清空回收站
      </el-button>
    </div>
    <div class="recycle-bin-list" v-loading="回收站加载中" @contextmenu.prevent>
      <el-table :data="回收站列表" stripe size="small" style="width:100%" empty-text="回收站是空的" @row-contextmenu="行右键">
        <el-table-column label="名称" min-width="200">
          <template #default="{ row }">
            <div class="filename-cell">
              <el-icon><Document v-if="row.类型 === '文件'" /><Folder v-else /></el-icon>
              {{ row.名称 }}<span v-if="row.format">.{{ row.format }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="类型" label="类型" width="80" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ row.类型 === '文件' ? 格式化大小(row.大小) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="回收时间" label="删除时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="可业务写" link type="primary" size="small" @click="emit('还原', row.类型, row.id)">还原</el-button>
            <el-button v-if="可业务写" link type="danger" size="small" @click="emit('彻底删除', row.类型, row.id)">彻底删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Delete, Document, Folder } from '@element-plus/icons-vue'
import { usePermission } from '@/shared/composables/use-permission'
import type { RecycleBinEntry } from '@/shared/api/types'

defineProps<{
  回收站列表: RecycleBinEntry[]
  回收站加载中: boolean
}>()

const emit = defineEmits<{
  (e: '关闭'): void
  (e: '还原', 类型: '文件' | '文件夹', id: number): void
  (e: '彻底删除', 类型: '文件' | '文件夹', id: number): void
  (e: '清空'): void
  (e: '行右键', row: RecycleBinEntry, column: unknown, event: MouseEvent): void
}>()

function 行右键(row: RecycleBinEntry, column: unknown, event: MouseEvent) {
  emit('行右键', row, column, event)
}

const { isEditorOrAbove: 可业务写 } = usePermission()

function 关闭回收站() { emit('关闭') }
function 格式化大小(字节: number): string {
  if (!字节 || 字节 === 0) return '-'
  const 单位 = ['B', 'KB', 'MB', 'GB']
  let 大小 = 字节, 单位索引 = 0
  while (大小 >= 1024 && 单位索引 < 单位.length - 1) { 大小 /= 1024; 单位索引++ }
  return 大小.toFixed(1) + ' ' + 单位[单位索引]
}
</script>

<style scoped>
.recycle-bin-container { display: flex; flex-direction: column; height: 100%; }
.recycle-bin-toolbar { padding: 12px 16px; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; gap: 8px; }
.recycle-bin-title { font-size: 14px; font-weight: 600; color: #303133; }
.recycle-bin-list { flex: 1; overflow-y: auto; }
.filename-cell { display: flex; align-items: center; gap: 6px; }
</style>
