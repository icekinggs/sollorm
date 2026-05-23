import api from './client'

export const agentTokensApi = {
  list() {
    return api.get('/agent-tokens')
  },

  get(id) {
    return api.get(`/agent-tokens/${id}`)
  },

  create({ name, platform_hint, expires_in_days }) {
    return api.post('/agent-tokens', {
      name,
      platform_hint,
      expires_in_days
    })
  },

  revoke(id) {
    return api.post(`/agent-tokens/${id}/revoke`)
  },

  delete(id) {
    return api.delete(`/agent-tokens/${id}`)
  }
}
