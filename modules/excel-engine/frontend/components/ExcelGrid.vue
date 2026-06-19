<template>
  <div class="excel-grid-container" ref="containerRef">
    <div class="grid-scroll" ref="scrollRef">
      <table class="excel-grid">
        <colgroup>
          <col style="width: 50px" />
          <col v-for="c in totalCols" :key="c" :style="{ width: getColWidth(c) + 'px' }" />
        </colgroup>
        <thead>
          <tr>
            <th class="row-header-corner"></th>
            <th v-for="c in totalCols" :key="c" class="col-header"
              @click="selectCol(c)" @contextmenu.prevent="onHeaderContextMenu($event, 'col', c)">
              {{ colLetter(c - 1) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in totalRows" :key="r" :style="{ height: getRowHeight(r) + 'px' }">
            <td class="row-header" @click="selectRow(r)" @contextmenu.prevent="onHeaderContextMenu($event, 'row', r)">
              {{ r }}
            </td>
            <td v-for="c in totalCols" :key="c" class="cell"
              :data-addr="`${colLetter(c - 1)}${r}`"
              v-show="!isMergedHidden(r, c)"
              :rowspan="mergeInfo(r, c)?.rowspan || 1"
              :colspan="mergeInfo(r, c)?.colspan || 1"
              :class="cellClasses(r, c)"
              @mousedown="onCellMouseDown($event, r, c)"
              @dblclick="onCellDblClick(r, c)"
              @contextmenu.prevent="onCellContextMenu($event, r, c)">
              <template v-if="isEditing && editAddr === `${colLetter(c - 1)}${r}`">
                <input ref="editInput" class="cell-editor"
                  v-model="editValue"
                  @keydown.enter="confirmEdit"
                  @keydown.tab.prevent="onTabEdit"
                  @keydown.escape="cancelEdit"
                  @blur="confirmEdit" />
              </template>
              <template v-else>
                <span class="cell-value" :style="cellTextStyle(r, c)">{{ displayValue(r, c) }}</span>
                <span v-if="isFormula(r, c)" class="formula-badge">fx</span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Formula bar -->
    <div class="formula-bar" v-if="showFormulaBar">
      <span class="formula-addr">{{ editAddr || selectedAddr }}</span>
      <input class="formula-input" id="formulaInput"
        :value="formulaValue" @input="onFormulaInput" @keydown.enter="onFormulaEnter" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { colLetter, parseCellAddr, buildMergeMap, truncateValue, decodeAsciiEscape } from './address-util'

const props = defineProps<{
  cells: Record<string, string>
  styles: Record<string, Record<string, any>>
  merges: Record<string, { topLeft: string; rows: number; cols: number }>
  colWidths: Record<string, number>
  rowHeights: Record<string, number>
  totalRows: number
  totalCols: number
  isEditing: boolean
  editAddr: string
  editValue: string
  selectedAddr: string
  selectedRange: string[]
  showFormulaBar: boolean
  formulaValue: string
}>()

const emit = defineEmits<{
  'cell-click': [addr: string]
  'cell-dblclick': [addr: string]
  'cell-contextmenu': [addr: string, event: MouseEvent]
  'header-contextmenu': [type: 'row' | 'col', index: number, event: MouseEvent]
  'select-range': [addrs: string[]]
  'confirm-edit': []
  'cancel-edit': []
  'update:editValue': [val: string]
  'update:formulaValue': [val: string]
  'formula-enter': []
  'tab-edit': [shift: boolean]
}>()

const containerRef = ref<HTMLElement>()
const scrollRef = ref<HTMLElement>()
const editInput = ref<HTMLInputElement>()

const mergeMap = computed(() => {
  const mergeRefs: string[] = []
  for (const key of Object.keys(props.merges)) {
    mergeRefs.push(key)
  }
  return buildMergeMap(mergeRefs)
})

function isMergedHidden(r: number, c: number): boolean {
  const info = mergeMap.value.get(`${r - 1}:${c - 1}`)
  return !!info && !info.isMain
}

function mergeInfo(r: number, c: number) {
  return mergeMap.value.get(`${r - 1}:${c - 1}`)
}

function getColWidth(c: number): number {
  const letter = colLetter(c - 1)
  return props.colWidths[letter] || 80
}

function getRowHeight(r: number): number {
  return props.rowHeights[String(r)] || 24
}

function displayValue(r: number, c: number): string {
  const addr = `${colLetter(c - 1)}${r}`
  const val = props.cells[addr]
  if (!val) return ''
  return truncateValue(decodeAsciiEscape(val))
}

function cellTextStyle(r: number, c: number): Record<string, string> {
  const addr = `${colLetter(c - 1)}${r}`
  const s = props.styles[addr]
  if (!s) return {}
  const style: Record<string, string> = {}
  if (s.bold) style.fontWeight = 'bold'
  if (s.italic) style.fontStyle = 'italic'
  if (s.underline) style.textDecoration = s.strikethrough ? 'underline line-through' : 'underline'
  else if (s.strikethrough) style.textDecoration = 'line-through'
  if (s.fontSize) style.fontSize = s.fontSize + 'pt'
  if (s.fontName) style.fontFamily = s.fontName
  if (s.color) style.color = s.color
  if (s.align) {
    const alignMap: Record<string, string> = { '左': 'left', '居中': 'center', '右': 'right' }
    style.textAlign = alignMap[s.align] || 'left'
  }
  if (s.fillColor) style.backgroundColor = s.fillColor
  if (s.wrapText) style.whiteSpace = 'pre-wrap'
  return style
}

function cellClasses(r: number, c: number): Record<string, boolean> {
  const addr = `${colLetter(c - 1)}${r}`
  const s = props.styles[addr]
  return {
    'cell-bold': s?.bold || false,
    'cell-formula': isFormula(r, c),
    'cell-selected': props.selectedRange.includes(addr),
    'cell-active': props.selectedAddr === addr,
  }
}

function isFormula(r: number, c: number): boolean {
  const addr = `${colLetter(c - 1)}${r}`
  const val = props.cells[addr]
  return typeof val === 'string' && val.startsWith('=')
}

function onCellMouseDown(e: MouseEvent, r: number, c: number) {
  const addr = `${colLetter(c - 1)}${r}`
  emit('cell-click', addr)
}

function onCellDblClick(r: number, c: number) {
  const addr = `${colLetter(c - 1)}${r}`
  emit('cell-dblclick', addr)
}

function onCellContextMenu(e: MouseEvent, r: number, c: number) {
  const addr = `${colLetter(c - 1)}${r}`
  emit('cell-contextmenu', addr, e)
}

function onHeaderContextMenu(e: MouseEvent, type: 'row' | 'col', index: number) {
  emit('header-contextmenu', type, index, e)
}

function confirmEdit() {
  emit('confirm-edit')
}

function cancelEdit() {
  emit('cancel-edit')
}

function onTabEdit(e: KeyboardEvent) {
  emit('tab-edit', e.shiftKey)
}

function onFormulaInput(e: Event) {
  emit('update:formulaValue', (e.target as HTMLInputElement).value)
}

function onFormulaEnter() {
  emit('formula-enter')
}

function selectCol(c: number) {
  const addrs: string[] = []
  for (let r = 1; r <= props.totalRows; r++) {
    addrs.push(`${colLetter(c - 1)}${r}`)
  }
  emit('select-range', addrs)
}

function selectRow(r: number) {
  const addrs: string[] = []
  for (let c = 1; c <= props.totalCols; c++) {
    addrs.push(`${colLetter(c - 1)}${r}`)
  }
  emit('select-range', addrs)
}

watch(() => props.editAddr, () => {
  if (props.isEditing && props.editAddr) {
    nextTick(() => editInput.value?.focus())
  }
})
</script>

<style scoped>
.excel-grid-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: #fff;
}
.grid-scroll {
  flex: 1;
  overflow: auto;
  position: relative;
}
.excel-grid {
  border-collapse: collapse;
  font-size: 12px;
  min-width: 100%;
  table-layout: fixed;
}
.excel-grid th,
.excel-grid td {
  border: 1px solid #d0d5dd;
  padding: 2px 4px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.row-header-corner {
  background: #f0f2f5;
  border-bottom: 1px solid #c0c4cc !important;
}
.col-header {
  position: sticky;
  top: 0;
  background: #f0f2f5;
  font-weight: 500;
  color: #666;
  text-align: center;
  font-size: 11px;
  cursor: pointer;
  z-index: 2;
  user-select: none;
  min-width: 60px;
}
.col-header:hover {
  background: #e4e7ed;
}
.row-header {
  position: sticky;
  left: 0;
  background: #f0f2f5;
  font-weight: 500;
  color: #666;
  text-align: center;
  font-size: 11px;
  cursor: pointer;
  user-select: none;
  z-index: 1;
  min-width: 50px;
}
.row-header:hover {
  background: #e4e7ed;
}
.cell {
  position: relative;
  cursor: cell;
  min-width: 60px;
  height: 24px;
}
.cell:hover {
  outline: 1px solid #409eff;
  outline-offset: -1px;
}
.cell-active {
  outline: 2px solid #409eff !important;
  outline-offset: -2px;
}
.cell-selected {
  background: #e6f7ff;
}
.cell-bold {
  font-weight: 700;
}
.cell-formula {
  background: #fffbe6;
}
.cell-value {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}
.formula-badge {
  position: absolute;
  top: 0;
  right: 0;
  font-size: 8px;
  color: #faad14;
  background: #fff7e6;
  padding: 0 2px;
  border-radius: 0 0 0 2px;
  line-height: 12px;
}
.cell-editor {
  width: 100%;
  box-sizing: border-box;
  border: 2px solid #409eff;
  outline: none;
  font-size: 12px;
  padding: 1px 2px;
  background: #fff;
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  z-index: 3;
}
.formula-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border-top: 1px solid #d0d5dd;
  background: #fafafa;
}
.formula-addr {
  font-size: 11px;
  font-weight: 500;
  color: #409eff;
  min-width: 50px;
  text-align: center;
}
.formula-input {
  flex: 1;
  border: 1px solid #c0c4cc;
  border-radius: 3px;
  padding: 3px 6px;
  font-size: 12px;
  outline: none;
}
.formula-input:focus {
  border-color: #409eff;
}
</style>
