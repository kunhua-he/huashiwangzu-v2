<template>
  <el-dropdown trigger="click" placement="top-end" class="taskbar-user-menu-wrapper">
    <button class="taskbar-user-menu-button" type="button">
      <el-avatar :size="22">
        {{ 用户Store.userInfo?.displayName?.[0] || 用户Store.userInfo?.username?.[0] || '?' }}
      </el-avatar>
      <span class="taskbar-user-menu-name">{{ 用户名 }}</span>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item @click="处理退出">退出登录</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/platform/stores/user'

const 用户Store = useUserStore()
const 用户名 = computed(() => 用户Store.userInfo?.displayName || 用户Store.userInfo?.username || '用户')

async function 处理退出() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await 用户Store.logout()
    window.location.href = '/'
  } catch {
    // 用户取消，不做任何操作
  }
}
</script>

<style scoped>
.taskbar-user-menu-wrapper {
  display: flex;
  align-items: center;
}
.taskbar-user-menu-button {
  display: flex; align-items: center; gap: 6px;
  padding: 0 8px; height: 28px; border: none; background: transparent;
  color: #dbeafe; cursor: pointer; border-radius: 4px;
  opacity: .82; transition: background .12s, opacity .12s;
}
.taskbar-user-menu-button:hover { background: rgba(255,255,255,.08); opacity: 1; }
.taskbar-user-menu-name { font-size: 12px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
