<script setup lang="ts">
import {
  NButton,
  NCard,
  NDatePicker,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGi,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTag,
  useDialog,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import dayjs from 'dayjs'
import { computed, onMounted, reactive, ref } from 'vue'
import { accountsApi, authApi, categoriesApi, exportCsvUrl } from '@/api'
import { messageOf } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { Account, Category, CategoryKind } from '@/types'
import { formatYuan, lastNDaysRange } from '@/utils/format'

const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()

const categories = ref<Category[]>([])
const accounts = ref<Account[]>([])
const loading = ref(false)

const categoryModal = ref(false)
const categoryForm = reactive({
  id: null as number | null,
  name: '',
  kind: 'expense' as CategoryKind,
  icon: '',
  color: '',
})

const accountModal = ref(false)
const accountForm = reactive({
  id: null as number | null,
  name: '',
  type: 'other',
  initial_balance: '',
})

const passwordForm = reactive({ current: '', next: '', confirm: '' })
const passwordLoading = ref(false)

const exportRange = ref<[number, number]>([
  dayjs(lastNDaysRange(365).from).valueOf(),
  dayjs().valueOf(),
])

const expenseCategories = computed(() => categories.value.filter((item) => item.kind === 'expense'))
const incomeCategories = computed(() => categories.value.filter((item) => item.kind === 'income'))

const accountTypeOptions: SelectOption[] = [
  { label: '现金', value: 'cash' },
  { label: '支付宝', value: 'alipay' },
  { label: '微信', value: 'wechat' },
  { label: '银行卡', value: 'bank' },
  { label: '信用卡', value: 'credit' },
  { label: '其他', value: 'other' },
]

async function load() {
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

function openCategoryCreate(kind: CategoryKind) {
  Object.assign(categoryForm, { id: null, name: '', kind, icon: '', color: '' })
  categoryModal.value = true
}

function openCategoryEdit(category: Category) {
  Object.assign(categoryForm, {
    id: category.id,
    name: category.name,
    kind: category.kind,
    icon: category.icon ?? '',
    color: category.color ?? '',
  })
  categoryModal.value = true
}

async function saveCategory() {
  if (!categoryForm.name.trim()) {
    message.warning('请填写分类名称')
    return
  }
  try {
    const payload = {
      name: categoryForm.name.trim(),
      kind: categoryForm.kind,
      icon: categoryForm.icon || null,
      color: categoryForm.color || null,
    }
    if (categoryForm.id) {
      const { kind: _kind, ...rest } = payload
      await categoriesApi.update(categoryForm.id, rest)
    } else {
      await categoriesApi.create(payload)
    }
    categoryModal.value = false
    message.success('已保存')
    await load()
  } catch (error) {
    message.error(messageOf(error))
  }
}

function confirmDeleteCategory(category: Category) {
  dialog.warning({
    title: `删除分类「${category.name}」？`,
    content: '仅在分类下没有流水时才能删除。',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await categoriesApi.remove(category.id)
        message.success('已删除')
        await load()
      } catch (error) {
        message.error(messageOf(error))
      }
    },
  })
}

function openAccountCreate() {
  Object.assign(accountForm, { id: null, name: '', type: 'other', initial_balance: '' })
  accountModal.value = true
}

function openAccountEdit(account: Account) {
  Object.assign(accountForm, {
    id: account.id,
    name: account.name,
    type: account.type,
    initial_balance: account.initial_balance,
  })
  accountModal.value = true
}

async function saveAccount() {
  if (!accountForm.name.trim()) {
    message.warning('请填写账户名称')
    return
  }
  try {
    if (accountForm.id) {
      await accountsApi.update(accountForm.id, {
        name: accountForm.name.trim(),
        type: accountForm.type,
        initial_balance: accountForm.initial_balance || '0',
      })
    } else {
      await accountsApi.create({
        name: accountForm.name.trim(),
        type: accountForm.type,
        initial_balance: accountForm.initial_balance || '0',
      })
    }
    accountModal.value = false
    message.success('已保存')
    await load()
  } catch (error) {
    message.error(messageOf(error))
  }
}

function confirmDeleteAccount(account: Account) {
  dialog.warning({
    title: `删除账户「${account.name}」？`,
    content: '仅在账户下没有流水时才能删除。',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await accountsApi.remove(account.id)
        message.success('已删除')
        await load()
      } catch (error) {
        message.error(messageOf(error))
      }
    },
  })
}

async function changePassword() {
  if (passwordForm.next !== passwordForm.confirm) {
    message.warning('两次输入的新密码不一致')
    return
  }
  passwordLoading.value = true
  try {
    await authApi.changePassword(passwordForm.current, passwordForm.next)
    message.success('密码已更新')
    passwordForm.current = ''
    passwordForm.next = ''
    passwordForm.confirm = ''
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    passwordLoading.value = false
  }
}

function downloadCsv() {
  const [from, to] = exportRange.value
  window.location.href = exportCsvUrl({
    date_from: dayjs(from).format('YYYY-MM-DD'),
    date_to: dayjs(to).format('YYYY-MM-DD'),
  })
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h2 class="page-title">设置</h2>
        <p class="page-subtitle">管理分类、账户，导出数据，修改密码</p>
      </div>
      <n-tag :bordered="false" type="info">{{ auth.user?.email }}</n-tag>
    </div>

    <n-grid :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <n-gi span="2 m:1">
        <n-card title="支出分类" size="small">
          <template #header-extra>
            <n-button size="tiny" type="primary" quaternary @click="openCategoryCreate('expense')">
              + 新增
            </n-button>
          </template>
          <n-empty v-if="expenseCategories.length === 0" description="还没有支出分类" />
          <div v-for="category in expenseCategories" :key="category.id" class="row">
            <span class="row-icon">{{ category.icon || '📁' }}</span>
            <span class="row-name">{{ category.name }}</span>
            <n-space :size="4">
              <n-button size="tiny" text type="primary" @click="openCategoryEdit(category)">编辑</n-button>
              <n-button size="tiny" text type="error" @click="confirmDeleteCategory(category)">删除</n-button>
            </n-space>
          </div>
        </n-card>
      </n-gi>

      <n-gi span="2 m:1">
        <n-card title="收入分类" size="small">
          <template #header-extra>
            <n-button size="tiny" type="primary" quaternary @click="openCategoryCreate('income')">
              + 新增
            </n-button>
          </template>
          <n-empty v-if="incomeCategories.length === 0" description="还没有收入分类" />
          <div v-for="category in incomeCategories" :key="category.id" class="row">
            <span class="row-icon">{{ category.icon || '📁' }}</span>
            <span class="row-name">{{ category.name }}</span>
            <n-space :size="4">
              <n-button size="tiny" text type="primary" @click="openCategoryEdit(category)">编辑</n-button>
              <n-button size="tiny" text type="error" @click="confirmDeleteCategory(category)">删除</n-button>
            </n-space>
          </div>
        </n-card>
      </n-gi>

      <n-gi span="2 m:1">
        <n-card title="支付账户" size="small">
          <template #header-extra>
            <n-button size="tiny" type="primary" quaternary @click="openAccountCreate">+ 新增</n-button>
          </template>
          <n-empty v-if="accounts.length === 0" description="还没有账户" />
          <div v-for="account in accounts" :key="account.id" class="row">
            <span class="row-icon">💳</span>
            <span class="row-name">{{ account.name }}</span>
            <span class="row-amount">{{ formatYuan(account.initial_balance) }}</span>
            <n-space :size="4">
              <n-button size="tiny" text type="primary" @click="openAccountEdit(account)">编辑</n-button>
              <n-button size="tiny" text type="error" @click="confirmDeleteAccount(account)">删除</n-button>
            </n-space>
          </div>
        </n-card>
      </n-gi>

      <n-gi span="2 m:1">
        <n-card title="数据导出" size="small">
          <p class="hint">导出为 CSV（含 UTF-8 BOM，Excel 可直接打开），建议定期备份。</p>
          <n-space align="center">
            <n-date-picker v-model:value="exportRange" type="daterange" size="small" />
            <n-button type="primary" size="small" @click="downloadCsv">下载 CSV</n-button>
          </n-space>
        </n-card>
      </n-gi>

      <n-gi span="2 m:1">
        <n-card title="修改密码" size="small">
          <n-form label-placement="top">
            <n-form-item label="当前密码">
              <n-input v-model:value="passwordForm.current" type="password" show-password-on="click" />
            </n-form-item>
            <n-form-item label="新密码">
              <n-input v-model:value="passwordForm.next" type="password" show-password-on="click" />
            </n-form-item>
            <n-form-item label="确认新密码">
              <n-input v-model:value="passwordForm.confirm" type="password" show-password-on="click" />
            </n-form-item>
          </n-form>
          <n-button type="primary" size="small" :loading="passwordLoading" @click="changePassword">
            更新密码
          </n-button>
        </n-card>
      </n-gi>
    </n-grid>

    <n-modal v-model:show="categoryModal" preset="card" :title="categoryForm.id ? '编辑分类' : '新增分类'" style="max-width: 420px">
      <n-form label-placement="top">
        <n-form-item label="名称">
          <n-input v-model:value="categoryForm.name" placeholder="例如：宠物" maxlength="40" />
        </n-form-item>
        <n-form-item label="图标（emoji）">
          <n-input v-model:value="categoryForm.icon" placeholder="🐱" maxlength="8" />
        </n-form-item>
        <n-form-item label="颜色">
          <n-input v-model:value="categoryForm.color" placeholder="#f59e0b" maxlength="16" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="categoryModal = false">取消</n-button>
          <n-button type="primary" @click="saveCategory">保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="accountModal" preset="card" :title="accountForm.id ? '编辑账户' : '新增账户'" style="max-width: 420px">
      <n-form label-placement="top">
        <n-form-item label="名称">
          <n-input v-model:value="accountForm.name" placeholder="例如：招行储蓄卡" maxlength="40" />
        </n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="accountForm.type" :options="accountTypeOptions" />
        </n-form-item>
        <n-form-item label="初始余额">
          <n-input v-model:value="accountForm.initial_balance" placeholder="0.00" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="accountModal = false">取消</n-button>
          <n-button type="primary" @click="saveAccount">保存</n-button>
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

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #f1f2f6;
}

.row:last-child {
  border-bottom: none;
}

.row-icon {
  font-size: 16px;
}

.row-name {
  flex: 1;
  font-size: 14px;
}

.row-amount {
  color: #6b7280;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.hint {
  margin: 0 0 12px;
  color: #6b7280;
  font-size: 13px;
}
</style>
