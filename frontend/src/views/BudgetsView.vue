<script setup lang="ts">
import {
  NButton,
  NCard,
  NDatePicker,
  NEmpty,
  NGrid,
  NGi,
  NInputNumber,
  NModal,
  NProgress,
  NSelect,
  NSpace,
  NTag,
  useDialog,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import dayjs from 'dayjs'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { budgetsApi, categoriesApi } from '@/api'
import { messageOf } from '@/api/client'
import type { BudgetProgress, BudgetStatus, Category } from '@/types'
import { formatYuan, toNumber } from '@/utils/format'

const message = useMessage()
const dialog = useDialog()

const monthValue = ref<number>(dayjs().valueOf())
const status = ref<BudgetStatus | null>(null)
const categories = ref<Category[]>([])
const loading = ref(false)

const modalVisible = ref(false)
const form = reactive<{ scope: 'total' | 'category'; categoryId: number | null; amount: number | null }>(
  { scope: 'total', categoryId: null, amount: null },
)
const saving = ref(false)

const monthKey = computed(() => dayjs(monthValue.value).format('YYYY-MM'))
const monthLabel = computed(() => dayjs(monthValue.value).format('YYYY 年 M 月'))

const categoryOptions = computed<SelectOption[]>(() =>
  categories.value
    .filter((item) => item.kind === 'expense')
    .map((item) => ({ label: `${item.icon ?? ''} ${item.name}`.trim(), value: item.id })),
)

async function load() {
  loading.value = true
  try {
    status.value = await budgetsApi.status(monthKey.value)
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    categories.value = await categoriesApi.list()
  } catch (error) {
    message.error(messageOf(error))
  }
}

function openCreate(scope: 'total' | 'category', existing?: BudgetProgress) {
  form.scope = scope
  form.categoryId = existing?.category_id ?? null
  form.amount = existing ? Number(existing.amount) : null
  modalVisible.value = true
}

async function save() {
  if (form.amount === null || form.amount <= 0) {
    message.warning('请输入大于 0 的预算金额')
    return
  }
  if (form.scope === 'category' && !form.categoryId) {
    message.warning('请选择分类')
    return
  }
  saving.value = true
  try {
    status.value = await budgetsApi.set(
      monthKey.value,
      form.amount.toFixed(2),
      form.scope === 'category' ? form.categoryId : null,
    )
    modalVisible.value = false
    message.success('预算已保存')
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    saving.value = false
  }
}

function confirmDelete(budget: BudgetProgress) {
  dialog.warning({
    title: '删除这条预算？',
    content: budget.category ? `${budget.category.name} · ${formatYuan(budget.amount)}` : `总预算 ${formatYuan(budget.amount)}`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await budgetsApi.remove(budget.id)
        message.success('已删除')
        await load()
      } catch (error) {
        message.error(messageOf(error))
      }
    },
  })
}

watch(monthKey, load)

onMounted(async () => {
  await loadCategories()
  await load()
})

function progressStatus(budget: BudgetProgress) {
  if (budget.over) return 'error'
  return budget.percent >= 80 ? 'warning' : 'success'
}

function usedPercent(budget: BudgetProgress) {
  return Math.min(100, Math.round(budget.percent))
}

function remainingLabel(budget: BudgetProgress) {
  const remaining = toNumber(budget.remaining)
  return remaining >= 0 ? `还剩 ${formatYuan(budget.remaining)}` : `超支 ${formatYuan(Math.abs(remaining).toFixed(2))}`
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h2 class="page-title">预算</h2>
        <p class="page-subtitle">给每个月（或某个分类）设个上限，超支时概览页会提醒</p>
      </div>
      <n-space align="center" :size="12">
        <n-date-picker v-model:value="monthValue" type="month" size="small" />
        <n-button type="primary" @click="openCreate('total', status?.total ?? undefined)">
          {{ status?.total ? '调整总预算' : '设置总预算' }}
        </n-button>
        <n-button @click="openCreate('category')">添加分类预算</n-button>
      </n-space>
    </div>

    <n-grid :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <n-gi span="2 m:1">
        <n-card size="small" :title="`${monthLabel} 总预算`">
          <template #header-extra>
            <n-tag v-if="status?.total?.over" type="error" size="small" :bordered="false">已超支</n-tag>
          </template>
          <n-empty
            v-if="!status?.total"
            description="还没有设置总预算"
            style="padding: 24px 0"
          >
            <template #extra>
              <n-button size="small" @click="openCreate('total')">现在设置</n-button>
            </template>
          </n-empty>
          <div v-else>
            <div class="budget-head">
              <div class="budget-amount">{{ formatYuan(status.total.amount) }}</div>
              <div class="budget-meta">{{ remainingLabel(status.total) }}</div>
            </div>
            <n-progress
              type="line"
              :percentage="usedPercent(status.total)"
              :status="progressStatus(status.total)"
              :height="10"
              :show-indicator="false"
            />
            <div class="budget-foot">
              已花 {{ formatYuan(status.total.spent) }}（{{ status.total.percent }}%）
              <n-button text type="error" size="tiny" style="margin-left: 12px" @click="confirmDelete(status.total)">
                删除
              </n-button>
            </div>
          </div>
        </n-card>
      </n-gi>

      <n-gi span="2 m:1">
        <n-card size="small" :title="`${monthLabel} 分类预算`">
          <n-empty
            v-if="!status?.categories.length"
            description="还没有分类预算"
            style="padding: 24px 0"
          >
            <template #extra>
              <n-button size="small" @click="openCreate('category')">添加</n-button>
            </template>
          </n-empty>
          <div v-else class="category-list">
            <div v-for="item in status.categories" :key="item.id" class="category-row">
              <div class="category-head">
                <span class="category-name">
                  {{ item.category?.icon ?? '📁' }} {{ item.category?.name ?? '已删除分类' }}
                  <n-tag v-if="item.over" type="error" size="tiny" :bordered="false">超支</n-tag>
                </span>
                <n-space :size="8" align="center">
                  <span class="category-meta">{{ formatYuan(item.spent) }} / {{ formatYuan(item.amount) }}</span>
                  <n-button text type="primary" size="tiny" @click="openCreate('category', item)">调整</n-button>
                  <n-button text type="error" size="tiny" @click="confirmDelete(item)">删除</n-button>
                </n-space>
              </div>
              <n-progress
                type="line"
                :percentage="usedPercent(item)"
                :status="progressStatus(item)"
                :height="8"
                :show-indicator="false"
              />
            </div>
          </div>
        </n-card>
      </n-gi>
    </n-grid>

    <n-modal v-model:show="modalVisible" preset="card" :title="form.scope === 'total' ? '设置总预算' : '设置分类预算'" style="max-width: 420px">
      <n-space vertical :size="14">
        <div v-if="form.scope === 'category'">
          <div class="field-label">分类</div>
          <n-select v-model:value="form.categoryId" :options="categoryOptions" placeholder="选择分类" />
        </div>
        <div>
          <div class="field-label">每月上限（元）</div>
          <n-input-number
            v-model:value="form.amount"
            :min="0.01"
            :precision="2"
            :show-button="false"
            placeholder="0.00"
            style="width: 100%"
            size="large"
          />
        </div>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="modalVisible = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-modal>
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

.budget-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}

.budget-amount {
  font-size: 24px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.budget-meta {
  color: #6b7280;
  font-size: 13px;
}

.budget-foot {
  margin-top: 8px;
  color: #6b7280;
  font-size: 13px;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.category-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.category-name {
  font-size: 14px;
  font-weight: 550;
}

.category-meta {
  color: #6b7280;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.field-label {
  font-size: 13px;
  color: #4b5563;
  margin-bottom: 6px;
}
</style>
