import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresGuest: true }
  },
  {
    path: '/',
    component: () => import('@/views/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue')
      },
      {
        path: 'agents/:id',
        name: 'agent-detail',
        component: () => import('@/views/AgentDetailView.vue'),
        props: true
      },
      {
        path: 'tokens',
        name: 'tokens',
        component: () => import('@/views/TokensView.vue')
      },
      {
        path: 'groups',
        name: 'groups',
        component: () => import('@/views/GroupsView.vue')
      },
      {
        path: 'alerts',
        name: 'alerts',
        component: () => import('@/views/AlertsView.vue')
      },
      {
        path: 'updates',
        name: 'updates',
        component: () => import('@/views/UpdatesView.vue')
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  if (to.meta.requiresGuest && auth.isAuthenticated) {
    return next({ name: 'dashboard' })
  }

  next()
})

export default router
