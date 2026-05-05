<!-- vibe2crazy/frontend/src/components/UpdateToast.vue -->
<template>
  <Transition name="slide-down">
    <div v-if="visible" class="update-toast">
      <div class="toast-content">
        <span class="toast-icon">📦</span>
        <span class="toast-message">
          New version v{{ version }} available (current: v{{ currentVersion }}).
          <button class="view-btn" @click="viewDetails">View details</button>
        </span>
      </div>
      <button class="dismiss-btn" @click="dismiss">×</button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
interface Props {
  visible: boolean
  version: string
  currentVersion: string
}

defineProps<Props>()
const emit = defineEmits(['view-details', 'dismiss'])

function viewDetails() {
  emit('view-details')
}

function dismiss() {
  emit('dismiss')
}
</script>

<style scoped>
.update-toast {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: var(--accent-color, #3b82f6);
  color: white;
  padding: 0.75rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 999;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.toast-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toast-icon {
  font-size: 1.25rem;
}

.toast-message {
  font-size: 0.875rem;
}

.view-btn {
  background: none;
  border: none;
  color: white;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
  margin-left: 0.25rem;
}

.dismiss-btn {
  background: none;
  border: none;
  color: white;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>