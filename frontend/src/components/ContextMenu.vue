<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'

export interface MenuItem {
  label: string
  icon: string
  action: () => void
  disabled?: boolean
  danger?: boolean
}

interface Props {
  show: boolean
  x: number
  y: number
  items: MenuItem[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const menuRef = ref<HTMLElement>()

const handleClickOutside = (e: MouseEvent) => {
  if (!props.show) return
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    emit('close')
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!props.show) return
  if (e.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})

const position = ref({ left: props.x, top: props.y })

watch(() => props.show, async (show) => {
  if (show) {
    await new Promise(resolve => setTimeout(resolve, 0))
    updatePosition()
  }
})

// Watch x and y props to update position when menu is already open
watch(() => [props.x, props.y], async () => {
  if (props.show) {
    updatePosition()
  }
})

const updatePosition = async () => {
  await new Promise(resolve => setTimeout(resolve, 0))
  if (menuRef.value) {
    const rect = menuRef.value.getBoundingClientRect()
    let { x, y } = { x: props.x, y: props.y }
    if (x + rect.width > window.innerWidth) {
      x = window.innerWidth - rect.width - 8
    }
    if (y + rect.height > window.innerHeight) {
      y = window.innerHeight - rect.height - 8
    }
    position.value = { left: x, top: y }
  }
}

const handleItemClick = (item: MenuItem) => {
  console.log('[ContextMenu] Item clicked:', item.label)
  if (item.disabled) {
    console.log('[ContextMenu] Item is disabled, ignoring')
    return
  }
  console.log('[ContextMenu] Calling item.action()...')
  item.action()
  console.log('[ContextMenu] action() completed, emitting close')
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      ref="menuRef"
      class="context-menu"
      :style="{ left: `${position.left}px`, top: `${position.top}px` }"
    >
      <div
        v-for="(item, index) in items"
        :key="index"
        class="context-menu-item"
        :class="{ 'disabled': item.disabled, 'danger': item.danger }"
        @click.stop="handleItemClick(item)"
      >
        <span class="menu-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.context-menu {
  position: fixed;
  background: white;
  border: 1px solid rgb(229 231 235);
  border-radius: 0.5rem;
  box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  padding: 0.25rem;
  min-width: 160px;
  z-index: 9999;
}

.dark .context-menu {
  background: rgb(31 41 55);
  border-color: rgb(55 65 81);
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-radius: 0.375rem;
  user-select: none;
}

.context-menu-item:hover:not(.disabled) {
  background: rgb(243 244 246);
}

.dark .context-menu-item:hover:not(.disabled) {
  background: rgb(55 65 81);
}

.context-menu-item.danger {
  color: rgb(220 38 38);
}

.dark .context-menu-item.danger {
  color: rgb(248 113 113);
}

.context-menu-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.menu-icon {
  min-width: 1.25rem;
}
</style>