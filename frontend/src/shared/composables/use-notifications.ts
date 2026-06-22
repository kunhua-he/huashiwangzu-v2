import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/shared/api'
import type { NotificationItem } from '@/shared/api/types'

export function useNotifications(containerSelector = '.taskbar-notifications-wrapper') {
  const unreadCount = ref(0)
  const notificationList = ref<NotificationItem[]>([])
  const showNotificationPanel = ref(false)

  async function loadUnreadCount() {
    try {
      const data = await api.get<unknown, { unread_count: number }>('/notifications/unread-count')
      unreadCount.value = data.unread_count
    } catch {
      unreadCount.value = 0
    }
  }

  async function loadNotificationList() {
    try {
      const data = await api.get<unknown, { list: NotificationItem[] }>('/notifications')
      notificationList.value = data.list
    } catch {
      notificationList.value = []
    }
  }

  async function markRead(id: number) {
    try {
      await api.post(`/notifications/${id}/read`)
      const item = notificationList.value.find((n) => n.id === id)
      if (item) item.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch {
      console.warn('[Notifications] Failed to mark notification as read.')
    }
  }

  async function markAllRead() {
    try {
      await api.post('/notifications/read-all')
      notificationList.value.forEach((n) => { n.is_read = true })
      unreadCount.value = 0
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
