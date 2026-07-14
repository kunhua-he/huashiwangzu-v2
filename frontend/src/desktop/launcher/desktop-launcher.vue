<template>
  <Teleport to="body">
    <Transition name="launcher-fade">
      <div v-if="show" class="launcher-overlay" @click.self="emit('close')">
        <Transition name="launcher-slide">
          <div v-if="show" class="launcher-panel" :style="{ width: panelWidth + 'px' }" @click.stop>
            <!-- 搜索栏 -->
            <div class="launcher-search">
              <span class="launcher-search-icon">🔍</span>
              <input
                ref="searchInputRef"
                v-model="searchText"
                class="launcher-search-input"
                type="text"
                placeholder="搜索应用和命令..."
                @keydown.escape="handleEscape"
              />
            </div>

            <!-- 搜索模式 -->
            <template v-if="isSearching">
              <div class="launcher-section-header">搜索结果</div>
              <div v-if="searchResults.length" class="launcher-search-results">
                <button
                  v-for="item in searchResults"
                  :key="item.id"
                  class="launcher-search-item"
                  type="button"
                  @click="executeSearchResult(item)"
                >
                  <AppIcon :icon="item.icon || fallbackIcon(item.type)" :size="24" />
                  <div class="launcher-search-item-text">
                    <div class="launcher-search-item-row">
                      <span class="launcher-search-item-title">{{ item.title }}</span>
                      <span class="launcher-search-item-badge">{{ resultKindLabel(item.type) }}</span>
                    </div>
                    <span v-if="item.description" class="launcher-search-item-desc">{{ item.description }}</span>
                  </div>
                </button>
              </div>
              <div v-else class="launcher-empty">未找到匹配项</div>
            </template>

            <!-- 正常模式 -->
            <template v-else>
              <!-- 已固定区域 -->
              <div class="launcher-section-header">
                <span>已固定</span>
                <button
                  class="launcher-all-apps-btn"
                  type="button"
                  @click="showAllApps = !showAllApps"
                >
                  {{ showAllApps ? '← 返回' : '全部应用 >' }}
                </button>
              </div>

              <!-- 全部应用列表视图 -->
              <div v-if="showAllApps" class="launcher-all-apps-list">
                <button
                  v-for="app in props.appList"
                  :key="app.appKey"
                  class="launcher-all-apps-item"
                  type="button"
                  @click="emit('openApp', app.appKey)"
                >
                  <AppIcon :icon="app.icon" :size="28" />
                  <span class="launcher-all-apps-item-name">{{ app.appName }}</span>
                  <span class="launcher-all-apps-item-desc">{{ app.description }}</span>
                </button>
              </div>

              <!-- 固定应用网格 -->
              <div v-else class="launcher-pinned-grid">
                <div
                  v-for="app in pinnedApps"
                  :key="app.appKey"
                  class="launcher-pinned-item"
                  @click="emit('openApp', app.appKey)"
                >
                  <AppIcon :icon="app.icon" :size="48" />
                  <span class="launcher-pinned-label">{{ app.appName }}</span>
                </div>
              </div>

              <!-- 分隔线 -->
              <div class="launcher-divider" />

              <!-- 推荐/最近打开 -->
              <div class="launcher-section-header">
                <span>推荐</span>
                <span class="launcher-section-sub">最近打开</span>
              </div>
              <div class="launcher-recent-list">
                <template v-if="recentFiles && recentFiles.length">
                  <div
                    v-for="file in recentFiles"
                    :key="file.id"
                    class="launcher-recent-item"
                  >
                    <span class="launcher-recent-icon">{{ file.icon }}</span>
                    <span class="launcher-recent-name">{{ file.name }}</span>
                    <span class="launcher-recent-time">{{ file.time }}</span>
                  </div>
                </template>
                <div v-else class="launcher-empty">暂无最近项目</div>
              </div>
            </template>

            <!-- 底部栏 -->
            <div class="launcher-footer">
              <div class="launcher-footer-user launcher-footer-user-clickable" @click="openProfile" title="查看个人资料">
                <span class="launcher-footer-avatar">👤</span>
                <span class="launcher-footer-username">{{ username }}</span>
                <span class="launcher-footer-role">{{ userRole }}</span>
              </div>
              <div class="launcher-footer-actions">
                <button
                  class="launcher-footer-btn"
                  type="button"
                  title="刷新桌面"
                  @click="emit('executeCommand', 'refresh-desktop')"
                >⚡ 刷新</button>
                <button
                  class="launcher-footer-btn launcher-footer-btn-logout"
                  type="button"
                  title="退出登录"
                  @click="emit('executeCommand', 'logout')"
                >🚪 退出</button>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { AppRegistryEntry } from '@/desktop/window-manager/window-types'
import { useUserStore } from '@/platform/stores/user'
import { useDesktopConfig } from '@/desktop/config/desktop-preferences'
import AppIcon from '@/desktop/components/app-icon.vue'
import { commandRegistry, type SearchResultItem } from '@/desktop/app-registry/command-registry'

const props = defineProps<{
  show: boolean
  appList: AppRegistryEntry[]
  recentFiles?: Array<{ id: number; name: string; icon: string; time: string }>
}>()

const emit = defineEmits<{
  (e: 'openApp', appKey: string): void
  (e: 'executeCommand', command: string): void
  (e: 'close'): void
}>()

const { config } = useDesktopConfig()
const panelWidth = computed(() => config.launcherWidth || 520)

const searchText = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)
const showAllApps = ref(false)

const query = computed(() => searchText.value.trim())
const isSearching = computed(() => query.value.length > 0)
const searchResults = computed(() => commandRegistry.search(query.value).slice(0, 15))

const pinnedApps = computed(() => props.appList.slice(0, 10))

const userStore = useUserStore()
const username = computed(() =>
  userStore.userInfo?.display_name || userStore.userInfo?.displayName || userStore.userInfo?.username || '用户'
)
const userRole = computed(() => {
  const role = userStore.userInfo?.role || ''
  const map: Record<string, string> = { admin: '管理员', editor: '编辑', viewer: '访客' }
  return map[role.toLowerCase()] || role || ''
})

function openProfile(): void {
  emit('openApp', 'user-profile')
  emit('close')
}

// 打开时聚焦搜索框、重置状态
watch(() => props.show, (val) => {
  if (val) {
    searchText.value = ''
    showAllApps.value = false
    nextTick(() => searchInputRef.value?.focus())
  }
})

function handleEscape(): void {
  if (searchText.value) {
    searchText.value = ''
  } else {
    emit('close')
  }
}

function fallbackIcon(type: SearchResultItem['type']): string {
  if (type === 'app') return 'Grid'
  if (type === 'action') return 'Operation'
  if (type === 'background-capability') return 'Connection'
  if (type === 'file') return 'Document'
  return 'Search'
}

function resultKindLabel(type: SearchResultItem['type']): string {
  if (type === 'app') return '应用'
  if (type === 'file') return '文件'
  if (type === 'background-capability') return '后台能力'
  return '命令'
}

function executeSearchResult(item: SearchResultItem): void {
  void item.execute()
  emit('close')
}
</script>

<style scoped>
/* ═══ 遮罩层 ═══ */
.launcher-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  display: flex;
  align-items: flex-end;
  justify-content: flex-start;
  padding-bottom: 52px; /* 任务栏高度 + 8px 间隔 */
  padding-left: 8px;
  background: transparent;
}

/* ═══ 面板主体 ═══ */
.launcher-panel {
  max-height: min(600px, 70vh);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  background: rgba(24, 24, 28, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  padding: 16px;
}

/* ═══ 搜索栏 ═══ */
.launcher-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 14px;
}
.launcher-search-icon { font-size: 14px; flex-shrink: 0; }
.launcher-search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: #f1f5f9;
  font-size: 13px;
  outline: none;
  line-height: 1.5;
}
.launcher-search-input::placeholder { color: rgba(148, 163, 184, 0.6); }

/* ═══ 区域标题 ═══ */
.launcher-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 2px 10px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  font-weight: 500;
}
.launcher-section-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}
.launcher-all-apps-btn {
  border: none;
  background: transparent;
  color: rgba(147, 197, 253, 0.85);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.launcher-all-apps-btn:hover { background: rgba(255, 255, 255, 0.06); }

/* ═══ 固定应用网格（5列） ═══ */
.launcher-pinned-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  padding: 4px 0;
}
.launcher-pinned-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.launcher-pinned-item:hover { background: rgba(255, 255, 255, 0.08); }
.launcher-pinned-label {
  font-size: 11px;
  color: #e2e8f0;
  text-align: center;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ═══ 全部应用列表 ═══ */
.launcher-all-apps-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 340px;
}
.launcher-all-apps-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: #e2e8f0;
  text-align: left;
}
.launcher-all-apps-item:hover { background: rgba(255, 255, 255, 0.08); }
.launcher-all-apps-item-name { font-size: 13px; font-weight: 500; }
.launcher-all-apps-item-desc { font-size: 11px; color: rgba(148, 163, 184, 0.7); margin-left: auto; }

/* ═══ 分隔线 ═══ */
.launcher-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 12px 0;
}

/* ═══ 最近打开列表 ═══ */
.launcher-recent-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 140px;
  overflow-y: auto;
}
.launcher-recent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: default;
}
.launcher-recent-item:hover { background: rgba(255, 255, 255, 0.04); }
.launcher-recent-icon { font-size: 16px; flex-shrink: 0; }
.launcher-recent-name { font-size: 12px; color: #e2e8f0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.launcher-recent-time { font-size: 11px; color: rgba(148, 163, 184, 0.6); flex-shrink: 0; }

/* ═══ 搜索结果 ═══ */
.launcher-search-results {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 420px;
  overflow-y: auto;
}
.launcher-search-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: #e2e8f0;
  text-align: left;
}
.launcher-search-item:hover { background: rgba(255, 255, 255, 0.08); }
.launcher-search-item-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.launcher-search-item-row { display: flex; align-items: center; gap: 8px; }
.launcher-search-item-title { font-size: 13px; color: #f8fafc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.launcher-search-item-badge {
  flex-shrink: 0;
  font-size: 10px;
  line-height: 16px;
  padding: 0 6px;
  border-radius: 3px;
  background: rgba(148, 163, 184, 0.15);
  color: rgba(226, 232, 240, 0.7);
}
.launcher-search-item-desc { font-size: 11px; color: rgba(226, 232, 240, 0.55); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.launcher-empty { color: rgba(226, 232, 240, 0.5); font-size: 12px; padding: 20px 8px; text-align: center; }

/* ═══ 底部栏 ═══ */
.launcher-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.launcher-footer-user { display: flex; align-items: center; gap: 8px; }
.launcher-footer-user-clickable { cursor: pointer; padding: 4px 8px; border-radius: 8px; margin: -4px -8px; transition: background 0.15s; }
.launcher-footer-user-clickable:hover { background: rgba(255, 255, 255, 0.08); }
.launcher-footer-avatar { font-size: 18px; }
.launcher-footer-username { font-size: 12px; color: #cbd5e1; font-weight: 500; }
.launcher-footer-role { font-size: 10px; color: rgba(148, 163, 184, 0.7); background: rgba(148, 163, 184, 0.12); padding: 1px 6px; border-radius: 4px; }
.launcher-footer-actions { display: flex; gap: 4px; }
.launcher-footer-btn {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  padding: 5px 8px;
  border-radius: 4px;
  transition: background 0.15s, color 0.15s;
}
.launcher-footer-btn:hover { background: rgba(255, 255, 255, 0.08); color: #e2e8f0; }
.launcher-footer-btn-logout:hover { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }

/* ═══ 进出场动画 ═══ */
.launcher-fade-enter-active { transition: opacity 0.2s ease; }
.launcher-fade-leave-active { transition: opacity 0.15s ease; }
.launcher-fade-enter-from,
.launcher-fade-leave-to { opacity: 0; }

.launcher-slide-enter-active { transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease; }
.launcher-slide-leave-active { transition: transform 0.18s ease-in, opacity 0.15s ease; }
.launcher-slide-enter-from { transform: translateY(20px); opacity: 0; }
.launcher-slide-leave-to { transform: translateY(12px); opacity: 0; }
</style>
