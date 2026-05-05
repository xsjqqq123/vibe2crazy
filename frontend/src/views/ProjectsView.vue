<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useTheme } from '@/composables/useTheme'
import { useConfirm } from '@/composables/useConfirm'
import { useUpdateCheck } from '@/composables/useUpdateCheck'
import projectsApi from '@/api/projects'
import type { Project, ProjectCreate } from '@/api/projects'
import DirectoryAutocomplete from '@/components/DirectoryAutocomplete.vue'
import BranchAutocomplete from '@/components/BranchAutocomplete.vue'
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'
import MatrixIcon from '@/components/MatrixIcon.vue'
import UpdateToast from '@/components/UpdateToast.vue'
import UpdateDetailModal from '@/components/UpdateDetailModal.vue'
import TunnelPanel from '@/components/TunnelPanel.vue'

const router = useRouter()
const { logout } = useAuth()
const { theme, cycleTheme } = useTheme()
const { showConfirm } = useConfirm()

const {
  latestVersionInfo,
  currentVersion,
  hasUpdate,
  init,
  checkForUpdates,
  getCurrentPlatform,
  isNewerVersion
} = useUpdateCheck()

const showUpdateToast = ref(false)
const showUpdateModal = ref(false)
const updateDismissed = ref(false)

// Show update toast when update is detected (non-blocking check)
watch(hasUpdate, (hasUpdateVal) => {
  if (hasUpdateVal && !updateDismissed.value) {
    showUpdateToast.value = true
  }
})

const projects = ref<Project[]>([])
const loading = ref(true)
const showCreateDialog = ref(false)
const showGitInitDialog = ref(false)
const showCreateDirectoryDialog = ref(false)
const pendingProject = ref<ProjectCreate | null>(null)
const pendingDirectoryProject = ref<ProjectCreate | null>(null)
const newProject = ref({ name: '', git_path: '', main_branch: '' })
const createError = ref('')

const loadProjects = async () => {
  loading.value = true
  try {
    projects.value = await projectsApi.list()
  } catch (err: any) {
    console.error('Failed to load projects:', err)
  }
  loading.value = false
}

const openProject = (project: Project) => {
  router.push(`/projects/${project.id}`)
}

const createProject = async (initGit = false) => {
  if (!newProject.value.name || !newProject.value.git_path) {
    createError.value = 'Please fill in all required fields'
    return
  }

  loading.value = true
  createError.value = ''

  try {
    const payload = {
      ...newProject.value,
      init_git: initGit
    }
    await projectsApi.create(payload)
    showCreateDialog.value = false
    showGitInitDialog.value = false
    pendingProject.value = null
    newProject.value = { name: '', git_path: '', main_branch: '' }
    await loadProjects()
  } catch (err: any) {
    if (err.message && err.message.includes('Directory does not exist') && !initGit) {
      // Show directory creation dialog
      pendingDirectoryProject.value = { ...newProject.value }
      showCreateDirectoryDialog.value = true
    } else if (err.message && err.message.includes('not a git repository') && !initGit) {
      // Show git init dialog
      pendingProject.value = { ...newProject.value }
      showGitInitDialog.value = true
    } else {
      createError.value = err.message || 'Failed to create project'
    }
  }

  loading.value = false
}

const createProjectWithInit = async () => {
  if (!pendingProject.value) {
    return
  }
  newProject.value = {
    name: pendingProject.value.name,
    git_path: pendingProject.value.git_path,
    main_branch: pendingProject.value.main_branch || ''
  }
  await createProject(true)
}

const closeGitInitDialog = () => {
  showGitInitDialog.value = false
  pendingProject.value = null
}

const createProjectWithDirectory = async () => {
  if (!pendingDirectoryProject.value) {
    return
  }
  newProject.value = {
    name: pendingDirectoryProject.value.name,
    git_path: pendingDirectoryProject.value.git_path,
    main_branch: pendingDirectoryProject.value.main_branch || ''
  }
  // Create directory and then create project (don't init git yet, that will be handled separately if needed)
  const payload = {
    ...newProject.value,
    create_directory: true
  }
  try {
    await projectsApi.create(payload)
    showCreateDialog.value = false
    showCreateDirectoryDialog.value = false
    pendingDirectoryProject.value = null
    newProject.value = { name: '', git_path: '', main_branch: '' }
    await loadProjects()
  } catch (err: any) {
    if (err.message && err.message.includes('not a git repository')) {
      // Directory created, but need git init
      pendingProject.value = { ...newProject.value }
      showCreateDirectoryDialog.value = false
      showGitInitDialog.value = true
    } else {
      createError.value = err.message || 'Failed to create project'
      showCreateDirectoryDialog.value = false
    }
  }
  loading.value = false
}

const closeCreateDirectoryDialog = () => {
  showCreateDirectoryDialog.value = false
  pendingDirectoryProject.value = null
}

const deleteProject = async (id: string, name: string) => {
  const confirmed = await showConfirm({
    title: 'Delete Project',
    message: `Are you sure you want to delete project "${name}"?`,
    confirmText: 'Delete',
    danger: true
  })

  if (!confirmed) return

  loading.value = true
  try {
    await projectsApi.delete(id)
    await loadProjects()
  } catch (err: any) {
    console.error('Failed to delete project:', err)
  }
  loading.value = false
}

async function manualCheckUpdate() {
  const info = await checkForUpdates(true)
  if (info && isNewerVersion(currentVersion.value, info.version)) {
    showUpdateToast.value = true
    updateDismissed.value = false
  } else {
    await showConfirm({
      title: 'No Update Available',
      message: 'You are already on the latest version.',
      confirmText: 'OK',
      cancelText: ''
    })
  }
}

function openUpdateModal() {
  showUpdateToast.value = false
  showUpdateModal.value = true
}

function dismissUpdateToast() {
  showUpdateToast.value = false
  updateDismissed.value = true
}

onMounted(async () => {
  loadProjects()
  await init()
  checkForUpdates()
})
</script>

<template>
  <div class="min-h-screen">
    <!-- Update Toast -->
    <UpdateToast
      :visible="showUpdateToast"
      :version="latestVersionInfo?.version || ''"
      :current-version="currentVersion"
      @view-details="openUpdateModal"
      @dismiss="dismissUpdateToast"
    />

    <!-- Update Detail Modal -->
    <UpdateDetailModal
      :visible="showUpdateModal"
      :version-info="latestVersionInfo"
      :current-version="currentVersion"
      :current-platform="getCurrentPlatform()"
      @close="showUpdateModal = false"
    />

    <!-- Header -->
    <header class="bg-main border-b border-main">
      <div class="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-2 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-main">Vibe2Crazy</h1>
          <p class="text-xs text-sub">Projects</p>
        </div>
        <div class="flex items-center gap-2">
          <button @click="manualCheckUpdate" class="p-1.5 rounded-lg hover:bg-sub" title="Check for Updates">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button @click="cycleTheme" class="p-1.5 rounded-lg hover:bg-sub" title="Cycle theme">
            <!-- Sun icon for light theme -->
            <svg v-if="theme === 'light'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <!-- Moon icon for dark theme -->
            <svg v-else-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            <!-- Leaf icon for green theme -->
            <svg v-else-if="theme === 'green'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
            <!-- Document icon for parchment theme -->
            <svg v-else-if="theme === 'parchment'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-amber-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          <GlobalTerminalIcon />
          <MatrixIcon />
          <button @click="logout" class="p-1.5 rounded-lg hover:bg-sub" title="Logout">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Tunnel Panel -->
    <div class="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 pt-4">
      <TunnelPanel />
    </div>

    <!-- Main content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-main">Your Projects</h2>
        <button @click="showCreateDialog = true" class="btn btn-primary">
          + New Project
        </button>
      </div>

      <!-- Projects grid -->
      <div v-if="loading && projects.length === 0" class="flex items-center justify-center py-12">
        <div class="spinner"></div>
      </div>

      <div v-else-if="projects.length === 0" class="text-center py-12">
        <p class="text-sub mb-4">No projects yet</p>
        <button @click="showCreateDialog = true" class="btn btn-primary">Create your first project</button>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="project in projects"
          :key="project.id"
          @click="openProject(project)"
          class="card-hover relative group"
        >
          <div class="flex items-start justify-between">
            <div class="min-w-0 flex-1">
              <h3 class="text-lg font-semibold text-main break-words">{{ project.name }}</h3>
              <p class="text-sm text-sub mt-1 break-all">
                {{ project.git_path }}
              </p>
              <p class="text-xs text-muted mt-2 break-words">
                Branch: {{ project.main_branch }}
              </p>
            </div>
            <button
              @click.stop="deleteProject(project.id, project.name)"
              class="p-1 text-red-600 hover:text-red-700"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- Create project dialog -->
    <div v-if="showCreateDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Create New Project</h3>

        <form @submit.prevent="() => createProject(false)" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-sub mb-2">
              Project Name *
            </label>
            <input v-model="newProject.name" type="text" class="input w-full" placeholder="My Project" />
          </div>

          <div>
            <label class="block text-sm font-medium text-sub mb-2">
              Git Repository Path *
            </label>
            <DirectoryAutocomplete
              v-model="newProject.git_path"
              placeholder="/path/to/repo"
            />
            <p class="text-xs text-gray-500 mt-1">Path to git repository - branch will be auto-detected when path is entered</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-sub mb-2">
              Main Branch
            </label>
            <BranchAutocomplete
              v-model="newProject.main_branch"
              :git-path="newProject.git_path"
              placeholder="main"
            />
            <p class="text-xs text-gray-500 mt-1">Auto-detected from repository, or select from dropdown</p>
          </div>

          <div v-if="createError" class="text-red-600 dark:text-red-400 text-sm">
            {{ createError }}
          </div>

          <div class="flex gap-3 justify-end">
            <button type="button" @click="showCreateDialog = false" class="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" :disabled="loading" class="btn btn-primary">
              <span v-if="loading" class="spinner mr-2"></span>
              Create
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Git init confirmation dialog -->
    <div v-if="showGitInitDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Initialize Git Repository?</h3>
        <p class="text-sm text-sub mb-4">
          The directory <code class="bg-sub px-2 py-1 rounded">{{ pendingProject?.git_path }}</code> is not a git repository.
        </p>
        <p class="text-sm text-sub mb-6">
          Would you like to initialize it as a git repository and create the project?
        </p>
        <div class="flex gap-3 justify-end">
          <button @click="closeGitInitDialog" class="btn btn-secondary">
            Cancel
          </button>
          <button @click="createProjectWithInit" :disabled="loading" class="btn btn-primary">
            <span v-if="loading" class="spinner mr-2"></span>
            Initialize & Create
          </button>
        </div>
      </div>
    </div>

    <!-- Directory creation confirmation dialog -->
    <div v-if="showCreateDirectoryDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Create Directory?</h3>
        <p class="text-sm text-sub mb-4">
          The directory <code class="bg-sub px-2 py-1 rounded">{{ pendingDirectoryProject?.git_path }}</code> does not exist.
        </p>
        <p class="text-sm text-sub mb-6">
          Would you like to create the directory and proceed with creating the project?
        </p>
        <div class="flex gap-3 justify-end">
          <button @click="closeCreateDirectoryDialog" class="btn btn-secondary">
            Cancel
          </button>
          <button @click="createProjectWithDirectory" :disabled="loading" class="btn btn-primary">
            <span v-if="loading" class="spinner mr-2"></span>
            Create Directory & Create
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
