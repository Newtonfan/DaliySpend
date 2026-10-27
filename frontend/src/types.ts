export interface User {
  id: number
  email: string
  display_name: string
  created_at: string | null
}

export interface PublicSettings {
  registration_enabled: boolean
  password_min_length: number
  app_name: string
}

export type Direction = 'out' | 'in'
export type CategoryKind = 'expense' | 'income'

export interface Category {
  id: number
  name: string
  kind: CategoryKind
  icon: string | null
  color: string | null
  sort_order: number
  is_active: boolean
}

export interface Account {
  id: number
  name: string
  type: string
  initial_balance: string
  sort_order: number
  is_active: boolean
}

export interface TransactionCategoryRef {
  id: number
  name: string
  kind: CategoryKind
  icon: string | null
  color: string | null
}

export interface TransactionAccountRef {
  id: number
  name: string
  type: string
}

export type TransactionSource = 'manual' | 'wechat' | 'alipay'

export interface Transaction {
  id: number
  biz_date: string
  occurred_at: string
  amount: string
  amount_cents: number
  direction: Direction
  category_id: number
  category: TransactionCategoryRef | null
  account_id: number | null
  account: TransactionAccountRef | null
  payee: string | null
  note: string | null
  source: TransactionSource
  deleted_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface Summary {
  date_from: string
  date_to: string
  expense: { amount: string; count: number }
  income: { amount: string; count: number }
  net: string
  count: number
  average_expense: string
}

export interface DailyPoint {
  date: string
  expense: string
  income: string
}

export interface CategorySlice {
  category_id: number
  name: string
  icon: string | null
  color: string | null
  amount: string
  count: number
  share: number
}

export interface AccountSlice {
  account_id: number | null
  name: string
  type: string | null
  amount: string
  count: number
  share: number
}

export interface MonthPoint {
  month: string
  expense: string
  income: string
}

export interface DashboardData {
  summary: Summary
  daily: DailyPoint[]
  by_category: CategorySlice[]
  by_account: AccountSlice[]
  monthly: MonthPoint[]
}

export interface TransactionQuery {
  source?: TransactionSource
  date_from?: string
  date_to?: string
  category_id?: number
  account_id?: number
  direction?: Direction
  q?: string
  page?: number
  page_size?: number
  sort?: 'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc'
}

export interface TransactionPayload {
  amount: string
  category_id: number
  account_id?: number | null
  biz_date?: string
  occurred_at?: string
  payee?: string | null
  note?: string | null
}

export interface ImportSampleRow {
  line: number
  date: string
  amount: string
  direction: Direction
  payee: string | null
  note: string | null
  category_hint: string | null
  method: string | null
  external_id: string
}

export interface ImportResult {
  source: 'wechat' | 'alipay'
  encoding: string
  total_rows: number
  ready: number
  duplicates: number
  skipped: number
  skipped_reasons: { line: number; reason: string }[]
  totals: { expense: string; income: string }
  date_range: { from: string; to: string } | null
  sample: ImportSampleRow[]
  imported: number | null
}

export interface BudgetProgress {
  id: number
  month: string
  amount: string
  category_id: number | null
  category: { id: number; name: string; icon: string | null } | null
  spent: string
  remaining: string
  percent: number
  over: boolean
}

export interface BudgetStatus {
  month: string
  spent: string
  total: BudgetProgress | null
  categories: BudgetProgress[]
  has_budget: boolean
  over_budget: boolean
}
