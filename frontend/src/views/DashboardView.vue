<script setup lang="ts">
import {
  NButton,
  NCard,
  NDatePicker,
  NEmpty,
  NGi,
  NGrid,
  NRadioButton,
  NRadioGroup,
  NSkeleton,
  NSpace,
  NTag,
  useMessage,
} from 'naive-ui'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { computed, onMounted, ref, watch } from 'vue'
import { statsApi, transactionsApi } from '@/api'
import { messageOf } from '@/api/client'
import BaseChart from '@/components/BaseChart.vue'
import TransactionDialog from '@/components/TransactionDialog.vue'
import type { DashboardData, Transaction } from '@/types'
import { formatMoney, formatYuan, lastNDaysRange, monthRange, toNumber } from '@/utils/format'

type Preset = 'thisMonth' | 'lastMonth' | 'last30' | 'custom'

const message = useMessage()

const loading = ref(true)
const data = ref<DashboardData | null>(null)
const recent = ref<Transaction[]>([])
const preset = ref<Preset>('thisMonth')
const customRange = ref<[number, number] | null>(null)
const dialogVisible = ref(false)

const range = computed<{ date_from: string; date_to: string }>(() => {
  if (preset.value === 'custom' && customRange.value) {
    return {
      date_from: dayjs(customRange.value[0]).format('YYYY-MM-DD'),
      date_to: dayjs(customRange.value[1]).format('YYYY-MM-DD'),
    }
  }
  const preset_range =
    preset.value === 'lastMonth'
      ? monthRange(-1)
      : preset.value === 'last30'
        ? lastNDaysRange(30)
        : monthRange(0)
  return { date_from: preset_range.from, date_to: preset_range.to }
})

const summary = computed(() => data.value?.summary)
const hasData = computed(() => (summary.value?.count ?? 0) > 0)

async function load() {
  loading.value = true
  try {
    const [dashboard, page] = await Promise.all([
      statsApi.dashboard({ ...range.value, months: 6 }),
      transactionsApi.list({ ...range.value, page_size: 6 }),
    ])
    data.value = dashboard
    recent.value = page.items
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    loading.value = false
  }
}

watch(range, load)
onMounted(load)

const dailyFocus = ref<'all' | 'expense' | 'income'>('all')

const dailyOption = computed<EChartsOption>(() => {
  const points = data.value?.daily ?? []
  const series: EChartsOption['series'] = []
  if (dailyFocus.value !== 'income') {
    series.push({
      name: '支出',
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.14 },
      itemStyle: { color: '#e11d48' },
      data: points.map((point) => toNumber(point.expense)),
    })
  }
  if (dailyFocus.value !== 'expense') {
    series.push({
      name: '收入',
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.08 },
      itemStyle: { color: '#059669' },
      data: points.map((point) => toNumber(point.income)),
    })
  }
  return {
    tooltip: { trigger: 'axis', valueFormatter: (value) => `¥${formatMoney(Number(value))}` },
    legend: { data: series.map((item) => (item as { name: string }).name), right: 0, top: 0 },
    grid: { left: 8, right: 16, top: 44, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((point) => dayjs(point.date).format('MM-DD')),
      axisTick: { show: false },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series,
  }
})

const categoryOption = computed<EChartsOption>(() => {
  const items = (data.value?.by_category ?? []).slice(0, 8)
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const entry = params as { name: string; value: number; percent: number }
        return `${entry.name}<br/>¥${entry.value}（${entry.percent}%）`
      },
    },
    legend: { orient: 'vertical', right: 0, top: 'middle', itemWidth: 10, itemHeight: 10 },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        data: items.map((item) => ({
          name: item.name,
          value: toNumber(item.amount),
          itemStyle: item.color ? { color: item.color } : undefined,
        })),
      },
    ],
  }
})

const monthlyOption = computed<EChartsOption>(() => {
  const points = data.value?.monthly ?? []
  return {
    tooltip: { trigger: 'axis', valueFormatter: (value) => `¥${value}` },
    legend: { data: ['支出', '收入'], right: 0, top: 0 },
    grid: { left: 8, right: 16, top: 44, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: points.map((point) => point.month), axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        name: '支出',
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { color: '#e11d48', borderRadius: [4, 4, 0, 0] },
        data: points.map((point) => toNumber(point.expense)),
      },
      {
        name: '收入',
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { color: '#059669', borderRadius: [4, 4, 0, 0] },
        data: points.map((point) => toNumber(point.income)),
      },
    ],
  }
})

const accountOption = computed<EChartsOption>(() => {
  const items = [...(data.value?.by_account ?? [])].reverse()
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value) => `¥${formatMoney(Number(value))}`,
    },
    grid: { left: 8, right: 48, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    yAxis: { type: 'category', data: items.map((item) => item.name), axisTick: { show: false } },
    series: [
      {
        type: 'bar',
        barMaxWidth: 18,
        itemStyle: { color: '#6366f1', borderRadius: [0, 4, 4, 0] },
        label: {
          show: true,
          position: 'right',
          formatter: (params) => `¥${formatMoney(Number(params.value))}`,
        },
        data: items.map((item) => toNumber(item.amount)),
      },
    ],
  }
})

function onSaved() {
  load()
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h2 class="page-title">概览</h2>
        <p class="page-subtitle">{{ range.date_from }} 至 {{ range.date_to }}</p>
      </div>
      <n-space align="center" :size="12">
        <n-radio-group v-model:value="preset" size="small">
          <n-radio-button value="thisMonth">本月</n-radio-button>
          <n-radio-button value="lastMonth">上月</n-radio-button>
          <n-radio-button value="last30">近 30 天</n-radio-button>
          <n-radio-button value="custom">自定义</n-radio-button>
        </n-radio-group>
        <n-date-picker
          v-if="preset === 'custom'"
          v-model:value="customRange"
          type="daterange"
          size="small"
          clearable
        />
        <n-button type="primary" @click="dialogVisible = true">记一笔</n-button>
      </n-space>
    </div>

    <n-grid :cols="4" :x-gap="16" responsive="screen" item-responsive>
      <n-gi span="4 s:2 m:1">
        <n-card size="small" class="stat-card">
          <div class="stat-label">支出</div>
          <n-skeleton v-if="loading" text :width="90" />
          <div v-else class="stat-value amount-out">{{ formatYuan(summary?.expense.amount ?? '0') }}</div>
          <div class="stat-foot">{{ summary?.expense.count ?? 0 }} 笔</div>
        </n-card>
      </n-gi>
      <n-gi span="4 s:2 m:1">
        <n-card size="small" class="stat-card">
          <div class="stat-label">收入</div>
          <n-skeleton v-if="loading" text :width="90" />
          <div v-else class="stat-value amount-in">{{ formatYuan(summary?.income.amount ?? '0') }}</div>
          <div class="stat-foot">{{ summary?.income.count ?? 0 }} 笔</div>
        </n-card>
      </n-gi>
      <n-gi span="4 s:2 m:1">
        <n-card size="small" class="stat-card">
          <div class="stat-label">结余</div>
          <n-skeleton v-if="loading" text :width="90" />
          <div v-else class="stat-value">{{ formatYuan(summary?.net ?? '0') }}</div>
          <div class="stat-foot">收入 − 支出</div>
        </n-card>
      </n-gi>
      <n-gi span="4 s:2 m:1">
        <n-card size="small" class="stat-card">
          <div class="stat-label">笔均支出</div>
          <n-skeleton v-if="loading" text :width="90" />
          <div v-else class="stat-value">{{ formatYuan(summary?.average_expense ?? '0') }}</div>
          <div class="stat-foot">共 {{ summary?.count ?? 0 }} 笔记录</div>
        </n-card>
      </n-gi>
    </n-grid>

    <n-grid :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive class="charts">
      <n-gi span="2 m:1">
        <n-card title="每日支出趋势" size="small">
          <template #header-extra>
            <n-radio-group v-model:value="dailyFocus" size="small">
              <n-radio-button value="all">全部</n-radio-button>
              <n-radio-button value="expense">只看支出</n-radio-button>
              <n-radio-button value="income">只看收入</n-radio-button>
            </n-radio-group>
          </template>
          <n-skeleton v-if="loading" height="280px" />
          <n-empty v-else-if="!hasData" description="这个时间段还没有记录" style="height: 280px" />
          <BaseChart v-else :option="dailyOption" height="280px" />
        </n-card>
      </n-gi>
      <n-gi span="2 m:1">
        <n-card title="支出分类占比" size="small">
          <n-skeleton v-if="loading" height="280px" />
          <n-empty v-else-if="!hasData" description="这个时间段还没有记录" style="height: 280px" />
          <BaseChart v-else :option="categoryOption" height="280px" />
        </n-card>
      </n-gi>
      <n-gi span="2 m:1">
        <n-card title="近 6 个月收支对比" size="small">
          <n-skeleton v-if="loading" height="280px" />
          <BaseChart v-else :option="monthlyOption" height="280px" />
        </n-card>
      </n-gi>
      <n-gi span="2 m:1">
        <n-card title="支付渠道" size="small">
          <n-skeleton v-if="loading" height="280px" />
          <n-empty v-else-if="!hasData" description="这个时间段还没有记录" style="height: 280px" />
          <BaseChart v-else :option="accountOption" height="280px" />
        </n-card>
      </n-gi>
    </n-grid>

    <n-card title="最近记录" size="small" class="recent">
      <template #header-extra>
        <n-button text type="primary" @click="$router.push('/transactions')">查看全部</n-button>
      </template>
      <n-skeleton v-if="loading" text :repeat="4" />
      <n-empty v-else-if="recent.length === 0" description="还没有记录，点击「记一笔」开始" />
      <div v-else class="recent-list">
        <div v-for="item in recent" :key="item.id" class="recent-row">
          <div class="recent-main">
            <span class="recent-icon">{{ item.category?.icon ?? '📝' }}</span>
            <div>
              <div class="recent-title">
                {{ item.payee || item.category?.name || '未命名' }}
                <n-tag size="tiny" :bordered="false" style="margin-left: 6px">
                  {{ item.category?.name }}
                </n-tag>
              </div>
              <div class="recent-meta">
                {{ item.biz_date }}
                <template v-if="item.account"> · {{ item.account.name }}</template>
                <template v-if="item.note"> · {{ item.note }}</template>
              </div>
            </div>
          </div>
          <div :class="item.direction === 'out' ? 'amount-out' : 'amount-in'">
            {{ item.direction === 'out' ? '-' : '+' }}{{ formatYuan(item.amount) }}
          </div>
        </div>
      </div>
    </n-card>

    <TransactionDialog v-model:show="dialogVisible" @saved="onSaved" />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0;
  font-size: 20px;
}

.page-subtitle {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.stat-card :deep(.n-card__content) {
  padding: 10px 4px;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.stat-value {
  font-size: 22px;
  font-weight: 650;
  margin: 6px 0 2px;
  font-variant-numeric: tabular-nums;
}

.stat-foot {
  font-size: 12px;
  color: #9ca3af;
}

.charts {
  margin-top: 16px;
}

.recent {
  margin-top: 16px;
}

.recent-list {
  display: flex;
  flex-direction: column;
}

.recent-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #f1f2f6;
}

.recent-row:last-child {
  border-bottom: none;
}

.recent-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.recent-icon {
  font-size: 20px;
}

.recent-title {
  font-size: 14px;
  font-weight: 550;
}

.recent-meta {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}
</style>
