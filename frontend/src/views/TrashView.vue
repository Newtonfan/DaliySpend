<script setup lang="ts">
import {
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NSpace,
  NTag,
  useDialog,
  useMessage,
  type DataTableColumns,
  type PaginationProps,
} from 'naive-ui'
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { transactionsApi } from '@/api'
import { messageOf } from '@/api/client'
import type { Transaction } from '@/types'
import { formatDateTime, formatYuan } from '@/utils/format'

const message = useMessage()
const dialog = useDialog()
const router = useRouter()

const rows = ref<Transaction[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const pagination = computed<PaginationProps>(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
}))

const columns = computed<DataTableColumns<Transaction>>(() => [
  { title: '日期', key: 'biz_date', width: 110 },
  {
    title: '分类',
    key: 'category',
    width: 130,
    render: (row) =>
      h('span', `${row.category?.icon ?? '📝'} ${row.category?.name ?? '—'}`.trim()),
  },
  {
    title: '商户 / 备注',
    key: 'payee',
    render: (row) =>
      h('div', [
        h('div', { style: 'font-weight:550' }, row.payee || row.category?.name || '—'),
        row.note ? h('div', { style: 'color:#9ca3af;font-size:12px' }, row.note) : null,
      ]),
  },
  {
    title: '金额',
    key: 'amount',
    width: 130,
    align: 'right',
    render: (row) =>
      h(
        'span',
        { class: row.direction === 'out' ? 'amount-out' : 'amount-in' },
        `${row.direction === 'out' ? '-' : '+'}${formatYuan(row.amount)}`,
      ),
  },
  {
    title: '删除时间',
    key: 'deleted_at',
    width: 170,
    render: (row) => (row.deleted_at ? formatDateTime(row.deleted_at) : '—'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    align: 'right',
    render: (row) =>
      h(NSpace, { justify: 'end', size: 4 }, () => [
        h(
          NButton,
          { size: 'tiny', text: true, type: 'primary', onClick: () => restore(row) },
          () => '恢复',
        ),
        h(
          NButton,
          { size: 'tiny', text: true, type: 'error', onClick: () => purge(row) },
          () => '永久删除',
        ),
      ]),
  },
])

async function load() {
  loading.value = true
  try {
    const data = await transactionsApi.trash({ page: page.value, page_size: pageSize.value })
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    loading.value = false
  }
}

async function restore(row: Transaction) {
  try {
    await transactionsApi.restore(row.id)
    message.success('已恢复到流水列表')
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (error) {
    message.error(messageOf(error))
  }
}

function purge(row: Transaction) {
  dialog.error({
    title: '永久删除这条流水？',
    content: '删除后无法恢复。',
    positiveText: '永久删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await transactionsApi.purge(row.id)
        message.success('已永久删除')
        if (rows.value.length === 1 && page.value > 1) page.value -= 1
        await load()
      } catch (error) {
        message.error(messageOf(error))
      }
    },
  })
}

function emptyTrash() {
  dialog.error({
    title: '清空回收站？',
    content: `将永久删除 ${total.value} 条流水，无法恢复。`,
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const removed = await transactionsApi.emptyTrash()
        message.success(`已永久删除 ${removed} 条`)
        page.value = 1
        await load()
      } catch (error) {
        message.error(messageOf(error))
      }
    },
  })
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h2 class="page-title">回收站</h2>
        <p class="page-subtitle">删除的流水会先放在这里，可以恢复或彻底删除</p>
      </div>
      <n-space>
        <n-button @click="router.push('/transactions')">返回流水</n-button>
        <n-button type="error" ghost :disabled="total === 0" @click="emptyTrash">清空回收站</n-button>
      </n-space>
    </div>

    <n-card size="small">
      <n-empty v-if="!loading && rows.length === 0" description="回收站是空的" style="padding: 32px 0" />
      <n-data-table
        v-else
        remote
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="pagination"
        :row-key="(row: Transaction) => row.id"
        :bordered="false"
        @update:page="(value: number) => { page = value; load() }"
      />
    </n-card>
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
