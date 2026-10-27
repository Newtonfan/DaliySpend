import type {
  Account,
  Category,
  DashboardData,
  ImportResult,
  Page,
  PublicSettings,
  Summary,
  Transaction,
  TransactionPayload,
  TransactionQuery,
  User,
} from '@/types'
import { http } from './client'

export interface MeResponse {
  user: User
  settings: PublicSettings
}

export const authApi = {
  async me(): Promise<MeResponse> {
    const { data } = await http.get<MeResponse>('/auth/me')
    return data
  },
  async login(email: string, password: string, remember = false): Promise<MeResponse> {
    const { data } = await http.post<MeResponse>('/auth/login', { email, password, remember })
    return data
  },
  async register(email: string, password: string, displayName?: string): Promise<MeResponse> {
    const { data } = await http.post<MeResponse>('/auth/register', {
      email,
      password,
      display_name: displayName ?? null,
    })
    return data
  },
  async logout(): Promise<void> {
    await http.post('/auth/logout')
  },
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await http.post('/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}

export const categoriesApi = {
  async list(kind?: 'expense' | 'income'): Promise<Category[]> {
    const { data } = await http.get<{ items: Category[] }>('/categories', {
      params: kind ? { kind } : undefined,
    })
    return data.items
  },
  async create(payload: Partial<Category> & { name: string }): Promise<Category> {
    const { data } = await http.post<{ category: Category }>('/categories', payload)
    return data.category
  },
  async update(id: number, payload: Partial<Category>): Promise<Category> {
    const { data } = await http.put<{ category: Category }>(`/categories/${id}`, payload)
    return data.category
  },
  async remove(id: number): Promise<void> {
    await http.delete(`/categories/${id}`)
  },
}

export const accountsApi = {
  async list(): Promise<Account[]> {
    const { data } = await http.get<{ items: Account[] }>('/accounts')
    return data.items
  },
  async create(payload: { name: string; type?: string; initial_balance?: string }): Promise<Account> {
    const { data } = await http.post<{ account: Account }>('/accounts', payload)
    return data.account
  },
  async update(id: number, payload: Record<string, unknown>): Promise<Account> {
    const { data } = await http.put<{ account: Account }>(`/accounts/${id}`, payload)
    return data.account
  },
  async remove(id: number): Promise<void> {
    await http.delete(`/accounts/${id}`)
  },
}

export const transactionsApi = {
  async list(query: TransactionQuery = {}): Promise<Page<Transaction>> {
    const { data } = await http.get<Page<Transaction>>('/transactions', { params: query })
    return data
  },
  async get(id: number): Promise<Transaction> {
    const { data } = await http.get<{ transaction: Transaction }>(`/transactions/${id}`)
    return data.transaction
  },
  async create(payload: TransactionPayload): Promise<Transaction> {
    const { data } = await http.post<{ transaction: Transaction }>('/transactions', payload)
    return data.transaction
  },
  async update(id: number, payload: Partial<TransactionPayload>): Promise<Transaction> {
    const { data } = await http.put<{ transaction: Transaction }>(`/transactions/${id}`, payload)
    return data.transaction
  },
  async remove(id: number): Promise<void> {
    await http.delete(`/transactions/${id}`)
  },
}

export interface DashboardParams {
  date_from?: string
  date_to?: string
  months?: number
  direction?: 'out' | 'in'
}

export const statsApi = {
  async dashboard(params: DashboardParams = {}): Promise<DashboardData> {
    const { data } = await http.get<DashboardData>('/stats/dashboard', { params })
    return data
  },
  async summary(params: DashboardParams = {}): Promise<Summary> {
    const { data } = await http.get<Summary>('/stats/summary', { params })
    return data
  },
}

export interface ImportOptions {
  default_category_id?: number | null
  default_account_id?: number | null
}

export const importsApi = {
  /** Uploads a statement; `dryRun` previews the result instead of writing it. */
  async upload(file: File, dryRun: boolean, options: ImportOptions = {}): Promise<ImportResult> {
    const form = new FormData()
    form.append('file', file)
    form.append('dry_run', dryRun ? 'true' : 'false')
    if (options.default_category_id) {
      form.append('default_category_id', String(options.default_category_id))
    }
    if (options.default_account_id) {
      form.append('default_account_id', String(options.default_account_id))
    }
    const { data } = await http.post<ImportResult>('/imports/csv', form)
    return data
  },
}

export function exportCsvUrl(params: { date_from?: string; date_to?: string } = {}): string {
  const search = new URLSearchParams()
  if (params.date_from) search.set('date_from', params.date_from)
  if (params.date_to) search.set('date_to', params.date_to)
  const query = search.toString()
  return `/api/exports/transactions.csv${query ? `?${query}` : ''}`
}
