<script setup lang="ts">
import { NAvatar, NButton, NDropdown, NLayout, NLayoutContent, NLayoutHeader, NMenu, NSpace } from 'naive-ui'
import { computed, h } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const menuOptions = [
  { label: () => h(RouterLink, { to: '/' }, { default: () => '概览' }), key: 'dashboard' },
  { label: () => h(RouterLink, { to: '/transactions' }, { default: () => '流水' }), key: 'transactions' },
  { label: () => h(RouterLink, { to: '/import' }, { default: () => '导入' }), key: 'import' },
  { label: () => h(RouterLink, { to: '/settings' }, { default: () => '设置' }), key: 'settings' },
]

const activeKey = computed(() => (route.name as string) ?? 'dashboard')

const userOptions = [
  { label: '分类与账户', key: 'settings' },
  { label: '退出登录', key: 'logout' },
]

async function onUserAction(key: string) {
  if (key === 'settings') {
    router.push('/settings')
    return
  }
  if (key === 'logout') {
    await auth.logout()
    router.push({ name: 'login' })
  }
}
</script>

<template>
  <n-layout position="absolute">
    <n-layout-header bordered style="height: 60px; padding: 0 24px; background: #fff">
      <div class="header">
        <div class="brand">
          <span class="brand-mark">¥</span>
          <span class="brand-name">每日账本</span>
        </div>
        <n-menu mode="horizontal" :options="menuOptions" :value="activeKey" class="nav" />
        <n-dropdown :options="userOptions" trigger="click" @select="onUserAction">
          <n-space align="center" :size="8" style="cursor: pointer">
            <n-avatar round size="small" style="background: #4f46e5">
              {{ auth.displayName.slice(0, 1) || 'U' }}
            </n-avatar>
            <span class="user-name">{{ auth.displayName }}</span>
          </n-space>
        </n-dropdown>
      </div>
    </n-layout-header>

    <n-layout-content style="padding: 24px">
      <div class="page">
        <router-view />
      </div>
    </n-layout-content>
  </n-layout>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 32px;
  height: 60px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 17px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: #fff;
  font-size: 15px;
}

.nav {
  flex: 1;
}

.user-name {
  font-size: 14px;
  color: #4b5563;
}

.page {
  max-width: 1180px;
  margin: 0 auto;
}
</style>
