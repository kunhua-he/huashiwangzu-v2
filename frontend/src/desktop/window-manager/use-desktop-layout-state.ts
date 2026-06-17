import { computed, ref } from 'vue'

const sidebarCollapsed = ref(false)

export function useDesktopLayoutState() {
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value }
  function setSidebarCollapsed(v: boolean) { sidebarCollapsed.value = v }
  return {
    sidebarCollapsed: computed(() => sidebarCollapsed.value),
    toggleSidebar,
    setSidebarCollapsed,
  }
}
