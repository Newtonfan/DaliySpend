<script setup lang="ts">
import {
  NCard,
  NButton,
  NGrid,
  NGi,
  NSelect,
  NSpace,
  NStatistic,
  NTag,
  NUpload,
  NDataTable,
  NAlert,
  useMessage,
  type DataTableColumns,
  type SelectOption,
  type UploadFileInfo,
} from 'naive-ui'
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { accountsApi, categoriesApi, importsApi } from '@/api'
import { messageOf } from '@/api/client'
import type { Account, Category, ImportResult, ImportSampleRow } from '@/types'
import { formatYuan } from '@/utils/format'

const message = useMessage()
const router = useRouter()

const file = ref<File | null>(null)
const fileName = ref('')
const categories = ref<Category[]>([])
const accounts = ref<Account[]>([])
const options = reactive<{ categoryId: number | null; accountId: number | null }>({
  categoryId: null,
  accountId: null,
})

const previewing = ref(false)
const importing = ref(false)
const result = ref<ImportResult | null>(null)

const categoryOptions = computed<SelectOption[]>(() => {
  const expense = categories.value.filter((item) => item.kind === 'expense')
  const income = categories.value.filter((item) => item.kind === 'income')
  const groups: SelectOption[] = []
  if (expense.length) {
    groups.push({
      type: 'group',
      label: '支出分类',
      key: 'expense',
      children: expense.map((item) => ({ label: item.name, value: item.id })),
    })
  }
  if (income.length) {
    groups.push({
      type: 'group',
      label: '收入分类',
      key: 'income',
      children: income.map((item) => ({ label: item.name, value: item.id })),
    })
  }
  return groups
})

const accountOptions = computed<SelectOption[]>(() =>
  accounts.value.map((item) => ({ label: item.name, value: item.id })),
)

const sourceLabel = computed(() =>
  result.value?.source === 'alipay' ? '支付宝账单' : '微信支付账单',
)

const columns = computed<DataTableColumns<ImportSampleRow>>(() => [
  { title: '行号', key: 'line', width: 70 },
  { title: '日期', key: 'date', width: 110 },
  {
    title: '商户 / 说明',
    key: 'payee',
    render: (row) =>
      h('div', [
        h('div', { style: 'font-weight:550' }, row.payee || row.category_hint || '—'),
        row.note ? h('div', { style: 'color:#9ca3af;font-size:12px' }, row.note) : null,
      ]),
  },
  {
    title: '账单分类',
    key: 'category_hint',
    width: 120,
    render: (row) => row.category_hint || '—',
  },
  { title: '支付方式', key: 'method', width: 150, render: (row) => row.method || '—' },
  {
    title: '金额',
    key: 'amount',
    width: 120,
    align: 'right',
    render: (row) =>
      h(
        'span',
        { class: row.direction === 'out' ? 'amount-out' : 'amount-in' },
        `${row.direction === 'out' ? '-' : '+'}${formatYuan(row.amount)}`,
      ),
  },
])

function onFileChange(info: { file: UploadFileInfo }) {
  const raw = info.file.file
  if (!raw) return
  if (!raw.name.toLowerCase().endsWith('.csv')) {
    message.warning('请选择 CSV 文件（微信/支付宝导出的明细）')
    return
  }
  file.value = raw
  fileName.value = raw.name
  result.value = null
}

async function loadOptions() {
  try {
    const [categoryList, accountList] = await Promise.all([
      categoriesApi.list(),
      accountsApi.list(),
    ])
    categories.value = categoryList
    accounts.value = accountList
    options.accountId = accountList[0]?.id ?? null
  } catch (error) {
    message.error(messageOf(error))
  }
}

async function preview() {
  if (!file.value) {
    message.warning('请先选择文件')
    return
  }
  previewing.value = true
  try {
    result.value = await importsApi.upload(file.value, true, {
      default_category_id: options.categoryId,
      default_account_id: options.accountId,
    })
    if (result.value.ready === 0) {
      message.info('没有新记录可导入（可能已全部导入过）')
    }
  } catch (error) {
    message.error(messageOf(error))
    result.value = null
  } finally {
    previewing.value = false
  }
}

async function commit() {
  if (!file.value || !result.value) return
  importing.value = true
  try {
    const imported = await importsApi.upload(file.value, false, {
      default_category_id: options.categoryId,
      default_account_id: options.accountId,
    })
    result.value = imported
    message.success(`已导入 ${imported.imported ?? 0} 条流水`)
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    importing.value = false
  }
}

onMounted(loadOptions)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h2 class="page-title">账单导入</h2>
        <p class="page-subtitle">
          导入微信支付 / 支付宝导出的 CSV 明细，按交易单号自动去重，重复导入不会多记账
        </p>
      </div>
      <n-button text type="primary" @click="router.push('/transactions')">查看流水</n-button>
    </div>

    <n-card size="small">
      <n-space align="center" :size="16" style="flex-wrap: wrap">
        <n-upload
          :show-file-list="false"
          accept=".csv,text/csv"
          :default-upload="false"
          :on-change="onFileChange"
        >
          <n-button>选择 CSV 文件</n-button>
        </n-upload>
        <span v-if="fileName" class="hint">已选择：{{ fileName }}</span>
        <n-button type="primary" :loading="previewing" :disabled="!file" @click="preview">
          解析预览
        </n-button>
      </n-space>
      <p class="hint" style="margin-top: 12px">
        微信：我 → 服务 → 钱包 → 账单 → 常见问题 → 下载账单 → 用于个人对账，导出后解压得到 CSV。<br />
        支付宝：我的 → 账单 → 右上角 → 开具交易流水证明 → 用于个人对账，导出后解压得到 CSV。
      </p>
    </n-card>

    <template v-if="result">
      <n-card size="small" style="margin-top: 16px">
        <template #header>
          <n-space align="center" :size="10">
            <span>解析结果</span>
            <n-tag size="small" type="success" :bordered="false">{{ sourceLabel }}</n-tag>
            <n-tag size="small" :bordered="false">编码 {{ result.encoding }}</n-tag>
          </n-space>
        </template>

        <n-grid :cols="5" :x-gap="12" responsive="screen" item-responsive>
          <n-gi span="5 s:1">
            <n-statistic label="账单行数" :value="result.total_rows" />
          </n-gi>
          <n-gi span="5 s:1">
            <n-statistic label="可导入" :value="result.ready" />
          </n-gi>
          <n-gi span="5 s:1">
            <n-statistic label="已存在（跳过）" :value="result.duplicates" />
          </n-gi>
          <n-gi span="5 s:1">
            <n-statistic label="无效行" :value="result.skipped" />
          </n-gi>
          <n-gi span="5 s:1">
            <n-statistic label="支出合计" :value="formatYuan(result.totals.expense)" />
          </n-gi>
        </n-grid>

        <n-alert v-if="result.imported !== null" type="success" :bordered="false" style="margin-top: 12px">
          已导入 {{ result.imported }} 条；本次跳过重复 {{ result.duplicates }} 条、无效
          {{ result.skipped }} 条。
        </n-alert>

        <n-space align="center" :size="12" style="margin-top: 16px; flex-wrap: wrap">
          <n-select
            v-model:value="options.categoryId"
            :options="categoryOptions"
            placeholder="未匹配分类时使用的默认分类"
            clearable
            style="width: 260px"
            size="small"
          />
          <n-select
            v-model:value="options.accountId"
            :options="accountOptions"
            placeholder="未匹配账户时使用的默认账户"
            clearable
            style="width: 220px"
            size="small"
          />
          <n-button
            type="primary"
            :loading="importing"
            :disabled="result.ready === 0 || result.imported !== null"
            @click="commit"
          >
            确认导入 {{ result.ready }} 条
          </n-button>
        </n-space>

        <div v-if="result.skipped_reasons.length" class="skipped">
          <p class="hint">被跳过的行（最多显示 20 条）：</p>
          <ul>
            <li v-for="reason in result.skipped_reasons" :key="reason.line">
              第 {{ reason.line }} 行：{{ reason.reason }}
            </li>
          </ul>
        </div>
      </n-card>

      <n-card size="small" style="margin-top: 16px" title="明细预览（前 10 条）">
        <n-data-table
          :columns="columns"
          :data="result.sample"
          :bordered="false"
          size="small"
          :row-key="(row: ImportSampleRow) => row.line"
        />
      </n-card>
    </template>
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

.hint {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}

.skipped {
  margin-top: 12px;
}

.skipped ul {
  margin: 6px 0 0;
  padding-left: 20px;
  color: #6b7280;
  font-size: 13px;
}
</style>
