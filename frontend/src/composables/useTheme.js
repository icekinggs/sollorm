import { ref, watch } from 'vue'

const STORAGE_KEY = 'sollorm_theme'
const DARK_CLASS = 'sollorm-dark'

function detectInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  // Respeita preferência do sistema na primeira vez
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

const theme = ref(detectInitialTheme())

function applyTheme(value) {
  const html = document.documentElement
  if (value === 'dark') {
    html.classList.add(DARK_CLASS)
  } else {
    html.classList.remove(DARK_CLASS)
  }
}

applyTheme(theme.value)

watch(theme, (newValue) => {
  applyTheme(newValue)
  localStorage.setItem(STORAGE_KEY, newValue)
})

export function useTheme() {
  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return {
    theme,
    toggle
  }
}
