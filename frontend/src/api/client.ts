import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const UNSAFE_METHODS = new Set(['post', 'put', 'patch', 'delete'])
const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/logout']

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown }
}

type RetriableConfig = InternalAxiosRequestConfig & { _csrfRetried?: boolean }

export const http = axios.create({
  baseURL: '/api',
  timeout: 20000,
  withCredentials: true,
})

let csrfToken: string | null = null

export function resetCsrfToken(): void {
  csrfToken = null
}

async function fetchCsrfToken(): Promise<string> {
  const { data } = await axios.get<{ csrf_token: string }>('/api/auth/csrf', {
    timeout: 20000,
    withCredentials: true,
  })
  csrfToken = data.csrf_token
  return csrfToken
}

http.interceptors.request.use(async (config) => {
  const method = (config.method ?? 'get').toLowerCase()
  if (UNSAFE_METHODS.has(method)) {
    config.headers.set('X-CSRFToken', csrfToken ?? (await fetchCsrfToken()))
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    // Login/logout rotate the server session, which invalidates the CSRF token.
    const url = response.config.url ?? ''
    if (AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint))) {
      resetCsrfToken()
    }
    return response
  },
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined
    if (
      error.response?.status === 400 &&
      codeOf(error) === 'csrf_failed' &&
      config &&
      !config._csrfRetried
    ) {
      config._csrfRetried = true
      resetCsrfToken()
      return http.request(config)
    }

    if (error.response?.status === 401 && !(config?.url ?? '').includes('/auth/')) {
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }
    return Promise.reject(error)
  },
)

export function codeOf(error: unknown): string | null {
  const body = (error as AxiosError<ApiErrorBody>).response?.data
  return body?.error?.code ?? null
}

export function messageOf(error: unknown): string {
  const axiosError = error as AxiosError<ApiErrorBody>
  const body = axiosError.response?.data
  if (body?.error?.message) {
    const details = body.error.details
    if (Array.isArray(details) && details.length > 0) {
      const first = details[0] as { loc?: string[]; msg?: string }
      if (first?.msg) {
        return `${body.error.message}：${first.loc?.join('.') ?? ''} ${first.msg}`.trim()
      }
    }
    return body.error.message
  }
  if (axiosError.code === 'ECONNABORTED') return '请求超时，请稍后重试'
  return axiosError.message || '请求失败'
}
