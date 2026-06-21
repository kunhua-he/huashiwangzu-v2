<template>
  <div class="scheduler-container">
    <div class="header">
      <h2>定时任务</h2>
      <el-button type="primary" @click="showCreate = true">新建定时任务</el-button>
    </div>

    <el-dialog v-model="showCreate" title="新建定时任务" width="500px" @close="resetForm">
      <el-form :model="form" label-position="top">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="如：每日工作汇报" />
        </el-form-item>
        <el-form-item label="动作描述" required>
          <el-input v-model="form.action_description" type="textarea" :rows="3"
            placeholder="到点要做什么？如：汇总今天新增的知识库文件，推给我" />
        </el-form-item>
        <el-form-item label="执行时间">
          <el-date-picker v-model="form.scheduled_at" type="datetime" placeholder="不选则立即执行"
            value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item label="周期">
          <el-select v-model="form.recur" placeholder="不选=单次" clearable>
            <el-option label="每小时" value="hourly" />
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="自定义 (cron:HH:MM)" value="cron" />
          </el-select>
          <el-input v-if="form.recur === 'cron'" v-model="form.cronExpr" placeholder="cron:09:00"
            style="margin-top:8px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>

    <el-table :data="tasks" v-loading="loading" empty-text="暂无定时任务">
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="scheduled_at" label="执行时间" width="160" />
      <el-table-column prop="recur" label="周期" width="120" />
      <el-table-column prop="next_run_at" label="下次运行" width="160" />
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" type="danger" size="small"
            @click="handleCancel(row.id)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { scheduler } from '../runtime/index'

interface TaskItem {
  id: number
  title: string
  action_description: string
  status: string
  scheduled_at: string | null
  recur: string | null
  next_run_at: string | null
  result: string | null
  error_message: string | null
  created_at: string | null
}

const tasks = ref<TaskItem[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)

const form = ref({
  title: '',
  action_description: '',
  scheduled_at: null as string | null,
  recur: null as string | null,
  cronExpr: '',
})

function statusType(s: string): string {
  if (s === 'completed') return 'success'
  if (s === 'running') return 'primary'
  if (s === 'failed' || s === 'cancelled') return 'danger'
  return 'warning'
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '待执行', running: '执行中', completed: '已完成',
    failed: '失败', cancelled: '已取消',
  }
  return map[s] || s
}

function resetForm() {
  form.value = { title: '', action_description: '', scheduled_at: null, recur: null, cronExpr: '' }
}

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await scheduler.list()
  } catch (e: any) {
    console.error('加载定时任务失败', e)
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.value.title || !form.value.action_description) return
  creating.value = true
  try {
    const recurVal = form.value.recur === 'cron' ? form.value.cronExpr : form.value.recur
    await scheduler.create({
      title: form.value.title,
      action_description: form.value.action_description,
      scheduled_at: form.value.scheduled_at || undefined,
      recur: recurVal || undefined,
    })
    showCreate.value = false
    await loadTasks()
  } catch (e: any) {
    console.error('创建定时任务失败', e)
  } finally {
    creating.value = false
  }
}

async function handleCancel(taskId: number) {
  try {
    await scheduler.cancel(taskId)
    await loadTasks()
  } catch (e: any) {
    console.error('取消失败', e)
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.scheduler-container {
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
</style>
