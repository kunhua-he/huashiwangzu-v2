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

const STORAGE_KEY = 'finder.item.tags.v1'

type TagMap = Record<string, FinderTagColor[]>

function entryKey(itemType: 'file' | 'folder', id: number) {
  return `${itemType}:${id}`
}

function readMap(): TagMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as TagMap
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeMap(map: TagMap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
}

export function getItemTags(itemType: 'file' | 'folder', id: number): FinderTagColor[] {
  const map = readMap()
  const tags = map[entryKey(itemType, id)]
  return Array.isArray(tags) ? tags : []
}

export function setItemTags(itemType: 'file' | 'folder', id: number, tags: FinderTagColor[]) {
  const map = readMap()
  const key = entryKey(itemType, id)
  const unique = Array.from(new Set(tags))
  if (!unique.length) delete map[key]
  else map[key] = unique
  writeMap(map)
}

/** Toggle one tag on/off for an item. */
export function toggleItemTag(
  itemType: 'file' | 'folder',
  id: number,
  tag: FinderTagColor,
): FinderTagColor[] {
  const current = new Set(getItemTags(itemType, id))
  if (current.has(tag)) current.delete(tag)
  else current.add(tag)
  const next = Array.from(current)
  setItemTags(itemType, id, next)
  return next
}

export function clearItemTags(itemType: 'file' | 'folder', id: number) {
  setItemTags(itemType, id, [])
}

export function getTagDef(key: FinderTagColor): FinderTagDef | undefined {
  return FINDER_TAGS.find((t) => t.key === key)
}

export function listTaggedEntryKeys(tag: FinderTagColor): string[] {
  const map = readMap()
  return Object.entries(map)
    .filter(([, tags]) => Array.isArray(tags) && tags.includes(tag))
    .map(([key]) => key)
}
