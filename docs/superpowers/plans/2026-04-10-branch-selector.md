# Branch Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a branch dropdown selector to the project creation form that auto-detects the current branch and lists all local branches for selection.

**Architecture:** Backend adds a new GitService method and API endpoint to list local branches. Frontend creates a new BranchAutocomplete component following the DirectoryAutocomplete pattern, which watches the git path prop and loads branches when it becomes a valid repository.

**Tech Stack:** Python/FastAPI (backend), Vue 3 + TypeScript + Vitest (frontend)

---

## File Structure

| File | Purpose |
|------|---------|
| `backend/app/services/git_service.py` | Add `get_local_branches()` static method |
| `backend/tests/test_git_service.py` | Add tests for `get_local_branches()` |
| `backend/app/routers/git.py` | Add `GET /api/git/branches` endpoint and `BranchListResponse` schema |
| `frontend/src/api/git.ts` | Add `BranchListResponse` type and `getBranches()` function |
| `frontend/src/components/BranchAutocomplete.vue` | New dropdown component for branch selection |
| `frontend/src/components/__tests__/BranchAutocomplete.spec.ts` | Unit tests for BranchAutocomplete |
| `frontend/src/views/ProjectsView.vue` | Replace branch input with BranchAutocomplete, remove detectCurrentBranch |

---

### Task 1: Backend - GitService.get_local_branches()

**Files:**
- Modify: `backend/app/services/git_service.py` (add new method after `get_default_branch`)
- Modify: `backend/tests/test_git_service.py` (add tests)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_git_service.py`:

```python
def test_get_local_branches_returns_branches_and_current(tmp_project):
    """
    Test that get_local_branches returns all local branches and identifies current branch.
    """
    # Create additional branches
    subprocess.run(["git", "branch", "develop"], cwd=tmp_project, check=True)
    subprocess.run(["git", "branch", "feature-x"], cwd=tmp_project, check=True)

    branches, current = GitService.get_local_branches(str(tmp_project))

    # Should return all branches
    assert "main" in branches
    assert "develop" in branches
    assert "feature-x" in branches

    # Should identify current branch
    assert current == "main"

    # Branches should be sorted
    assert branches == sorted(branches)


def test_get_local_branches_handles_non_git_directory(tmp_path):
    """
    Test that get_local_branches returns empty list for non-git directory.
    """
    non_git_dir = tmp_path / "non-git"
    non_git_dir.mkdir()

    branches, current = GitService.get_local_branches(str(non_git_dir))

    assert branches == []
    assert current == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && pytest tests/test_git_service.py::test_get_local_branches_returns_branches_and_current -v`

Expected: FAIL with "AttributeError: type object 'GitService' has no attribute 'get_local_branches'" or similar

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/services/git_service.py` after the `get_default_branch` method (around line 85):

```python
    @staticmethod
    def get_local_branches(path: str) -> tuple[list[str], str]:
        """
        Get all local branch names and current branch.

        Returns: (branches_list, current_branch)

        - Uses `git branch --no-color` to list all local branches
        - Parses output: current branch has '*' prefix, others are plain names
        - Returns sorted list of branch names and the current branch name
        """
        logger.debug(f"Getting local branches for {path}")
        try:
            result = subprocess.run(
                ["git", "branch", "--no-color"],
                cwd=path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode != 0:
                logger.error(f"Failed to get branches: {result.stderr}")
                return [], ""

            branches = []
            current_branch = ""

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                # git branch output format:
                # "* main"  <- current branch (has * prefix)
                # "  develop" <- other branches (spaces prefix)
                line = line.strip()
                if line.startswith('*'):
                    # Current branch - remove * and leading/trailing spaces
                    current_branch = line[1:].strip()
                    branches.append(current_branch)
                else:
                    # Other branch
                    branch_name = line.strip()
                    if branch_name:
                        branches.append(branch_name)

            # Sort branches alphabetically
            branches = sorted(branches)

            logger.debug(f"Found {len(branches)} branches, current: {current_branch}")
            return branches, current_branch

        except Exception as e:
            logger.error(f"Error getting local branches: {e}")
            return [], ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && pytest tests/test_git_service.py::test_get_local_branches_returns_branches_and_current tests/test_git_service.py::test_get_local_branches_handles_non_git_directory -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/services/git_service.py backend/tests/test_git_service.py
git commit -m "feat(git): add get_local_branches method to GitService

Returns all local branches and identifies current branch using
git branch --no-color command.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Backend - API endpoint GET /api/git/branches

**Files:**
- Modify: `backend/app/routers/git.py` (add endpoint and schema)
- Modify: `backend/tests/test_git_router.py` (add test)

- [ ] **Step 1: Write the failing test**

Check existing test file structure first. Then add to `backend/tests/test_git_router.py`:

```python
def test_get_branches_endpoint_returns_branches(client, tmp_project):
    """
    Test that /api/git/branches endpoint returns branch list.
    """
    import subprocess
    from pathlib import Path

    # Create additional branches
    subprocess.run(["git", "branch", "develop"], cwd=tmp_project, check=True)

    response = client.get(f"/api/git/branches?path={tmp_project}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "main" in data["branches"]
    assert "develop" in data["branches"]
    assert data["current_branch"] == "main"


def test_get_branches_endpoint_handles_non_git(client, tmp_path):
    """
    Test that /api/git/branches returns error for non-git directory.
    """
    non_git = tmp_path / "non-git"
    non_git.mkdir()

    response = client.get(f"/api/git/branches?path={non_git}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["branches"] == []
    assert data["current_branch"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && pytest tests/test_git_router.py::test_get_branches_endpoint_returns_branches -v`

Expected: FAIL with 404 or endpoint not found

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/routers/git.py` after the existing `BranchResponse` class (around line 22):

```python
class BranchListResponse(BaseModel):
    branches: List[str]
    current_branch: str
    success: bool
    message: str | None = None
```

Add endpoint after the existing `get_branch` endpoint (around line 340):

```python
@branch_router.get("/branches", response_model=BranchListResponse)
async def get_branches(
    path: str = Query(..., description="Path to the git repository"),
    current_user: Task = Depends(require_auth)
):
    """Get all local branches and current branch for a git repository"""
    try:
        branches, current_branch = GitService.get_local_branches(path)
        if not branches and not current_branch:
            return BranchListResponse(
                branches=[],
                current_branch="",
                success=False,
                message="Failed to get branches: not a git repository or no branches found"
            )
        return BranchListResponse(
            branches=branches,
            current_branch=current_branch,
            success=True,
            message=None
        )
    except Exception as e:
        logger.error(f"Error getting branches: {e}")
        return BranchListResponse(
            branches=[],
            current_branch="",
            success=False,
            message=f"Failed to get branches: {str(e)}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && pytest tests/test_git_router.py::test_get_branches_endpoint_returns_branches tests/test_git_router.py::test_get_branches_endpoint_handles_non_git -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/routers/git.py backend/tests/test_git_router.py
git commit -m "feat(api): add GET /api/git/branches endpoint

Returns all local branches and current branch for a git repository.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Frontend - API client for branches

**Files:**
- Modify: `frontend/src/api/git.ts`

- [ ] **Step 1: Add BranchListResponse type and getBranches function**

Modify `frontend/src/api/git.ts` - add after the existing `ResetResponse` interface (around line 42):

```typescript
export interface BranchListResponse {
  branches: string[]
  current_branch: string
  success: boolean
  message: string | null
}

export async function getBranches(gitPath: string): Promise<BranchListResponse> {
  return request<BranchListResponse>(`/git/branches?path=${encodeURIComponent(gitPath)}`)
}
```

Add to the `gitApi` export object at the end of file:

```typescript
export const gitApi = {
  getWorktreeCommits,
  getCommitDiff,
  resetToCommit,
  getBranches
}
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm run build 2>&1 | head -20`

Expected: Build succeeds or shows no TypeScript errors related to git.ts

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/api/git.ts
git commit -m "feat(api): add getBranches function and BranchListResponse type

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Frontend - BranchAutocomplete component

**Files:**
- Create: `frontend/src/components/BranchAutocomplete.vue`
- Create: `frontend/src/components/__tests__/BranchAutocomplete.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/__tests__/BranchAutocomplete.spec.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BranchAutocomplete from '../BranchAutocomplete.vue'
import { getBranches } from '@/api/git'

// Mock the API
vi.mock('@/api/git', () => ({
  getBranches: vi.fn()
}))

describe('BranchAutocomplete', () => {
  it('renders input field with placeholder', () => {
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '', placeholder: 'Select branch' }
    })

    expect(wrapper.find('input').attributes('placeholder')).toBe('Select branch')
  })

  it('emits update:modelValue when input changes', async () => {
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '' }
    })

    const input = wrapper.find('input')
    await input.setValue('main')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['main'])
  })

  it('loads branches when gitPath changes to valid value', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop', 'feature-x'],
      current_branch: 'main',
      success: true,
      message: null
    })

    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '' }
    })

    // Change gitPath to trigger loading
    await wrapper.setProps({ gitPath: '/path/to/repo' })

    // Wait for async operation
    await new Promise(resolve => setTimeout(resolve, 100))

    expect(mockGetBranches).toHaveBeenCalledWith('/path/to/repo')
  })

  it('auto-fills current branch on successful load when modelValue is empty', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop'],
      current_branch: 'main',
      success: true,
      message: null
    })

    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '' }
    })

    await wrapper.setProps({ gitPath: '/path/to/repo' })
    await new Promise(resolve => setTimeout(resolve, 100))

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['main'])
  })

  it('does not auto-fill when modelValue already has value', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop'],
      current_branch: 'main',
      success: true,
      message: null
    })

    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: 'develop', gitPath: '' }
    })

    await wrapper.setProps({ gitPath: '/path/to/repo' })
    await new Promise(resolve => setTimeout(resolve, 100))

    // Should not emit because modelValue already has 'develop'
    const emitted = wrapper.emitted('update:modelValue')
    if (emitted) {
      // If emitted, should not be 'main' (auto-fill)
      expect(emitted[emitted.length - 1]).not.toEqual(['main'])
    }
  })

  it('shows dropdown when button is clicked and branches exist', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop'],
      current_branch: 'main',
      success: true,
      message: null
    })

    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '/repo' }
    })

    await new Promise(resolve => setTimeout(resolve, 100))

    // Click dropdown button
    const dropdownBtn = wrapper.find('button')
    await dropdownBtn.trigger('click')

    // Dropdown should be visible
    expect(wrapper.html()).toContain('main')
  })

  it('disables dropdown button when no branches available', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: [],
      current_branch: '',
      success: false,
      message: 'Not a git repo'
    })

    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '/non-repo' }
    })

    await new Promise(resolve => setTimeout(resolve, 100))

    const dropdownBtn = wrapper.find('button')
    expect(dropdownBtn.attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm test -- --run BranchAutocomplete.spec.ts`

Expected: FAIL with "Cannot find module '../BranchAutocomplete.vue'" or similar

- [ ] **Step 3: Write the component implementation**

Create `frontend/src/components/BranchAutocomplete.vue`:

```vue
<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useDebounceFn, onClickOutside } from '@vueuse/core'
import { getBranches } from '@/api/git'

interface Props {
  modelValue: string
  gitPath: string
  placeholder?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Select branch',
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  blur: []
}>()

// State
const query = ref(props.modelValue)
const branches = ref<string[]>([])
const currentBranch = ref('')
const showDropdown = ref(false)
const highlightedIndex = ref(-1)
const loading = ref(false)
const isValidRepo = ref(false)

// Template refs
const inputRef = ref<HTMLInputElement>()
const dropdownRef = ref<HTMLDivElement>()
const wrapperRef = ref<HTMLDivElement>()

// Debounced fetch function
const fetchBranches = useDebounceFn(async (path: string) => {
  if (!path || path.trim() === '') {
    branches.value = []
    currentBranch.value = ''
    isValidRepo.value = false
    showDropdown.value = false
    return
  }

  loading.value = true
  try {
    const response = await getBranches(path)
    if (response.success) {
      branches.value = response.branches
      currentBranch.value = response.current_branch
      isValidRepo.value = true

      // Auto-fill current branch if modelValue is empty
      if (!props.modelValue && response.current_branch) {
        query.value = response.current_branch
        emit('update:modelValue', response.current_branch)
      }
    } else {
      branches.value = []
      currentBranch.value = ''
      isValidRepo.value = false
    }
    showDropdown.value = false
    highlightedIndex.value = -1
  } catch (error) {
    console.error('Failed to fetch branches:', error)
    branches.value = []
    currentBranch.value = ''
    isValidRepo.value = false
    showDropdown.value = false
  } finally {
    loading.value = false
  }
}, 300)

// Watch for gitPath changes
watch(() => props.gitPath, (newPath) => {
  fetchBranches(newPath)
})

// Watch for query changes (user input)
watch(query, (newQuery) => {
  emit('update:modelValue', newQuery)
})

// Watch for external modelValue changes
watch(() => props.modelValue, (newValue) => {
  if (newValue !== query.value) {
    query.value = newValue
  }
})

// Toggle dropdown
const toggleDropdown = () => {
  if (!isValidRepo.value || branches.value.length === 0) {
    return
  }
  showDropdown.value = !showDropdown.value
  highlightedIndex.value = -1
}

// Select a branch from dropdown
const selectBranch = (branch: string) => {
  query.value = branch
  showDropdown.value = false
  highlightedIndex.value = -1
}

// Keyboard navigation
const handleKeydown = (event: KeyboardEvent) => {
  if (!showDropdown.value || branches.value.length === 0) {
    // If user presses Enter without dropdown, just emit blur
    if (event.key === 'Enter') {
      showDropdown.value = false
    }
    return
  }

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(highlightedIndex.value + 1, branches.value.length - 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, -1)
      break
    case 'Enter':
      if (highlightedIndex.value >= 0) {
        event.preventDefault()
        selectBranch(branches.value[highlightedIndex.value])
      }
      break
    case 'Escape':
      showDropdown.value = false
      highlightedIndex.value = -1
      break
  }
}

// Handle blur with delay to allow click events
const handleBlur = () => {
  setTimeout(() => {
    showDropdown.value = false
    highlightedIndex.value = -1
    emit('blur')
  }, 200)
}

// Click outside handler
onClickOutside(wrapperRef, () => {
  showDropdown.value = false
  highlightedIndex.value = -1
})

// Initialize on mount if gitPath is provided
onMounted(() => {
  if (props.gitPath && props.gitPath.trim() !== '') {
    fetchBranches(props.gitPath)
  }
})
</script>

<template>
  <div ref="wrapperRef" class="relative flex items-center gap-0">
    <input
      ref="inputRef"
      v-model="query"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      @keydown="handleKeydown"
      @blur="handleBlur"
      class="flex-1 px-3 py-2 border border-gray-300 dark:border-dark-700 rounded-l-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-dark-800 dark:text-gray-100 dark:placeholder-gray-500 disabled:bg-gray-100 dark:disabled:bg-dark-900 disabled:cursor-not-allowed"
    />

    <!-- Dropdown button -->
    <button
      type="button"
      @click="toggleDropdown"
      :disabled="disabled || !isValidRepo || branches.length === 0"
      class="px-2 py-2 border border-l-0 border-gray-300 dark:border-dark-700 rounded-r-md bg-gray-50 dark:bg-dark-700 hover:bg-gray-100 dark:hover:bg-dark-600 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
      title="Select branch"
    >
      <!-- Loading spinner -->
      <svg
        v-if="loading"
        class="animate-spin h-4 w-4 text-gray-500 dark:text-gray-300"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
      <!-- Down arrow icon -->
      <svg
        v-else
        class="h-4 w-4 text-gray-500 dark:text-gray-300"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown list -->
    <div
      v-if="showDropdown && branches.length > 0"
      ref="dropdownRef"
      class="absolute z-10 w-full mt-1 top-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-dark-700 rounded-md shadow-lg max-h-60 overflow-auto"
    >
      <ul class="py-1">
        <li
          v-for="(branch, index) in branches"
          :key="branch"
          @click="selectBranch(branch)"
          @mousedown.prevent
          class="px-3 py-2 cursor-pointer transition-colors flex items-center justify-between"
          :class="{
            'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300': index === highlightedIndex,
            'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-700': index !== highlightedIndex
          }"
        >
          <span>{{ branch }}</span>
          <span
            v-if="branch === currentBranch"
            class="text-xs text-gray-500 dark:text-gray-400 ml-2"
          >(current)</span>
        </li>
      </ul>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm test -- --run BranchAutocomplete.spec.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/components/BranchAutocomplete.vue frontend/src/components/__tests__/BranchAutocomplete.spec.ts
git commit -m "feat(ui): add BranchAutocomplete component

Dropdown component for branch selection with:
- Auto-fill current branch on valid git repo
- Keyboard navigation support
- Loading state indicator
- Graceful handling for non-git paths

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Frontend - Integrate BranchAutocomplete in ProjectsView

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`

- [ ] **Step 1: Import BranchAutocomplete component**

Modify `frontend/src/views/ProjectsView.vue` - add import after DirectoryAutocomplete import (around line 10):

```typescript
import BranchAutocomplete from '@/components/BranchAutocomplete.vue'
```

- [ ] **Step 2: Remove detectCurrentBranch function and detectingBranch state**

Remove the `detectingBranch` ref (around line 45):

```typescript
const detectingBranch = ref(false)
```

Remove the `detectCurrentBranch` function (around line 155-177):

```typescript
const detectCurrentBranch = async () => {
  // ... entire function to be removed
}
```

- [ ] **Step 3: Replace Main Branch input with BranchAutocomplete**

In the template, find the Main Branch section (around line 369-382) and replace:

```vue
<!-- BEFORE: Remove this entire section -->
<div>
  <label class="block text-sm font-medium text-sub mb-2">
    Main Branch
    <span v-if="detectingBranch" class="ml-2 spinner-xs"></span>
  </label>
  <input
    v-model="newProject.main_branch"
    type="text"
    class="input w-full"
    placeholder="main"
    :disabled="detectingBranch"
  />
  <p v-if="detectingBranch" class="text-xs text-gray-500 mt-1">Detecting current branch...</p>
</div>
```

Replace with:

```vue
<!-- AFTER -->
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
```

- [ ] **Step 4: Remove @blur handler from DirectoryAutocomplete**

The DirectoryAutocomplete currently has `@blur="detectCurrentBranch"` - remove this handler (around line 364):

```vue
<!-- BEFORE -->
<DirectoryAutocomplete
  v-model="newProject.git_path"
  placeholder="/path/to/repo"
  @blur="detectCurrentBranch"
/>

<!-- AFTER -->
<DirectoryAutocomplete
  v-model="newProject.git_path"
  placeholder="/path/to/repo"
/>
```

- [ ] **Step 5: Verify build succeeds**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm run build`

Expected: Build succeeds with no errors

- [ ] **Step 6: Manual verification**

Start the frontend: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm run dev`

Check that:
1. Create project dialog shows BranchAutocomplete for Main Branch
2. When git path is entered (valid repo), branch dropdown populates
3. Current branch is auto-filled
4. Dropdown button works to show/hide branch list
5. Manual typing still works

- [ ] **Step 7: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/views/ProjectsView.vue
git commit -m "feat(ui): integrate BranchAutocomplete in ProjectsView

Replace manual branch input with BranchAutocomplete component.
Remove detectCurrentBranch function (now handled by component).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Remove obsolete projects API detectBranch

**Files:**
- Modify: `frontend/src/api/projects.ts` (remove detectBranch function)
- Modify: `backend/app/routers/git.py` (existing endpoint, no changes needed)

- [ ] **Step 1: Remove detectBranch from projects API**

Modify `frontend/src/api/projects.ts` - remove the `detectBranch` function and `BranchDetectionResponse` type (around line 25-55):

```typescript
// Remove this type
export interface BranchDetectionResponse {
  branch: string
  success: boolean
  message: string | null
}

// Remove this function from projectsApi object
detectBranch: (gitPath: string) =>
  request<BranchDetectionResponse>(`/git/branch?path=${encodeURIComponent(gitPath)}`)
```

The `projectsApi` object should only have: `list`, `get`, `create`, `update`, `delete`.

- [ ] **Step 2: Verify build succeeds**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm run build`

Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/api/projects.ts
git commit -m "refactor(api): remove obsolete detectBranch from projects API

Branch detection now handled by BranchAutocomplete component
using the new /api/git/branches endpoint.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage check:**
- Requirement 1 (Auto-detect current branch): Task 4 (BranchAutocomplete auto-fill) ✓
- Requirement 2 (Dropdown branch list): Task 4 (BranchAutocomplete dropdown) ✓
- Requirement 3 (Editable input): Task 4 (input field remains editable) ✓
- Requirement 4 (Graceful handling for non-git): Task 1 (get_local_branches returns empty), Task 4 (dropdown disabled) ✓
- Backend endpoint: Task 2 ✓
- Frontend API: Task 3 ✓
- ProjectsView integration: Task 5 ✓
- Cleanup obsolete code: Task 6 ✓

**2. Placeholder scan:**
- No "TBD", "TODO", or vague instructions found
- All code steps have complete implementation code
- All test steps have complete test code
- All commands have exact paths

**3. Type consistency:**
- `BranchListResponse` used consistently in backend (Task 2) and frontend (Task 3)
- `getBranches` function signature matches usage in component (Task 4)
- Props `modelValue`, `gitPath`, `disabled` used consistently throughout

---

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?