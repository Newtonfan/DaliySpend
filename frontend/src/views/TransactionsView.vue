<script setup lang="ts">
import {
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NInput,
  NSelect,
  NSpace,
  NTag,
  useDialog,
  useMessage,
  type DataTableColumns,
  type PaginationProps,
  type SelectOption,
} from 'naive-ui'
import dayjs from 'dayjs'
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { accountsApi, categoriesApi, exportCsvUrl, transactionsApi } from '@/api'
import { messageOf } from '@/api/client'
import TransactionDialog from '@/components/TransactionDialog.vue'
import type { Account, Category, Transaction, TransactionQuery } from '@/types'
import { formatYuan, monthRange } from '@/utils/format'

const message = useMessage()
const dialog = useDialog()

const rows = ref<Transaction[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const categories = ref<Category[]>([])
const accounts = ref<Account[]>([])
const dialogVisible = ref(false)
const editing = ref<Transaction | null>(null)

const initial = monthRange(0)
const filters = reactive({
  dateRange: [dayjs(initial.from).valueOf(), dayjs(initial.to).valueOf()] as [number, number] | null,
  categoryId: null as number | null,
  accountId: null as number | null,
  direction: null as 'out' | 'in' | null,
  keyword: '',
})

const categoryOptions = computed<SelectOption[]>(() =>
  categories.value.map((item) => ({ label: `${item.icon ?? ''} ${item.name}`.trim(), value: item.id })),
)
const accountOptions = computed<SelectOption[]>(() =>
  accounts.value.map((item) => ({ label: item.name, value: item.id })),
)
const directionOptions: SelectOption[] = [
  { label: '全部', value: null as unknown as string },
  { label: '支出', value: 'out' },
  { label: '收入', value: 'in' },
]

const rangeParams = computed(() => {
  if (!filters.dateRange) return {}
  return {
    date_from: dayjs(filters.dateRange[0]).format('YYYY-MM-DD'),
    date_to: dayjs(filters.dateRange[1]).format('YYYY-MM-DD'),
  }
})

const pagination = computed<PaginationProps>(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
}))

const columns = computed<DataTableColumns<Transaction>>(() => [
  { title: '日期', key: 'biz_date', width: 112 },
  {
    title: '分类',
    key: 'category',
    width: 140,
    render: (row) =>
      h(NSpace, { align: 'center', size: 6, wrapItem: false }, () => [
        h('span', { style: 'font-size:16px' }, row.category?.icon ?? '📝'),
        h('span', row.category?.name ?? '—'),
      ]),
  },
  {
    title: '商户 / 备注',
    key: 'payee',
    render: (row) =>
      h('div', [
        h('div', { style: 'font-weight:550' }, [
          row.payee || row.category?.name || '—',
          row.source !== 'manual'
            ? h(
                NTag,
                {
                  size: 'tiny',
                  bordered: false,
                  type: row.source === 'alipay' ? 'info' : 'success',
                  style: 'margin-left:6px',
                },
                () => (row.source === 'alipay' ? '支付宝' : '微信'),
              )
            : null,
        ]),
        row.note
          ? h('div', { style: 'color:#9ca3af;font-size:12px;margin-top:2px' }, row.note)
          : null,
      ]),
  },
  {
    title: '账户',
    key: 'account',
    width: 110,
    render: (row) => row.account?.name ?? '—',
  },
  {
    title: '金额',
    key: 'amount',
    width: 140,
    align: 'right',
    render: (row) =>
      h(
        'span',
        { class: row.direction === 'out' ? 'amount-out' : 'amount-in' },
        `${row.direction === 'out' ? '-' : '+'}${formatYuan(row.amount)}`,
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    align: 'right',
    render: (row) =>
      h(NSpace, { justify: 'end', size: 4 }, () => [
        h(
          NButton,
          { size: 'tiny', text: true, type: 'primary', onClick: () => openEdit(row) },
          () => '编辑',
        ),
        h(
          NButton,
          { size: 'tiny', text: true, type: 'error', onClick: () => confirmDelete(row) },
          () => '删除',
        ),
      ]),
  },
])

async function loadOptions() {
  try {
    const [categoryList, accountList] = await Promise.all([
      categoriesApi.list(),
      accountsApi.list(),
    ])
    categories.value = categoryList
    accounts.value = accountList
  } catch (error) {
    message.error(messageOf(error))
  }
}

async function load() {
  loading.value = true
  try {
    const query: TransactionQuery = {
      page: page.value,
      page_size: pageSize.value,
      ...rangeParams.value,
    }
    if (filters.categoryId) query.category_id = filters.categoryId
    if (filters.accountId) query.account_id = filters.accountId
    if (filters.direction) query.direction = filters.direction
    if (filters.keyword.trim()) query.q = filters.keyword.trim()

    const data = await transactionsApi.list(query)
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  dialogVisible.value = true
}

function openEdit(row: Transaction) {
  editing.value = row
  dialogVisible.value = true
}

function confirmDelete(row: Transaction) {
  dialog.warning({
    title: '删除这条流水？',
    content: `${row.biz_date} ${row.payee ?? row.category?.name ?? ''} ${formatYuan(row.amount)}`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await transactionsApi.remove(row.id)
        message.success('已删除')
        if (rows.value.length === 1 && page.value > 1) page.value -= 1
        await load()
      } catch (error) {
        message.error(messageOf(error))
      }
    },
  })
}

function downloadCsv() {
  window.location.href = exportCsvUrl(rangeParams.value)
}

function resetFilters() {
  const range = monthRange(0)
  filters.dateRange = [dayjs(range.from).valueOf(), dayjs(range.to).valueOf()]
  filters.categoryId = null
  filters.accountId = null
  filters.direction = null
  filters.keyword = ''
  page.value = 1
}

let keywordTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => [filters.dateRange, filters.categoryId, filters.accountId, filters.direction],
  () => {
    page.value = 1
    load()
  },
  { deep: true },
)
watch(
  () => filters.keyword,
  () => {
    if (keywordTimer) clearTimeout(keywordTimer)
    keywordTimer = setTimeout(() => {
      page.value = 1
      load()
    }, 300)
  },
)
watch([page, pageSize], load)

onMounted(async () => {
  await loadOptions()
  await load()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h2 class="page-title">流水</h2>
        <p class="page-subtitle">记录每一笔支出与收入，可按日期、分类、账户和关键字筛选</p>
      </div>
      <n-space>
        <n-button text @click="$router.push('/trash')">回收站</n-button>
        <n-button @click="downloadCsv">导出 CSV</n-button>
        <n-button type="primary" @click="openCreate">记一笔</n-button>
      </n-space>
    </div>

    <n-card size="small" class="filters">
      <n-space align="center" :size="12" style="flex-wrap: wrap">
        <n-date-picker v-model:value="filters.dateRange" type="daterange" size="small" clearable />
        <n-select
          v-model:value="filters.categoryId"
          :options="categoryOptions"
          placeholder="全部分类"
          size="small"
          clearable
          style="width: 160px"
        />
        <n-select
          v-model:value="filters.accountId"
          :options="accountOptions"
          placeholder="全部账户"
          size="small"
          clearable
          style="width: 150px"
        />
        <n-select
          v-model:value="filters.direction"
          :options="directionOptions"
          placeholder="收支类型"
          size="small"
          clearable
          style="width: 130px"
        />
        <n-input
          v-model:value="filters.keyword"
          placeholder="搜索商户或备注"
          size="small"
          clearable
          style="width: 200px"
        />
        <n-button size="small" quaternary @click="resetFilters">重置</n-button>
      </n-space>
    </n-card>

    <n-card size="small" style="margin-top: 16px">
      <n-data-table
        remote
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="pagination"
        :row-key="(row: Transaction) => row.id"
        :bordered="false"
        @update:page="(value: number) => (page = value)"
        @update:page-size="(value: number) => { pageSize = value; page = 1 }"
      />
    </n-card>

    <TransactionDialog
      v-model:show="dialogVisible"
      :transaction="editing"
      @saved="load"
    />
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
</style>
