import { onMounted, toRefs } from 'vue'
import { useMainStore } from '@/store'

export function useTheme() {
  const store = useMainStore()

  onMounted(() => {
    store.initTheme()
  })

  const cycleTheme = () => {
    store.cycleTheme()
  }

  const toggleTheme = () => {
    store.toggleTheme()
  }

  // Use toRefs to maintain reactivity when destructuring
  return {
    ...toRefs(store),
    cycleTheme,
    toggleTheme
  }
}
