import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('sollorm_token') || null)
  const user = ref(
    localStorage.getItem('sollorm_user')
      ? JSON.parse(localStorage.getItem('sollorm_user'))
      : null
  )

  const isAuthenticated = computed(() => !!token.value)
  const isSuperuser = computed(() => user.value?.is_superuser === true)

  async function login(username, password) {
    const response = await authApi.login(username, password)
    const data = response.data

    token.value = data.access_token
    user.value = data.user

    localStorage.setItem('sollorm_token', data.access_token)
    localStorage.setItem('sollorm_user', JSON.stringify(data.user))

    return data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('sollorm_token')
    localStorage.removeItem('sollorm_user')
  }

  async function fetchMe() {
    try {
      const response = await authApi.me()
      user.value = response.data
      localStorage.setItem('sollorm_user', JSON.stringify(response.data))
      return response.data
    } catch (err) {
      logout()
      throw err
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    isSuperuser,
    login,
    logout,
    fetchMe
  }
})
