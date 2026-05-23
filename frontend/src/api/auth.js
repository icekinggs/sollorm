import api from './client'

export const authApi = {
  login(username, password) {
    return api.post('/auth/login', { username, password })
  },

  me() {
    return api.get('/auth/me')
  }
}
