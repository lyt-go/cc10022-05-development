<template>
  <section class="page" data-testid="cleansing-trial">
    <header class="page-head">
      <div>
        <h2>参考别名清洗试算</h2>
        <p class="page-desc">
          按实际地址记录对比两套别名解释，展示原始地址转换前后的旧码与拟改新码差异；
          试算只读，生效参考数据与正式清洗记录保持原样。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" data-testid="check-effective" @click="checkEffective">
          核对生效字段
        </button>
        <button class="btn primary" type="button" data-testid="run-trial" :disabled="loading" @click="runTrial">
          {{ loading ? '试算中…' : '生成试算' }}
        </button>
      </div>
    </header>

    <form class="filter-bar" @submit.prevent="runTrial">
      <label class="filter-item">
        <span>试算参考类别</span>
        <select v-model="category" data-testid="trial-category">
          <option v-for="item in categories" :key="item.数据类别" :value="item.数据类别">
            {{ item.数据类别 }}（{{ item.更正条数 }} 条别名更正）
          </option>
        </select>
      </label>
      <button class="btn" type="submit">开始试算</button>
    </form>

    <p v-if="notice" class="page-desc" data-testid="trial-notice">{{ notice }}</p>
    <p v-if="errorMessage" class="error-text" data-testid="trial-error">{{ errorMessage }}</p>

    <template v-if="preview">
      <div class="stat-row" data-testid="trial-summary">
        <article class="stat-card">
          <span class="stat-label">地址记录总数</span>
          <strong class="stat-value">{{ preview.汇总.地址记录总数 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">已回源 / 待回源</span>
          <strong class="stat-value">
            {{ preview.汇总.已回源记录数 }} / {{ preview.汇总.待回源记录数 }}
          </strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">存在差异记录</span>
          <strong class="stat-value">{{ preview.汇总.存在差异记录数 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">受影响区域（含待回源）</span>
          <strong class="stat-value">{{ preview.汇总.受影响区域数 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">待回源区域</span>
          <strong class="stat-value">{{ preview.汇总.待回源区域数 }}</strong>
        </article>
      </div>
      <p class="page-desc">只读说明：{{ preview.只读说明 }}；试算时间 {{ preview.试算时间 }}</p>

      <h3 class="section-title">受影响区域及站点映射</h3>
      <table class="data-table" data-testid="region-table">
        <thead>
          <tr>
            <th>区域</th><th>参考类别</th><th>地址记录数</th><th>已回源</th><th>待回源</th>
            <th>差异记录数</th><th>影响状态</th><th>涉及旧码</th><th>涉及新码</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in preview.区域汇总" :key="row.区域" :data-impact="row.影响状态">
            <td>{{ row.区域 }}</td>
            <td>{{ row.参考类别 }}</td>
            <td>{{ row.地址记录数 }}</td>
            <td>{{ row.已回源数 }}</td>
            <td :class="{ 'warn-cell': row.待回源数 > 0 }">{{ row.待回源数 }}</td>
            <td>{{ row.差异记录数 }}</td>
            <td>
              <span :class="impactClass(row.影响状态)">{{ row.影响状态 }}</span>
            </td>
            <td>{{ row.涉及旧码.join('、') || '—' }}</td>
            <td>{{ row.涉及新码.join('、') || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <h3 class="section-title">站点映射（旧码 → 拟改新码）</h3>
      <table class="data-table" data-testid="site-mapping-table">
        <thead>
          <tr>
            <th>参考类别</th><th>旧码</th><th>旧码名称</th><th>新码</th><th>新码名称</th>
            <th>覆盖区域</th><th>记录数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in preview.站点映射" :key="`${row.旧码}-${row.新码}`">
            <td>{{ row.参考类别 }}</td>
            <td class="old-code">{{ row.旧码 || '（空）' }}</td>
            <td>{{ row.旧码名称 || '—' }}</td>
            <td class="new-code">{{ row.新码 || '（空）' }}</td>
            <td>{{ row.新码名称 || '—' }}</td>
            <td>{{ row.覆盖区域.join('、') }}</td>
            <td>{{ row.记录数 }}</td>
          </tr>
          <tr v-if="!preview.站点映射.length">
            <td colspan="7" class="empty-state">当前试算范围没有别名清洗差异</td>
          </tr>
        </tbody>
      </table>

      <h3 class="section-title">别名清洗差异明细（重洗预览）</h3>
      <table class="data-table" data-testid="diff-table">
        <thead>
          <tr>
            <th>地址编号</th><th>区域</th><th>原始地址（转换前）</th><th>参考类别</th>
            <th>旧码</th><th>拟改新码</th><th>命中别名</th><th>别名来源</th>
            <th>正式清洗旧码</th><th>差异类型</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in diffRows" :key="row.地址编号" :data-diff="row.差异类型">
            <td>{{ row.地址编号 }}</td>
            <td>{{ row.区域 }}</td>
            <td>{{ row.原始地址 || '（原始输入缺失，待回源）' }}</td>
            <td>{{ row.参考类别 }}</td>
            <td class="old-code">{{ row.旧码 || '—' }}</td>
            <td class="new-code">{{ row.新码 || '—' }}</td>
            <td>{{ row.命中别名 || '—' }}</td>
            <td>{{ row.别名来源 || '—' }}</td>
            <td>{{ row.正式清洗旧码 || '—' }}</td>
            <td><span :class="diffClass(row.差异类型)">{{ row.差异类型 }}</span></td>
          </tr>
        </tbody>
      </table>
      <p class="page-desc">
        <button class="link" type="button" @click="showAll = !showAll">
          {{ showAll ? '仅看差异记录' : `查看全部 ${preview.全量记录评估.length} 条记录评估` }}
        </button>
      </p>

      <h3 class="section-title">试算别名更正（第二套别名解释）</h3>
      <table class="data-table" data-testid="override-table">
        <thead>
          <tr><th>更正编号</th><th>标准编码</th><th>标准名称</th><th>更正别名</th><th>别名解释</th><th>更新时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in overrides" :key="row.更正编号">
            <td>{{ row.更正编号 }}</td>
            <td>{{ row.标准编码 }}</td>
            <td>{{ row.标准名称 }}</td>
            <td class="new-code">{{ row.更正别名 }}</td>
            <td>{{ row.别名解释 }}</td>
            <td>{{ row.更新时间 }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <div class="backfill-panel" data-testid="backfill-panel">
      <h3 class="section-title">原始地址回源补录</h3>
      <p class="page-desc">
        历史输入尚未找到的地区可在此补登原始地址；补录只写原始记录表，
        不改动生效参考数据与正式清洗旧码，补录后重新生成试算即可看到视图变化。
      </p>
      <form class="filter-bar" @submit.prevent="submitBackfill">
        <label class="filter-item">
          <span>地址编号（留空自动生成）</span>
          <input v-model="backfill.地址编号" data-testid="backfill-id" placeholder="如 ADDR-006" />
        </label>
        <label class="filter-item">
          <span>区域</span>
          <input v-model="backfill.区域" data-testid="backfill-region" placeholder="如 南城区" required />
        </label>
        <label class="filter-item filter-wide">
          <span>原始地址</span>
          <input v-model="backfill.原始地址" data-testid="backfill-address" placeholder="补录回源的历史原始地址" required />
        </label>
        <button class="btn primary" type="submit" data-testid="backfill-submit" :disabled="submitting">
          {{ submitting ? '补录中…' : '回源补录并重试' }}
        </button>
      </form>
    </div>

    <div v-if="snapshot" class="backfill-panel" data-testid="effective-panel">
      <h3 class="section-title">生效字段核对（试算未改动）</h3>
      <table class="data-table">
        <thead>
          <tr><th>地址编号</th><th>正式清洗旧码（当前生效）</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in snapshot.正式清洗旧码" :key="row.地址编号">
            <td>{{ row.地址编号 }}</td>
            <td>{{ row.当前旧码 || '（空）' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="page-desc">
        生效参考数据别名：
        <span v-for="ref in snapshot.生效参考数据" :key="ref.标准编码" class="ref-chip">
          {{ ref.标准名称 }}（{{ ref.标准编码 }}）：{{ ref.别名列表 }}
        </span>
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  fetchAliasOverrides,
  fetchEffectiveSnapshot,
  fetchTrialCategories,
  fetchTrialPreview,
  registerAddressSource,
} from '@/api/trial'
import type { AliasOverride, TrialCategory, TrialPreview } from '@/api/trial'

const categories = ref<TrialCategory[]>([])
const category = ref('站点编码')
const overrides = ref<AliasOverride[]>([])
const preview = ref<TrialPreview | null>(null)
const snapshot = ref<Awaited<ReturnType<typeof fetchEffectiveSnapshot>> | null>(null)
const loading = ref(false)
const submitting = ref(false)
const showAll = ref(false)
const notice = ref('')
const errorMessage = ref('')
const backfill = ref({ 地址编号: '', 区域: '南城区', 原始地址: '' })

const diffRows = computed(() =>
  showAll.value && preview.value ? preview.value.全量记录评估 : preview.value?.差异明细 ?? [],
)

function impactClass(status: string): string {
  if (status === '无影响') return 'tag tag-muted'
  if (status.includes('待回源')) return 'tag tag-warn'
  return 'tag tag-diff'
}

function diffClass(type: string): string {
  if (type === '待回源确认') return 'tag tag-warn'
  if (type === '无差异') return 'tag tag-muted'
  return 'tag tag-diff'
}

async function loadOverrides() {
  if (!category.value) return
  try {
    overrides.value = await fetchAliasOverrides(category.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '别名更正读取失败'
  }
}

async function runTrial() {
  if (!category.value) {
    errorMessage.value = '请先选择试算参考类别'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    preview.value = await fetchTrialPreview(category.value)
    await loadOverrides()
    notice.value = `试算完成：${preview.value.汇总.存在差异记录数} 条差异，${preview.value.汇总.受影响区域数} 个受影响区域`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '试算失败'
  } finally {
    loading.value = false
  }
}

async function checkEffective() {
  errorMessage.value = ''
  try {
    snapshot.value = await fetchEffectiveSnapshot(category.value)
    notice.value = '已核对：试算期间生效参考数据与正式清洗旧码保持原样'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生效字段核对失败'
  }
}

async function submitBackfill() {
  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await registerAddressSource({
      地址编号: backfill.value.地址编号 || undefined,
      区域: backfill.value.区域,
      原始地址: backfill.value.原始地址,
    })
    if (!result.ok) throw new Error(result.message)
    notice.value = result.message
    backfill.value.地址编号 = ''
    backfill.value.原始地址 = ''
    await runTrial()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回源补录失败'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    categories.value = await fetchTrialCategories()
    if (!categories.value.some((item) => item.数据类别 === category.value) && categories.value[0]) {
      category.value = categories.value[0].数据类别
    }
    await loadOverrides()
    await runTrial()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '试算视图初始化失败'
  }
})
</script>

<style scoped>
.section-title { font-size: 15px; margin: 18px 0 8px; }
.warn-cell { color: #b54708; font-weight: 600; }
.old-code { color: #b42318; }
.new-code { color: #15803d; font-weight: 600; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.tag-diff { background: #fee4e2; color: #b42318; }
.tag-warn { background: #fef0c7; color: #b54708; }
.tag-muted { background: #e2e8f0; color: #475569; }
.backfill-panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-top: 16px; }
.filter-wide { flex: 1; min-width: 260px; }
.filter-wide input { width: 100%; }
.ref-chip { display: inline-block; margin-right: 8px; padding: 2px 8px; background: #f1f5f9; border-radius: 10px; font-size: 12px; }
</style>
