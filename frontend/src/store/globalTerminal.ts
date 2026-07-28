// frontend/src/store/globalTerminal.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'v2c-global-terminal'

interface Position {
  x: number
  y: number
}

interface Size {
  width: number
  height: number
}

export const useGlobalTerminalStore = defineStore('globalTerminal', () => {
  const visible = ref(false)
  const position = ref<Position>({ x: 0, y: 0 })
  const size = ref<Size>({ width: 0, height: 0 })
  const activeInstance = ref(0)

  // Fixed initial size
  const INITIAL_WIDTH = 800
  const INITIAL_HEIGHT = 500

  const getInitialPosition = (): Position => ({
    x: (window.innerWidth - INITIAL_WIDTH) / 2,
    y: (window.innerHeight - INITIAL_HEIGHT) / 2
  })

  const getInitialSize = (): Size => ({
    width: INITIAL_WIDTH,
    height: INITIAL_HEIGHT
  })

  const toggle = () => {
    visible.value = !visible.value
  }

  const show = () => {
    visible.value = true
  }

  const hide = () => {
    visible.value = false
  }

  const setPosition = (pos: Position) => {
    position.value = pos
  }

  const setSize = (s: Size) => {
    size.value = s
  }

  const setActiveInstance = (index: number) => {
    activeInstance.value = index
  }

  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.position) position.value = parsed.position
        if (parsed.size) size.value = parsed.size
        if (typeof parsed.activeInstance === 'number') activeInstance.value = parsed.activeInstance
      }
    } catch {
      // Ignore parse errors
    }

    // Set defaults if not loaded
    if (position.value.x === 0 && position.value.y === 0) {
      position.value = getInitialPosition()
    }
    if (size.value.width === 0 && size.value.height === 0) {
      size.value = getInitialSize()
    }
  }

  const saveToStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        position: position.value,
        size: size.value,
        activeInstance: activeInstance.value
      }))
    } catch {
      // Ignore storage errors
    }
  }

  return {
    visible,
    position,
    size,
    activeInstance,
    toggle,
    show,
    hide,
    setPosition,
    setSize,
    setActiveInstance,
    loadFromStorage,
    saveToStorage
  }
})
