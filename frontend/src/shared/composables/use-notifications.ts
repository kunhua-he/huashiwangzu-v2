import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/shared/api'
import type { NotificationItem } from '@/shared/api/types'

interface NotificationListResponse {
  success: boolean
  data: {
    list: NotificationItem[]
  }
}

interface UnreadCountResponse {
  success: boolean
  data: {
    unread_count: number
  }
}

interface MutationResponse {
  success: boolean
}

async function fetchNotificationList() {
  const res = await api.get('/notifications')
  return res.data as NotificationListResponse
}
async function fetchUnreadCount() {
  const res = await api.get('/notifications/unread-count')
  return res.data as UnreadCountResponse
}
async function markReadRequest(id: number) {
  const res = await api.post(`/notifications/${id}/read`)
  return res.data as MutationResponse
}
async function markAllReadRequest() {
  const res = await api.post('/notifications/read-all')
  return res.data as MutationResponse
}

export function useNotifications(containerSelector = '.taskbar-notifications-wrapper') {
  const unreadCount = ref(0)
  const notificationList = ref<NotificationItem[]>([])
  const showNotificationPanel = ref(false)

  async function loadUnreadCount() {
    try {
      const res = await fetchUnreadCount()
      if (res.success) {
        unreadCount.value = res.data.unread_count
      }
    } catch {
      unreadCount.value = 0
    }
  }

  async function loadNotificationList() {
    try {
      const res = await fetchNotificationList()
      if (res.success) {
        notificationList.value = res.data.list
      }
    } catch {
      notificationList.value = []
    }
  }

  async function markRead(id: number) {
    try {
      const res = await markReadRequest(id)
      if (res.success) {
        const item = notificationList.value.find((n) => n.id === id)
        if (item) item.is_read = true
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch {
      console.warn('[Notifications] Failed to mark notification as read.')
    }
  }

  async function markAllRead() {
    try {
      const res = await markAllReadRequest()
      if (res.success) {
        notificationList.value.forEach((n) => { n.is_read = true })
        unreadCount.value = 0
      }
    } catch {
      console.warn('[Notifications] Failed to mark all notifications as read.')
    }
  }

  function toggleNotificationPanel() {
    showNotificationPanel.value = !showNotificationPanel.value
    if (showNotificationPanel.value) {
      loadNotificationList()
    }
  }

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement
    if (!target.closest(containerSelector)) {
      showNotificationPanel.value = false
    }
  }

  onMounted(() => {
    loadUnreadCount()
    document.addEventListener('click', handleClickOutside)
  })

  onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside)
  })

  return {
    unreadCount,
    notificationList,
    showNotificationPanel,
    toggleNotificationPanel,
    loadUnreadCount,
    markRead,
    markAllRead,
  }
}
