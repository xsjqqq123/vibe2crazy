<script setup lang="ts">
/**
 * Lists the tasks defined in `.vscode/tasks.json` with copy buttons.
 *
 * Shown automatically when that file is opened in the code editor. Each row
 * offers the vtr invocation (which resolves variables and dependsOn the way
 * VS Code does) and the underlying shell command.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { parseTasksJson } from '@/utils/vscodeTasks'

interface Props {
  show: boolean
  filePath: string
  content: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const parsed = computed(() => parseTasksJson(props.content))

// Which button was last copied, so it can confirm itself. Keyed by a stable
// per-row id rather than the task label, which need not be unique.
const copiedKey = ref<string | null>(null)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

const copy = async (key: string, text: string) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // Older/insecure contexts have no async clipboard.
    const area = document.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.left = '-9999px'
    document.body.appendChild(area)
    area.select()
    try {
      document.execCommand('copy')
    } finally {
      document.body.removeChild(area)
    }
  }

  copiedKey.value = key
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copiedKey.value = null
    copiedTimer = null
  }, 1200)
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.show) return
  if (e.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', handleKeyDown))
onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
  if (copiedTimer) clearTimeout(copiedTimer)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="vt-overlay" role="dialog" @click.self="emit('close')">
        <div class="vt-panel card">
          <!-- Header -->
          <div class="vt-header">
            <div class="min-w-0">
              <h3 class="text-base font-semibold text-main">VS Code Tasks</h3>
              <p class="text-xs text-muted truncate" :title="filePath">{{ filePath }}</p>
            </div>
            <button class="vt-close" title="Close (ESC)" @click="emit('close')">✕</button>
          </div>

          <!-- Body -->
          <div class="vt-body">
            <p v-if="parsed.error" class="vt-notice vt-notice-error">{{ parsed.error }}</p>

            <p v-else-if="parsed.tasks.length === 0" class="vt-notice">
              No tasks defined in this file.
            </p>

            <template v-else>
              <p class="vt-hint">
                Copy a command and paste it into the terminal. <code>vtr</code> resolves
                <code>${...}</code> variables and <code>dependsOn</code> itself.
              </p>

              <div v-for="(task, index) in parsed.tasks" :key="index" class="vt-task">
                <div class="vt-task-head">
                  <span class="vt-label" :title="task.label">{{ task.label }}</span>
                  <span v-if="task.group" class="vt-badge">{{ task.group }}</span>
                  <span v-if="task.isDefaultBuild" class="vt-badge">default</span>
                  <span v-if="task.isBackground" class="vt-badge">background</span>
                </div>

                <p v-if="task.detail" class="vt-detail">{{ task.detail }}</p>

                <!-- vtr command -->
                <div class="vt-cmd">
                  <code class="vt-code">{{ task.vtrCommand }}</code>
                  <button
                    class="vt-copy"
                    :class="{ 'is-copied': copiedKey === `${index}-vtr` }"
                    :title="`Copy ${task.vtrCommand}`"
                    @click="copy(`${index}-vtr`, task.vtrCommand)"
                  >{{ copiedKey === `${index}-vtr` ? '✓ Copied' : 'Copy' }}</button>
                </div>

                <!-- underlying command -->
                <div v-if="task.rawCommand" class="vt-cmd vt-cmd-raw">
                  <code class="vt-code" :title="task.rawCommand">└ {{ task.rawCommand }}</code>
                  <button
                    class="vt-copy"
                    :class="{ 'is-copied': copiedKey === `${index}-raw` }"
                    :title="`Copy ${task.rawCommand}`"
                    @click="copy(`${index}-raw`, task.rawCommand!)"
                  >{{ copiedKey === `${index}-raw` ? '✓ Copied' : 'Copy' }}</button>
                </div>

                <p v-if="task.rawCommand && task.hasVariables" class="vt-warn">
                  Contains <code>${...}</code> variables — a bare shell will not expand them.
                  Use the <code>vtr</code> command, or substitute them yourself.
                </p>

                <p v-if="task.inputIds.length" class="vt-warn">
                  Needs input
                  <code v-for="id in task.inputIds" :key="id">VTR_INPUT_{{ id }}</code>
                  — set it as an environment variable before running.
                </p>

                <p v-if="task.dependsOn.length" class="vt-meta">
                  Runs after: {{ task.dependsOn.join(', ') }}
                </p>
                <p v-if="task.cwd" class="vt-meta">Working directory: {{ task.cwd }}</p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vt-overlay {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.5);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.vt-panel {
  width: 100%;
  max-width: 46rem;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--bg-primary);
}

.vt-header {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

.vt-close {
  margin-left: auto;
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  line-height: 1;
}

.vt-close:hover {
  background-color: rgb(220 38 38);
  border-color: rgb(220 38 38);
  color: #fff;
}

.vt-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.75rem 1rem 1rem;
}

.vt-notice {
  padding: 1.5rem 0;
  text-align: center;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.vt-notice-error {
  color: #dc2626;
}

.vt-hint {
  margin-bottom: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.vt-task {
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background-color: var(--bg-secondary);
}

.vt-task + .vt-task {
  margin-top: 0.5rem;
}

.vt-task-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.vt-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.vt-badge {
  flex-shrink: 0;
  padding: 0 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.625rem;
  line-height: 1.5;
  background-color: var(--bg-tertiary);
  color: var(--text-muted);
}

.vt-detail {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.vt-cmd {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.vt-code {
  flex: 1;
  min-width: 0;
  padding: 0.3rem 0.5rem;
  border-radius: 0.25rem;
  background-color: var(--bg-primary);
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
  color: var(--text-primary);
  overflow-x: auto;
  white-space: nowrap;
}

.vt-cmd-raw .vt-code {
  color: var(--text-muted);
  background-color: transparent;
}

.vt-copy {
  flex-shrink: 0;
  min-width: 4.5rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.6875rem;
  cursor: pointer;
  transition: all 0.12s ease;
}

.vt-copy:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.vt-copy.is-copied {
  border-color: #16a34a;
  color: #16a34a;
}

.vt-warn {
  margin-top: 0.35rem;
  font-size: 0.6875rem;
  color: #b45309;
}

.vt-meta {
  margin-top: 0.25rem;
  font-size: 0.6875rem;
  color: var(--text-muted);
}

code {
  font-family: ui-monospace, monospace;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
