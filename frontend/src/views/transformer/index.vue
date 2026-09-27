<template>
  <section class="page" data-module="transformer">
    <header class="page-head">
      <div>
        <h2>箱变管理管理</h2>
        <p class="page-desc">维护箱式变压器，围绕箱变编号、箱变型号、额定容量、所属电站做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记箱式变压器</button>
        <button class="btn" type="button" @click="exportRows">导出箱变管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="locate-bar">
      <div class="locate-controls">
        <label class="filter-item">
          <span>箱变编号</span>
          <input v-model="locateCode" placeholder="如 TRAN-0001" />
        </label>
        <label class="filter-item">
          <span>所属电站</span>
          <input v-model="locatePlant" placeholder="如 沙坡头" />
        </label>
        <label class="filter-item">
          <span>容量下限(kVA)</span>
          <input v-model="capacityMin" placeholder="可留空" />
        </label>
        <label class="filter-item">
          <span>容量上限(kVA)</span>
          <input v-model="capacityMax" placeholder="可留空" />
        </label>
        <button class="btn primary" type="button" @click="locate">定位</button>
        <button class="btn ghost" type="button" @click="clearLocate">清除定位</button>
      </div>
      <p v-if="locateMessage" class="locate-message" :class="locateMessageKind">{{ locateMessage }}</p>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in displayRows"
          :key="String(row.id)"
          :class="{ 'located-row': row.id === locatedId }"
        >
          <td v-for="column in columns" :key="column">
            <template v-if="column === '箱变编号'">
              {{ row[column] ?? '—' }}
              <span v-if="row.id === locatedId" class="tag located">已定位</span>
            </template>
            <template v-else-if="column === '额定容量'">
              {{ row[column] ?? '—' }}
              <span v-if="capacityRange && inCapacityRange(row)" class="tag in-range">区间内</span>
              <span v-else-if="capacityRange" class="tag out-range">区间外</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!displayRows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无箱变管理数据，可先登记箱式变压器</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条箱变管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailOpen" class="detail-mask" @click.self="closeDetail">
      <div class="detail-dialog">
        <header class="detail-head">
          <h3>箱式变压器详情</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <p v-if="detailLoading" class="detail-tip">详情读取中…</p>
        <p v-else-if="detailError" class="error-text">{{ detailError }}</p>
        <dl v-else-if="detail" class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/transformer'
const columns = ["箱变编号", "箱变型号", "额定容量", "所属电站", "油温", "绕组温度", "上次检修日", "箱变状态"]
const actions = ["停机检修", "复归信号", "恢复供电"]
const statuses = ["运行", "轻瓦斯", "重瓦斯", "停机"]
const stats = [{"label": "运行箱变", "value": 0}, {"label": "告警箱变", "value": 0}, {"label": "停机箱变", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

// 定位条：按箱变编号或所属电站把目标设备提到首行，容量区间只负责标注匹配情况
const locateCode = ref('')
const locatePlant = ref('')
const capacityMin = ref('')
const capacityMax = ref('')
const locatedId = ref<number | null>(null)
const capacityRange = ref<{ min: number | null; max: number | null } | null>(null)
const locateMessage = ref('')
const locateMessageKind = ref<'error' | 'info'>('info')

// 详情弹窗：只读展示，关闭时不动列表顺序，定位结果保持
const detailOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detail = ref<Row | null>(null)

const displayRows = computed<Row[]>(() => {
  if (locatedId.value === null) {
    return rows.value
  }
  const target = rows.value.find((row) => row.id === locatedId.value)
  if (!target) {
    return rows.value
  }
  return [target, ...rows.value.filter((row) => row.id !== locatedId.value)]
})

function parseCapacity(value: Row[string]): number | null {
  const match = String(value ?? '').match(/\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function inCapacityRange(row: Row): boolean {
  if (!capacityRange.value) {
    return false
  }
  const capacity = parseCapacity(row['额定容量'])
  if (capacity === null) {
    return false
  }
  const { min, max } = capacityRange.value
  if (min !== null && capacity < min) {
    return false
  }
  if (max !== null && capacity > max) {
    return false
  }
  return true
}

function readCapacityBound(raw: string, label: string): number | null {
  const text = raw.trim()
  if (!text) {
    return null
  }
  const value = Number(text)
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${label}需为不小于 0 的数字`)
  }
  return value
}

function locate() {
  locateMessage.value = ''
  const code = locateCode.value.trim()
  const plant = locatePlant.value.trim()
  let min: number | null
  let max: number | null
  try {
    min = readCapacityBound(capacityMin.value, '容量下限')
    max = readCapacityBound(capacityMax.value, '容量上限')
  } catch (error) {
    locateMessageKind.value = 'error'
    locateMessage.value = error instanceof Error ? error.message : '容量区间填写不合法'
    return
  }
  if (min !== null && max !== null && min > max) {
    locateMessageKind.value = 'error'
    locateMessage.value = '容量下限不能大于容量上限'
    return
  }
  if (!code && !plant && min === null && max === null) {
    locateMessageKind.value = 'error'
    locateMessage.value = '请填写箱变编号、所属电站或容量区间后再定位'
    return
  }

  capacityRange.value = min === null && max === null ? null : { min, max }

  let target: Row | undefined
  if (code || plant) {
    target = rows.value.find((row) => {
      const codeHit = !code || String(row['箱变编号'] ?? '').toLowerCase() === code.toLowerCase()
      const plantHit = !plant || String(row['所属电站'] ?? '').includes(plant)
      return codeHit && plantHit
    })
  }

  if (code || plant) {
    if (!target) {
      // 没有命中：保留当前定位条件与已定位设备，只给行内提示
      locateMessageKind.value = 'error'
      locateMessage.value = '没有命中的箱变，已保留当前定位条件'
      return
    }
    locatedId.value = Number(target.id)
    const matched = capacityRange.value
      ? rows.value.filter((row) => inCapacityRange(row)).length
      : null
    locateMessageKind.value = 'info'
    locateMessage.value = matched === null
      ? `已定位到 ${target['箱变编号']}（${target['所属电站'] ?? '—'}）`
      : `已定位到 ${target['箱变编号']}（${target['所属电站'] ?? '—'}），容量区间内共 ${matched} 台`
    return
  }

  // 只填容量区间：不动首行，仅标注匹配情况
  const matched = rows.value.filter((row) => inCapacityRange(row)).length
  locateMessageKind.value = 'info'
  locateMessage.value = `容量区间内共 ${matched} 台箱变`
}

function clearLocate() {
  locateCode.value = ''
  locatePlant.value = ''
  capacityMin.value = ''
  capacityMax.value = ''
  locatedId.value = null
  capacityRange.value = null
  locateMessage.value = ''
}

async function openDetail(row: Row) {
  detailOpen.value = true
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('箱式变压器详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '箱式变压器详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailOpen.value = false
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '箱式变压器登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('箱变管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('箱式变压器列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.locate-bar {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.locate-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
}
.locate-controls input {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.locate-message {
  margin: 8px 0 0;
  font-size: 12px;
}
.locate-message.info {
  color: var(--brand);
}
.locate-message.error {
  color: #b42318;
}
.located-row {
  background: #eaf2ff;
}
.tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.tag.located {
  background: var(--brand);
  color: #fff;
}
.tag.in-range {
  background: #e7f6ec;
  color: #067647;
}
.tag.out-range {
  background: #f2f4f7;
  color: var(--muted);
}
.detail-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.detail-dialog {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 520px;
  max-width: 90vw;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-head h3 {
  margin: 0;
  font-size: 15px;
}
.detail-tip {
  color: var(--muted);
  font-size: 13px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 12px 0 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
</style>
