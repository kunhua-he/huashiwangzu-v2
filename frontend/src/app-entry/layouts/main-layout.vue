<template>
  <div class="main-layout">
    <div v-if="maintenanceVisible" class="maintenance-banner" :data-status="maintenanceStatus">
      <span class="maintenance-banner-title">{{ maintenanceTitle }}</span>
      <span class="maintenance-banner-meta">{{ maintenanceMeta }}</span>
    </div>
    <!-- 在 V1.5 中：当路由为 /desktop 时，由桌面壳接管全屏布局，隐藏传统侧边栏与顶部栏 -->
    <div v-if="currentPath !== '/desktop'" class="layout-sidebar">
      <div class="layout-sidebar-title">华世王镞</div>
      <div class="layout-sidebar-menu">
        <el-menu :default-active="currentPath" router>
          <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="getIconComponent(item.icon)" /></el-icon>
            <span>{{ item.name }}</span>
          </el-menu-item>
        </el-menu>
      </div>
    </div>

    <div class="main-content">
      <div v-if="currentPath !== '/desktop'" class="topbar">
        <div class="topbar-left">
          <div class="notification-button" @click="toggleNotificationPanel">
            <el-badge :value="unreadCount" :hidden="unreadCount <= 0" class="notification-badge">
              <el-icon :size="22"><Bell /></el-icon>
            </el-badge>
            <NoticePanel
              :show="showNotificationPanel"
              :items="notificationList"
              @mark-read="markRead"
              @mark-all-read="markAllRead"
            />
          </div>
        </div>
        <div class="topbar-right">
          <el-button class="feedback-button" type="primary" size="small" @click="showFeedbackDialog = true">
            问题反馈
          </el-button>
           <FeedbackSubmitDialog :show="showFeedbackDialog" @close="showFeedbackDialog = false" @submit-success="showFeedbackDialog = false" />
          <el-dropdown trigger="click" @command="handleDropdown">
            <span style="cursor: pointer; display: flex; align-items: center; gap: 8px;">
              <el-avatar :size="32" style="background: var(--primary-color);">
                {{ store.userInfo?.displayName?.charAt(0) || '?' }}
              </el-avatar>
              <span>{{ store.userInfo?.displayName || '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <div class="content-area">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Component } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowDown, Bell } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/platform/stores/user'
import { usePermission } from '@/shared/composables/use-permission'
import NoticePanel from '@/shared/components/notification-panel.vue'
import FeedbackSubmitDialog from './feedback-submit-dialog.vue'
import { useNotifications } from '@/shared/composables/use-notifications'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import type { MenuItem } from '@/shared/api/types'
import api from '@/shared/api'

const showFeedbackDialog = ref(false)
const route = useRoute()
const store = useUserStore()
const currentPath = computed(() => route.path)
const { unreadCount, notificationList, showNotificationPanel, toggleNotificationPanel, markRead, markAllRead } = useNotifications('.notification-button')
const { canAccessMenu } = usePermission()

type MaintenanceStatus = 'normal' | 'draining' | 'restarting' | 'failed'

interface MaintenanceState {
  status: MaintenanceStatus
  restart_requested: boolean
  reason?: string
}

interface MaintenanceBlockers {
  running_tasks: number
  active_upload_sessions: number
}

interface MaintenanceSnapshot {
  state: MaintenanceState
  blockers: MaintenanceBlockers
}

const maintenanceSnapshot = ref<MaintenanceSnapshot | null>(null)
let maintenanceTimer: number | undefined

const maintenanceStatus = computed(() => maintenanceSnapshot.value?.state.status ?? 'normal')
const maintenanceVisible = computed(() => maintenanceStatus.value !== 'normal')
const maintenanceTitle = computed(() => {
  if (maintenanceStatus.value === 'draining') return '系统维护中'
  if (maintenanceStatus.value === 'restarting') return '后台重启中'
  if (maintenanceStatus.value === 'failed') return '维护状态异常'
  return ''
})
const maintenanceMeta = computed(() => {
  const blockers = maintenanceSnapshot.value?.blockers
  if (!blockers) return ''
  const running = blockers.running_tasks || 0
  const uploads = blockers.active_upload_sessions || 0
  if (maintenanceStatus.value === 'draining') return `已有任务继续，新任务排队，运行中 ${running}，上传 ${uploads}`
  return maintenanceSnapshot.value?.state.reason || ''
})

const allMenuItems: MenuItem[] = [
  { name: '桌面', path: '/desktop', icon: 'Files' },
]

const menuItems = computed(() => allMenuItems.filter(item => canAccessMenu(item)))

function getIconComponent(name: string) {
  return (ElementPlusIconsVue as Record<string, unknown>)[name] as Component
}

function handleDropdown(command: string) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定退出登录？', '提示').then(() => {
      store.logout().finally(() => {
        window.location.replace('/')
      })
    }).catch(() => {})
  }
}

async function refreshMaintenanceStatus(): Promise<void> {
  try {
    maintenanceSnapshot.value = await api.get('/maintenance/status') as unknown as MaintenanceSnapshot
  } catch {
    // Keep the last known state; API errors are already handled globally.
  }
}

onMounted(() => {
  void refreshMaintenanceStatus()
  maintenanceTimer = window.setInterval(() => {
    void refreshMaintenanceStatus()
  }, 5000)
})

onUnmounted(() => {
  if (maintenanceTimer !== undefined) {
    window.clearInterval(maintenanceTimer)
  }
})
</script>

<style scoped>
.maintenance-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 3000;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  min-height: 34px;
  padding: 6px 16px;
  color: #1f2937;
  background: #fff7ed;
  border-bottom: 1px solid #fed7aa;
  font-size: 13px;
}

.maintenance-banner[data-status="restarting"] {
  background: #eff6ff;
  border-bottom-color: #bfdbfe;
}

.maintenance-banner[data-status="failed"] {
  color: #7f1d1d;
  background: #fef2f2;
  border-bottom-color: #fecaca;
}

.maintenance-banner-title {
  font-weight: 600;
}

.maintenance-banner-meta {
  color: #4b5563;
}
</style>
