<script setup lang="ts">
import {
  NButton,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import dayjs from 'dayjs'
import { computed, ref, watch } from 'vue'
import { accountsApi, categoriesApi, transactionsApi } from '@/api'
import { messageOf } from '@/api/client'
import type { Account, Category, Transaction } from '@/types'

const props = defineProps<{
  show: boolean
  transaction?: Transaction | null
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'saved'): void
}>()

const message = useMessage()

const loading = ref(false)
const saving = ref(false)
const categories = ref<Category[]>([])
const accounts = ref<Account[]>([])

const amount = ref<number | null>(null)
const categoryId = ref<number | null>(null)
const accountId = ref<number | null>(null)
const bizDate = ref<number>(dayjs().valueOf())
const payee = ref('')
const note = ref('')

const title = computed(() => (props.transaction ? '编辑流水' : '记一笔'))

const categoryOptions = computed<SelectOption[]>(() => {
  const groups: SelectOption[] = []
  const expense = categories.value.filter((item) => item.kind === 'expense')
  const income = categories.value.filter((item) => item.kind === 'income')
  if (expense.length) {
    groups.push({
      type: 'group',
      label: '支出',
      key: 'group-expense',
      children: expense.map((item) => ({
        label: `${item.icon ?? ''} ${item.name}`.trim(),
        value: item.id,
      })),
    })
  }
  if (income.length) {
    groups.push({
      type: 'group',
      label: '收入',
      key: 'group-income',
      children: income.map((item) => ({
        label: `${item.icon ?? ''} ${item.name}`.trim(),
        value: item.id,
      })),
    })
  }
  return groups
})

const accountOptions = computed<SelectOption[]>(() =>
  accounts.value.map((item) => ({ label: item.name, value: item.id })),
)

function resetForm() {
  if (props.transaction) {
    amount.value = Number(props.transaction.amount)
    categoryId.value = props.transaction.category_id
    accountId.value = props.transaction.account_id
    bizDate.value = dayjs(props.transaction.biz_date).valueOf()
    payee.value = props.transaction.payee ?? ''
    note.value = props.transaction.note ?? ''
    return
  }
  amount.value = null
  categoryId.value = categories.value.find((item) => item.kind === 'expense')?.id ?? null
  accountId.value = accounts.value[0]?.id ?? null
  bizDate.value = dayjs().valueOf()
  payee.value = ''
  note.value = ''
}

async function ensureOptions() {
  if (categories.value.length && accounts.value.length) return
  loading.value = true
  try {
    const [categoryList, accountList] = await Promise.all([
      categoriesApi.list(),
      accountsApi.list(),
    ])
    categories.value = categoryList
    accounts.value = accountList
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  async (visible) => {
    if (!visible) return
    await ensureOptions()
    resetForm()
  },
  { immediate: true },
)

function close() {
  emit('update:show', false)
}

async function submit() {
  if (amount.value === null || amount.value <= 0) {
    message.warning('请输入大于 0 的金额')
    return
  }
  if (!categoryId.value) {
    message.warning('请选择分类')
    return
  }

  const payload = {
    amount: amount.value.toFixed(2),
    category_id: categoryId.value,
    account_id: accountId.value,
    biz_date: dayjs(bizDate.value).format('YYYY-MM-DD'),
    payee: payee.value.trim() || null,
    note: note.value.trim() || null,
  }

  saving.value = true
  try {
    if (props.transaction) {
      await transactionsApi.update(props.transaction.id, payload)
      message.success('已更新')
    } else {
      await transactionsApi.create(payload)
      message.success('已记账')
    }
    emit('saved')
    close()
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal :show="props.show" preset="card" :title="title" style="max-width: 460px" @update:show="close">
    <n-spin :show="loading">
      <n-form label-placement="top">
        <n-form-item label="金额（元）">
          <n-input-number
            v-model:value="amount"
            :min="0.01"
            :precision="2"
            :show-button="false"
            placeholder="0.00"
            size="large"
            style="width: 100%"
          />
        </n-form-item>

        <n-form-item label="分类">
          <n-select
            v-model:value="categoryId"
            :options="categoryOptions"
            placeholder="选择分类"
            filterable
          />
        </n-form-item>

        <n-form-item label="日期">
          <n-date-picker v-model:value="bizDate" type="date" style="width: 100%" />
        </n-form-item>

        <n-form-item label="支付账户">
          <n-select
            v-model:value="accountId"
            :options="accountOptions"
            placeholder="可选"
            clearable
          />
        </n-form-item>

        <n-form-item label="商户">
          <n-input v-model:value="payee" placeholder="例如：星巴克" maxlength="120" />
        </n-form-item>

        <n-form-item label="备注">
          <n-input
            v-model:value="note"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="补充说明（可选）"
            maxlength="2000"
          />
        </n-form-item>
      </n-form>
    </n-spin>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">取消</n-button>
        <n-button type="primary" :loading="saving" @click="submit">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
