<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { theme, toggle } = useTheme()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')

async function handleSubmit() {
  errorMessage.value = ''

  if (!username.value || !password.value) {
    errorMessage.value = 'Preencha usuário e senha'
    return
  }

  loading.value = true
  try {
    await auth.login(username.value, password.value)
    const redirect = route.query.redirect || '/dashboard'
    router.push(redirect)
  } catch (err) {
    if (err.response?.status === 401) {
      errorMessage.value = 'Usuário ou senha inválidos'
    } else if (err.code === 'ERR_NETWORK') {
      errorMessage.value = 'Não foi possível conectar ao servidor'
    } else {
      errorMessage.value = err.response?.data?.detail || 'Erro ao fazer login'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <Button
      :icon="theme === 'dark' ? 'pi pi-sun' : 'pi pi-moon'"
      text
      rounded
      class="theme-toggle"
      aria-label="Alternar tema"
      @click="toggle"
    />

    <div class="login-card">
      <div class="login-brand">
        <div class="logo-circle">
          <i class="pi pi-desktop"></i>
        </div>
        <h1>SolloRMM</h1>
        <p class="text-muted">Faça login para continuar</p>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <Message v-if="errorMessage" severity="error" :closable="false">
          {{ errorMessage }}
        </Message>

        <div class="field">
          <label for="username">Usuário</label>
          <InputText
            id="username"
            v-model="username"
            placeholder="admin"
            autocomplete="username"
            autofocus
            :disabled="loading"
            fluid
          />
        </div>

        <div class="field">
          <label for="password">Senha</label>
          <Password
            id="password"
            v-model="password"
            placeholder="••••••••"
            :feedback="false"
            toggle-mask
            autocomplete="current-password"
            :disabled="loading"
            fluid
            input-class="w-full"
          />
        </div>

        <Button
          type="submit"
          label="Entrar"
          icon="pi pi-sign-in"
          :loading="loading"
          fluid
        />
      </form>

      <p class="login-footer text-muted">
        SolloRMM v0.2 · Em desenvolvimento
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: var(--p-surface-50);
  position: relative;
}

.sollorm-dark .login-page {
  background: var(--p-surface-950);
}

.theme-toggle {
  position: absolute !important;
  top: 1rem;
  right: 1rem;
}

.login-card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 12px;
  padding: 2.5rem;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.login-brand {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-circle {
  width: 56px;
  height: 56px;
  margin: 0 auto 1rem;
  border-radius: 50%;
  background: var(--p-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-circle i {
  color: white;
  font-size: 1.4rem;
}

.login-brand h1 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--p-text-color);
}

.login-footer {
  margin-top: 2rem;
  text-align: center;
  font-size: 0.75rem;
}

:deep(.p-password) {
  width: 100%;
}

:deep(.p-password input) {
  width: 100%;
}
</style>
