<template>
  <div class="memory-container">
    <div class="header">
      <h2>我的记忆</h2>
      <el-button type="primary" @click="showSave = true">记一条</el-button>
    </div>

    <el-dialog v-model="showSave" title="记一条记忆" width="450px" @close="resetForm">
      <el-form :model="form" label-position="top">
        <el-form-item label="内容" required>
          <el-input v-model="form.text" type="textarea" :rows="4"
            placeholder="如：我们品牌主色是 #2395bc" />
        </el-form-item>
        <el-form-item label="标签（可选）">
          <el-input v-model="form.tags" placeholder="如：品牌,配色,风格" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>

    <div class="search-bar">
      <el-input v-model="query" placeholder="搜索记忆..." clearable style="width:300px"
        @keyup.enter="handleRecall" />
      <el-button @click="handleRecall" style="margin-left:8px">搜索</el-button>
      <el-button @click="loadList" style="margin-left:4px">全部</el-button>
    </div>

    <el-table :data="items" v-loading="loading" empty-text="暂无记忆">
      <el-table-column prop="text" label="内容" min-width="200">
        <template #default="{ row }">
          <div class="memory-text" :title="row.text">{{ row.text }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="tags" label="标签" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.tags" size="small">{{ row.tags }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="160" />
      <el-table-column label="操作" width="70">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="handleDelete(row.id)">删</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { memory, type MemoryItem } from '../runtime/index'

const items = ref<MemoryItem[]>([])
const loading = ref(false)
const showSave = ref(false)
const saving = ref(false)
const query = ref('')

const form = ref({ text: '', tags: '' })

function resetForm() {
  form.value = { text: '', tags: '' }
}

async function loadList() {
  loading.value = true
  try {
    items.value = await memory.list()
  } catch (e: any) {
    console.error('加载记忆失败', e)
  } finally {
    loading.value = false
  }
}

async function handleRecall() {
  if (!query.value.trim()) {
    await loadList()
    return
  }
  loading.value = true
  try {
    items.value = await memory.recall({ query: query.value })
  } catch (e: any) {
    console.error('搜索失败', e)
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!form.value.text.trim()) return
  saving.value = true
  try {
    await memory.save({ text: form.value.text, tags: form.value.tags || undefined })
    showSave.value = false
    await loadList()
  } catch (e: any) {
    console.error('保存失败', e)
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await memory.delete(id)
    await loadList()
  } catch (e: any) {
    console.error('删除失败', e)
  }
}

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.memory-container {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
  font-size: 18px;
  color: #2395bc;
}

.search-bar {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}

.memory-text {
  max-height: 48px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
