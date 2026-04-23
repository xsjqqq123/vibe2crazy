import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeName = 'light' | 'dark' | 'green' | 'parchment'

export const useMainStore = defineStore('main', () => {
  // Theme
  const theme = ref<ThemeName>('dark')
  const themeOrder: ThemeName[] = ['light', 'dark', 'green', 'parchment']
  const validThemes: ThemeName[] = ['light', 'dark', 'green', 'parchment']

  // Keep isDark for backward compatibility during transition
  const isDark = ref(true)

  const setTheme = (newTheme: ThemeName) => {
    theme.value = newTheme
    isDark.value = newTheme === 'dark'

    // Remove all theme classes
    document.documentElement.classList.remove('theme-dark', 'theme-light', 'theme-green', 'theme-parchment', 'dark')
    // Add new theme class
    document.documentElement.classList.add(`theme-${newTheme}`)
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark')
    }
    localStorage.setItem('theme', newTheme)
  }

  const cycleTheme = () => {
    const currentIndex = themeOrder.indexOf(theme.value)
    const nextIndex = (currentIndex + 1) % themeOrder.length
    setTheme(themeOrder[nextIndex])
  }

  const toggleTheme = () => {
    cycleTheme()
  }

  const initTheme = () => {
    const saved = localStorage.getItem('theme') as ThemeName | null
    const initialTheme = saved && validThemes.includes(saved) ? saved : 'dark'
    setTheme(initialTheme)
  }

  // Current project/task
  const currentProject = ref<any>(null)
  const currentTask = ref<any>(null)

  const setCurrentProject = (project: any) => {
    currentProject.value = project
  }

  const setCurrentTask = (task: any) => {
    currentTask.value = task
  }

  return {
    theme,
    isDark,
    cycleTheme,
    toggleTheme,
    initTheme,
    currentProject,
    currentTask,
    setCurrentProject,
    setCurrentTask
  }
})