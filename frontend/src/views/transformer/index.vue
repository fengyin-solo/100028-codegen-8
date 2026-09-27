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

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <form class="locate-bar" @submit.prevent="runLocate">
      <label class="filter-item">
        <span>定位方式</span>
        <select v-model="locateForm.field">
          <option v-for="option in locateFields" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>定位值</span>
        <input v-model.trim="locateForm.value" :placeholder="`按${locateForm.field}定位`" />
      </label>
      <label class="filter-item">
        <span>容量下限（kVA）</span>
        <input v-model.trim="locateForm.capacityMin" placeholder="选填" />
      </label>
      <label class="filter-item">
        <span>容量上限（kVA）</span>
        <input v-model.trim="locateForm.capacityMax" placeholder="选填" />
      </label>
      <button class="btn primary" type="submit">定位</button>
      <button class="btn ghost" type="button" @click="clearLocate">清除定位</button>
      <span v-if="locateTip" class="locate-tip" :class="{ error: locateFailed }">{{ locateTip }}</span>
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
          v-for="row in rows"
          :key="String(row.id)"
          :class="{ 'located-row': locatedId !== null && Number(row.id) === locatedId }"
        >
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
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
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无箱变管理数据，可先登记箱式变压器</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条箱变管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailRow" class="detail-mask" @click.self="closeDetail">
      <aside class="detail-panel">
        <header class="detail-head">
          <h3>箱式变压器详情</h3>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </header>
        <dl class="detail-list">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detailRow[column] ?? '—' }}</dd>
          </template>
          <dt>当前状态</dt>
          <dd>{{ detailRow.status ?? '—' }}</dd>
        </dl>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

type LocatePayload = {
  ok: boolean
  message: string
  target_id: number | null
  matched: number
  items: Row[]
}

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

const locateFields = ["箱变编号", "所属电站"]
const locateForm = ref({ field: locateFields[0], value: '', capacityMin: '', capacityMax: '' })
const locateTip = ref('')
const locateFailed = ref(false)
const locatedId = ref<number | null>(null)
const locateActive = ref(false)
const detailRow = ref<Row | null>(null)

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

function validateLocate(): string {
  if (!locateForm.value.value) {
    return `请填写要定位的${locateForm.value.field}`
  }
  const { capacityMin, capacityMax } = locateForm.value
  if (capacityMin && Number.isNaN(Number(capacityMin))) {
    return '容量下限需为数字'
  }
  if (capacityMax && Number.isNaN(Number(capacityMax))) {
    return '容量上限需为数字'
  }
  if (capacityMin && capacityMax && Number(capacityMin) > Number(capacityMax)) {
    return '容量下限不能大于上限'
  }
  return ''
}

function locateQuery(): string {
  const params = new URLSearchParams()
  params.set('field', locateForm.value.field)
  params.set('value', locateForm.value.value)
  if (locateForm.value.capacityMin) {
    params.set('capacity_min', locateForm.value.capacityMin)
  }
  if (locateForm.value.capacityMax) {
    params.set('capacity_max', locateForm.value.capacityMax)
  }
  return params.toString()
}

async function runLocate() {
  locateTip.value = ''
  locateFailed.value = false
  const invalid = validateLocate()
  if (invalid) {
    locateTip.value = invalid
    locateFailed.value = true
    return
  }
  try {
    const response = await request(`${ENDPOINT}/locate?${locateQuery()}`)
    const payload = (await response.json()) as LocatePayload
    if (!response.ok || !payload.ok) {
      // 条件不合法或未命中：保留当前定位条件，只在定位条内给出提示
      locateTip.value = payload.message ?? '定位失败，请调整条件后重试'
      locateFailed.value = true
      return
    }
    rows.value = payload.items ?? []
    total.value = rows.value.length
    locatedId.value = payload.target_id
    locateActive.value = true
    locateTip.value = payload.message
  } catch (error) {
    locateTip.value = error instanceof Error ? error.message : '定位请求失败'
    locateFailed.value = true
  }
}

function clearLocate() {
  locateForm.value = { field: locateFields[0], value: '', capacityMin: '', capacityMax: '' }
  locateTip.value = ''
  locateFailed.value = false
  locatedId.value = null
  locateActive.value = false
  void reload()
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('箱式变压器详情读取失败')
    }
    detailRow.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱式变压器详情读取失败'
  }
}

function closeDetail() {
  // 只关闭面板、不刷新列表：定位命中的设备保持停在首行
  detailRow.value = null
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
    if (locateActive.value) {
      await runLocate()
    } else {
      await reload()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  locatedId.value = null
  locateActive.value = false
  locateTip.value = ''
  locateFailed.value = false
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
