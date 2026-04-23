<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

interface Props {
  show: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

// Don't destructure props - use props.show directly for reactivity
const props = withDefaults(defineProps<Props>(), {
  confirmText: 'Confirm',
  cancelText: 'Cancel',
  danger: false
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
}

const handleBackdropClick = () => {
  emit('cancel')
}

// Keyboard accessibility
const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.show) return
  if (e.key === 'Escape') {
    handleCancel()
  } else if (e.key === 'Enter') {
    handleConfirm()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="props.show"
      class="dialog-backdrop"
      @click="handleBackdropClick"
    >
      <div class="dialog" @click.stop>
        <h3 class="dialog-title">{{ props.title }}</h3>
        <p class="dialog-message">{{ props.message }}</p>
        <div class="dialog-actions" :class="{ 'justify-center': !props.cancelText }">
          <button
            v-if="props.cancelText"
            class="btn btn-secondary"
            @click="handleCancel"
          >
            {{ props.cancelText }}
          </button>
          <button
            class="btn"
            :class="props.danger ? 'btn-danger' : 'btn-primary'"
            @click="handleConfirm"
          >
            {{ props.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgb(0 0 0 / 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9998;
}

.dialog {
  background: white;
  border-radius: 0.75rem;
  padding: 1.5rem;
  min-width: 320px;
  max-width: 480px;
  box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1);
}

.dark .dialog {
  background: rgb(31 41 55);
}

.dialog-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.dialog-message {
  color: rgb(107 114 128);
  margin-bottom: 1.5rem;
}

.dark .dialog-message {
  color: rgb(156 163 175);
}

.dialog-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.justify-center {
  justify-content: center;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
}

.btn-primary {
  background: rgb(59 130 246);
  color: white;
}

@media (hover: hover) {
.btn-primary:hover {
  background: rgb(37 99 235);
}
}

.btn-secondary {
  background: rgb(229 231 235);
  color: rgb(17 24 39);
}

.dark .btn-secondary {
  background: rgb(75 85 99);
  color: rgb(243 244 246);
}

@media (hover: hover) {
.btn-secondary:hover {
  background: rgb(209 213 209);
}

.dark .btn-secondary:hover {
  background: rgb(107 114 128);
}
}

.btn-danger {
  background: rgb(220 38 38);
  color: white;
}

@media (hover: hover) {
.btn-danger:hover {
  background: rgb(185 28 28);
}
}
</style>