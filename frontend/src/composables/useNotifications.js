import { onUnmounted } from 'vue'

// Module-level singleton — one WebSocket shared by all subscribers.
let _ws = null
let _reconnectTimer = null
const _handlers = new Set()

function _wsUrl() {
  const token = localStorage.getItem('sollorm_token')
  if (!token) return null
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/notifications?token=${encodeURIComponent(token)}`
}

function _connect() {
  if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return
  const url = _wsUrl()
  if (!url) return

  _ws = new WebSocket(url)

  _ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      _handlers.forEach(h => h(msg))
    } catch {}
  }

  _ws.onclose = () => {
    _ws = null
    if (_handlers.size > 0) {
      _reconnectTimer = setTimeout(_connect, 3000)
    }
  }

  _ws.onerror = () => {
    _ws?.close()
  }
}

function _disconnect() {
  clearTimeout(_reconnectTimer)
  _reconnectTimer = null
  if (_ws) {
    _ws.onclose = null
    _ws.close()
    _ws = null
  }
}

/**
 * Subscribe to real-time backend events for the lifetime of the calling component.
 * handler(msg) is called with every event object. Automatically unsubscribes on unmount.
 *
 * Event types:
 *   { type: 'agent_online',    agent_id }
 *   { type: 'agent_offline',   agent_id }
 *   { type: 'agent_heartbeat', agent_id, hostname, cpu_usage_percent,
 *                               ram_usage_percent, disk_usage_percent,
 *                               uptime_seconds, last_seen }
 */
export function useNotifications(handler) {
  _handlers.add(handler)
  _connect()

  onUnmounted(() => {
    _handlers.delete(handler)
    if (_handlers.size === 0) {
      _disconnect()
    }
  })
}
