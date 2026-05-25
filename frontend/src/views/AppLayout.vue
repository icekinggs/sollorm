<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import Button from 'primevue/button'
import Menu from 'primevue/menu'

const router = useRouter()
const auth = useAuthStore()
const { theme, toggle } = useTheme()
const userMenu = ref()

const userMenuItems = ref([
  {
    label: 'Perfil',
    icon: 'pi pi-user',
    disabled: true
  },
  {
    separator: true
  },
  {
    label: 'Sair',
    icon: 'pi pi-sign-out',
    command: () => {
      auth.logout()
      router.push('/login')
    }
  }
])

function toggleUserMenu(event) {
  userMenu.value.toggle(event)
}
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/dashboard" class="brand">
        <i class="pi pi-desktop"></i>
        <span>SolloRMM</span>
      </router-link>

      <nav class="nav-links">
        <router-link to="/dashboard" active-class="active">
          <i class="pi pi-th-large"></i>
          Dashboard
        </router-link>
        <router-link to="/alerts" active-class="active">
          <i class="pi pi-bell"></i>
          Alertas
        </router-link>
        <router-link to="/groups" active-class="active">
          <i class="pi pi-folder"></i>
          Grupos
        </router-link>
        <router-link to="/updates" active-class="active">
          <i class="pi pi-sync"></i>
          Atualizações
        </router-link>
        <router-link to="/tokens" active-class="active">
          <i class="pi pi-key"></i>
          Tokens
        </router-link>
      </nav>

      <div class="header-actions">
        <Button
          :icon="theme === 'dark' ? 'pi pi-sun' : 'pi pi-moon'"
          text
          rounded
          aria-label="Alternar tema"
          @click="toggle"
        />

        <Button
          icon="pi pi-user"
          text
          rounded
          :label="auth.user?.username"
          @click="toggleUserMenu"
          aria-haspopup="true"
          aria-controls="user-menu"
        />
        <Menu id="user-menu" ref="userMenu" :model="userMenuItems" :popup="true" />
      </div>
    </div>
  </header>

  <main class="page-container">
    <router-view />
  </main>
</template>

<style scoped>
.app-header {
  background: var(--p-content-background);
  border-bottom: 1px solid var(--p-content-border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 2rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 1.1rem;
  color: var(--p-text-color);
  text-decoration: none;
}

.brand i {
  color: var(--p-primary-color);
  font-size: 1.3rem;
}

.brand:hover {
  text-decoration: none;
}

.nav-links {
  display: flex;
  gap: 0.5rem;
  flex: 1;
}

.nav-links a {
  padding: 0.5rem 0.85rem;
  border-radius: 6px;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  transition: all 0.15s ease;
}

.nav-links a:hover {
  background: var(--p-surface-100);
  color: var(--p-text-color);
  text-decoration: none;
}

.sollorm-dark .nav-links a:hover {
  background: var(--p-surface-800);
}

.nav-links a.active {
  background: var(--p-primary-50);
  color: var(--p-primary-700);
}

.sollorm-dark .nav-links a.active {
  background: var(--p-primary-900);
  color: var(--p-primary-300);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
</style>
