import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '@/api'
import type { PublicSettings, User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const settings = ref<PublicSettings | null>(null)
  const ready = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const displayName = computed(() => user.value?.display_name ?? '')

  async function loadSession(): Promise<void> {
    try {
      const data = await authApi.me()
      user.value = data.user
      settings.value = data.settings
    } catch {
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function login(email: string, password: string): Promise<void> {
    const data = await authApi.login(email, password)
    user.value = data.user
    settings.value = data.settings
  }

  async function register(email: string, password: string, displayName?: string): Promise<void> {
    const data = await authApi.register(email, password, displayName)
    user.value = data.user
    settings.value = data.settings
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      user.value = null
    }
  }

  return { user, settings, ready, isAuthenticated, displayName, loadSession, login, register, logout }
})
