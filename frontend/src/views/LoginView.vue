<script setup lang="ts">
import { NButton, NCard, NForm, NFormItem, NInput, NTabPane, NTabs, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { messageOf } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const message = useMessage()

const tab = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const displayName = ref('')
const loading = ref(false)

const registrationEnabled = computed(() => auth.settings?.registration_enabled ?? true)
const passwordHint = computed(() => `至少 ${auth.settings?.password_min_length ?? 8} 位`)

async function submit() {
  if (!email.value.trim() || !password.value) {
    message.warning('请填写邮箱和密码')
    return
  }
  loading.value = true
  try {
    if (tab.value === 'login') {
      await auth.login(email.value.trim(), password.value)
    } else {
      await auth.register(email.value.trim(), password.value, displayName.value.trim() || undefined)
    }
    message.success(tab.value === 'login' ? '欢迎回来' : '账号已创建')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (error) {
    message.error(messageOf(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <n-card class="login-card" :bordered="false">
      <div class="brand">
        <span class="brand-mark">¥</span>
        <div>
          <h1>每日账本</h1>
          <p>看清每一笔支出，管住每个月的钱包</p>
        </div>
      </div>

      <n-tabs v-model:value="tab" type="segment" animated>
        <n-tab-pane name="login" tab="登录">
          <n-form label-placement="top" @keyup.enter="submit">
            <n-form-item label="邮箱">
              <n-input v-model:value="email" placeholder="you@example.com" autocomplete="username" />
            </n-form-item>
            <n-form-item label="密码">
              <n-input
                v-model:value="password"
                type="password"
                show-password-on="click"
                placeholder="请输入密码"
                autocomplete="current-password"
              />
            </n-form-item>
            <n-button type="primary" block size="large" :loading="loading" @click="submit">
              登录
            </n-button>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="register" tab="注册" :disabled="!registrationEnabled">
          <n-form label-placement="top" @keyup.enter="submit">
            <n-form-item label="邮箱">
              <n-input v-model:value="email" placeholder="you@example.com" autocomplete="username" />
            </n-form-item>
            <n-form-item label="昵称" extra="可留空，默认使用邮箱前缀">
              <n-input v-model:value="displayName" placeholder="怎么称呼你" maxlength="80" />
            </n-form-item>
            <n-form-item label="密码" :feedback="passwordHint">
              <n-input
                v-model:value="password"
                type="password"
                show-password-on="click"
                placeholder="设置登录密码"
                autocomplete="new-password"
              />
            </n-form-item>
            <n-button type="primary" block size="large" :loading="loading" @click="submit">
              创建账号
            </n-button>
          </n-form>
          <p v-if="!registrationEnabled" class="closed-tip">管理员已关闭注册，请联系管理员开通。</p>
        </n-tab-pane>
      </n-tabs>

      <p class="foot-tip">账号仅在本地数据库中保存，密码使用加盐哈希存储。</p>
    </n-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: radial-gradient(1200px 600px at 10% -10%, #e0e7ff 0%, #f5f6fa 55%, #f5f6fa 100%);
}

.login-card {
  width: 100%;
  max-width: 420px;
  border-radius: 18px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.12);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
}

h1 {
  margin: 0;
  font-size: 20px;
}

p {
  margin: 2px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.foot-tip {
  margin-top: 18px;
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
}

.closed-tip {
  margin-top: 12px;
  color: #b45309;
  font-size: 13px;
}
</style>
