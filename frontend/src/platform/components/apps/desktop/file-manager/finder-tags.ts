import {
  clearFileItemTagsRequest,
  fetchFileTagsMap,
  setFileItemTagsRequest,
  toggleFileItemTagRequest,
} from '@/shared/api/desktop'

export type FinderTagColor =
  | 'red'
  | 'orange'
  | 'yellow'
  | 'green'
  | 'blue'
  | 'purple'
  | 'gray'

export interface FinderTagDef {
  key: FinderTagColor
  name: string
  color: string
}

export const FINDER_TAGS: FinderTagDef[] = [
  { key: 'red', name: '红色', color: 'rgb(255, 69, 58)' },
  { key: 'orange', name: '橙色', color: 'rgb(255, 159, 10)' },
  { key: 'yellow', name: '黄色', color: 'rgb(255, 214, 10)' },
  { key: 'green', name: '绿色', color: 'rgb(48, 209, 88)' },
  { key: 'blue', name: '蓝色', color: 'rgb(10, 132, 255)' },
  { key: 'purple', name: '紫色', color: 'rgb(191, 90, 242)' },
  { key: 'gray', name: '灰色', color: 'rgb(152, 152, 157)' },
]

/** User-custom display names for the 7 system colors (prefs, no schema change). */
const CUSTOM_LABEL_KEY = 'finder.tag.labels.v1'
let customLabels: Partial<Record<FinderTagColor, string>> = {}

export function loadCustomTagLabels(): Partial<Record<FinderTagColor, string>> {
  try {
    const raw = localStorage.getItem(CUSTOM_LABEL_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, string>
    const out: Partial<Record<FinderTagColor, string>> = {}
    for (const t of FINDER_TAGS) {
      const name = parsed[t.key]
      if (typeof name === 'string' && name.trim()) out[t.key] = name.trim().slice(0, 16)
    }
    customLabels = out
    return out
  } catch {
    return {}
  }
}

export function saveCustomTagLabels(labels: Partial<Record<FinderTagColor, string>>) {
  customLabels = { ...labels }
  localStorage.setItem(CUSTOM_LABEL_KEY, JSON.stringify(customLabels))
}

export function getTagDisplayName(key: FinderTagColor): string {
  if (!Object.keys(customLabels).length) loadCustomTagLabels()
  return customLabels[key] || FINDER_TAGS.find((t) => t.key === key)?.name || key
}

export function listTagsWithCustomNames(): FinderTagDef[] {
  if (!Object.keys(customLabels).length) loadCustomTagLabels()
  return FINDER_TAGS.map((t) => ({
    ...t,
    name: customLabels[t.key] || t.name,
  }))
}

/** In-memory cache mirrored from backend (per user session). */
let tagMap: Record<string, FinderTagColor[]> = {}
let loaded = false
let loading: Promise<void> | null = null

function entryKey(itemType: 'file' | 'folder', id: number) {
  return `${itemType}:${id}`
}

function normalizeTags(tags: unknown): FinderTagColor[] {
  if (!Array.isArray(tags)) return []
  const allowed = new Set(FINDER_TAGS.map((t) => t.key))
  const out: FinderTagColor[] = []
  for (const raw of tags) {
    const key = String(raw || '').toLowerCase() as FinderTagColor
    if (allowed.has(key) && !out.includes(key)) out.push(key)
  }
  return out
}

export async function loadFinderTagsFromServer(): Promise<void> {
  if (loading) return loading
  loading = (async () => {
    try {
      const data = await fetchFileTagsMap()
      const next: Record<string, FinderTagColor[]> = {}
      if (data && typeof data === 'object') {
        for (const [key, tags] of Object.entries(data)) {
          next[key] = normalizeTags(tags)
        }
      }
      tagMap = next
      loaded = true
    } catch {
      // keep existing cache on failure
      loaded = true
    } finally {
      loading = null
    }
  })()
  return loading
}

export function isFinderTagsLoaded() {
  return loaded
}

export function getItemTags(itemType: 'file' | 'folder', id: number): FinderTagColor[] {
  return tagMap[entryKey(itemType, id)] || []
}

export async function setItemTags(
  itemType: 'file' | 'folder',
  id: number,
  tags: FinderTagColor[],
): Promise<FinderTagColor[]> {
  const unique = Array.from(new Set(tags))
  const saved = normalizeTags(await setFileItemTagsRequest(itemType, id, unique))
  const key = entryKey(itemType, id)
  if (!saved.length) delete tagMap[key]
  else tagMap[key] = saved
  return saved
}

/** Toggle one tag on/off for an item (server-backed). */
export async function toggleItemTag(
  itemType: 'file' | 'folder',
  id: number,
  tag: FinderTagColor,
): Promise<FinderTagColor[]> {
  const saved = normalizeTags(await toggleFileItemTagRequest(itemType, id, tag))
  const key = entryKey(itemType, id)
  if (!saved.length) delete tagMap[key]
  else tagMap[key] = saved
  return saved
}

export async function clearItemTags(itemType: 'file' | 'folder', id: number): Promise<void> {
  await clearFileItemTagsRequest(itemType, id)
  delete tagMap[entryKey(itemType, id)]
}

export function getTagDef(key: FinderTagColor): FinderTagDef | undefined {
  return FINDER_TAGS.find((t) => t.key === key)
}

export function listTaggedEntryKeys(tag: FinderTagColor): string[] {
  return Object.entries(tagMap)
    .filter(([, tags]) => Array.isArray(tags) && tags.includes(tag))
    .map(([key]) => key)
}
