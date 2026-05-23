import { formatDistanceToNow, format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

export function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

export function formatUptime(seconds) {
  if (!seconds) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)

  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

export function formatRelativeDate(dateStr) {
  if (!dateStr) return 'nunca'
  try {
    return formatDistanceToNow(new Date(dateStr), {
      addSuffix: true,
      locale: ptBR
    })
  } catch {
    return '—'
  }
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "dd/MM/yyyy HH:mm:ss", { locale: ptBR })
  } catch {
    return '—'
  }
}

export function usageColorClass(percent) {
  if (percent >= 85) return 'high'
  if (percent >= 60) return 'medium'
  return 'low'
}
