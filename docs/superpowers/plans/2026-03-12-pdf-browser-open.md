# PDF Browser Open Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove in-app PDF preview and replace with browser open functionality with download progress support.

**Architecture:** Delete PdfPreviewModal component, add streaming blob fetch with progress to API client, update CodeReviewView to show PDF prompt with progress bar in editor area.

**Tech Stack:** Vue 3, TypeScript, Fetch API with ReadableStream

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/api/client.ts` | Modify | Add `requestBlobWithProgress` function |
| `frontend/src/api/files.ts` | Modify | Update `getRawFile` to accept progress callback |
| `frontend/src/views/CodeReviewView.vue` | Modify | Remove PDF modal, add PDF prompt UI |
| `frontend/src/components/PdfPreviewModal.vue` | Delete | No longer needed |
| `frontend/package.json` | Modify | Remove `pdfjs-dist` dependency |

---

## Chunk 1: API Client Enhancement

### Task 1: Add Streaming Blob Fetch with Progress

**Files:**
- Modify: `frontend/src/api/client.ts:140-141`

- [ ] **Step 1: Add BlobProgress interface and requestBlobWithProgress function**

After the existing `requestBlob` function (line 138), add:

```typescript
interface BlobProgress {
  loaded: number
  total: number
}

async function requestBlobWithProgress(
  endpoint: string,
  onProgress: (progress: BlobProgress) => void,
  options: RequestInit = {}
): Promise<Blob> {
  const token = localStorage.getItem('auth_token')

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {})
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  })

  if (response.status === 401) {
    handle401()
    throw new Error('Unauthorized')
  }

  if (response.status === 403) {
    handle403()
    throw new Error('Forbidden')
  }

  if (response.status === 204) {
    return new Blob()
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || error.message || 'Request failed')
  }

  const contentLength = response.headers.get('content-length')
  const total = contentLength ? parseInt(contentLength, 10) : 0

  const reader = response.body?.getReader()
  if (!reader) {
    return await response.blob()
  }

  const chunks: Uint8Array[] = []
  let loaded = 0

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    loaded += value.length
    onProgress({ loaded, total })
  }

  return new Blob(chunks)
}

export { requestBlob, requestBlobWithProgress }
```

- [ ] **Step 2: Update export statement**

Change line 140 from:
```typescript
export { requestBlob }
```
to:
```typescript
export { requestBlob, requestBlobWithProgress }
```

- [ ] **Step 3: Commit changes**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(api): add requestBlobWithProgress for streaming downloads

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 2: Files API Update

### Task 2: Update getRawFile to Support Progress

**Files:**
- Modify: `frontend/src/api/files.ts:1,61-62`

- [ ] **Step 1: Update import statement**

Change line 1 from:
```typescript
import request, { requestBlob } from './client'
```
to:
```typescript
import request, { requestBlob, requestBlobWithProgress } from './client'
```

- [ ] **Step 2: Add progress callback type**

Add after line 27 (after `FileUploadResponse` interface):

```typescript
type ProgressCallback = (progress: { loaded: number; total: number }) => void
```

- [ ] **Step 3: Update getRawFile method**

Change lines 61-62 from:
```typescript
  getRawFile: (taskId: string, filePath: string) =>
    requestBlob(`/tasks/${taskId}/files/${filePath}?raw=true`),
```
to:
```typescript
  getRawFile: (taskId: string, filePath: string, onProgress?: ProgressCallback) => {
    if (onProgress) {
      return requestBlobWithProgress(`/tasks/${taskId}/files/${filePath}?raw=true`, onProgress)
    }
    return requestBlob(`/tasks/${taskId}/files/${filePath}?raw=true`)
  },
```

- [ ] **Step 4: Commit changes**

```bash
git add frontend/src/api/files.ts
git commit -m "feat(api): add progress callback support to getRawFile

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 3: CodeReviewView Changes

### Task 3: Remove PDF Modal and Add PDF Prompt State

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue:17,118-119,485-494,1817-1823`

- [ ] **Step 1: Remove PdfPreviewModal import**

Delete line 17:
```typescript
import PdfPreviewModal from '@/components/PdfPreviewModal.vue'
```

- [ ] **Step 2: Replace PDF preview state with PDF prompt state**

Change lines 117-119 from:
```typescript
// PDF preview state
const showPdfPreview = ref(false)
const pdfPreviewPath = ref('')
```
to:
```typescript
// PDF prompt state
const pdfPromptFile = ref<string | null>(null)
const openingPdf = ref(false)
const pdfError = ref<string | null>(null)
const pdfDownloadProgress = ref<{ loaded: number; total: number } | null>(null)
```

- [ ] **Step 3: Add formatFileSize helper function**

Add after line 119 (after the new PDF state):

```typescript
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
```

- [ ] **Step 4: Add openPdfInBrowser and closePdfPrompt functions**

Add after the formatFileSize function:

```typescript
async function openPdfInBrowser() {
  if (!pdfPromptFile.value) return
  openingPdf.value = true
  pdfError.value = null
  pdfDownloadProgress.value = null
  try {
    const blob = await filesApi.getRawFile(taskId.value, pdfPromptFile.value, (progress) => {
      pdfDownloadProgress.value = progress
    })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  } catch (err) {
    pdfError.value = 'Failed to open PDF. Please try again.'
    console.error('Failed to open PDF:', err)
  } finally {
    openingPdf.value = false
    pdfDownloadProgress.value = null
  }
}

function closePdfPrompt() {
  pdfPromptFile.value = null
  pdfError.value = null
  pdfDownloadProgress.value = null
}
```

- [ ] **Step 5: Update loadFile function for PDF handling**

Change lines 484-494 from:
```typescript
  // CHECK FOR PDF: If file is PDF, show preview modal
  if (filePath.endsWith('.pdf')) {
    showPdfPreview.value = true
    pdfPreviewPath.value = filePath

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }
```
to:
```typescript
  // CHECK FOR PDF: If file is PDF, show prompt to open in browser
  if (filePath.endsWith('.pdf')) {
    pdfPromptFile.value = filePath
    pdfError.value = null

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // Reset PDF prompt state when loading other files
  pdfPromptFile.value = null
```

- [ ] **Step 6: Remove PdfPreviewModal from template**

Delete lines 1817-1823:
```vue
    <!-- PDF Preview Modal -->
    <PdfPreviewModal
      :task-id="taskId"
      :file-path="pdfPreviewPath"
      :show="showPdfPreview"
      @close="showPdfPreview = false"
    />
```

- [ ] **Step 7: Modify empty state condition and add PDF prompt UI**

Change line 1519 from:
```vue
                <div v-else-if="!currentFile && !selectedCommit" class="flex items-center justify-center h-full text-sub">
```
to:
```vue
                <div v-else-if="!currentFile && !selectedCommit && !pdfPromptFile" class="flex items-center justify-center h-full text-sub">
```

Then after the empty state div (after line 1521), add the PDF prompt:

```vue

                <!-- PDF File Prompt -->
                <div v-else-if="pdfPromptFile" class="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
                  <div class="text-6xl mb-4">📄</div>
                  <div class="text-lg mb-2">PDF File</div>
                  <div class="text-sm mb-4 text-center">
                    This is a PDF file.<br/>
                    Open in browser to view.
                  </div>

                  <!-- Progress bar -->
                  <div v-if="openingPdf && pdfDownloadProgress" class="w-64 mb-4">
                    <div class="flex justify-between text-xs mb-1">
                      <span>{{ formatFileSize(pdfDownloadProgress.loaded) }}</span>
                      <span v-if="pdfDownloadProgress.total > 0">
                        {{ Math.round(pdfDownloadProgress.loaded / pdfDownloadProgress.total * 100) }}%
                      </span>
                    </div>
                    <div class="w-full bg-gray-700 dark:bg-gray-600 rounded-full h-2">
                      <div
                        class="bg-blue-500 h-2 rounded-full transition-all duration-200"
                        :style="{ width: pdfDownloadProgress.total > 0 ? `${(pdfDownloadProgress.loaded / pdfDownloadProgress.total * 100)}%` : '0%' }"
                      ></div>
                    </div>
                    <div v-if="pdfDownloadProgress.total > 0" class="text-xs text-center mt-1">
                      {{ formatFileSize(pdfDownloadProgress.loaded) }} / {{ formatFileSize(pdfDownloadProgress.total) }}
                    </div>
                  </div>

                  <div v-if="pdfError" class="text-red-500 text-sm mb-2">{{ pdfError }}</div>
                  <div class="flex gap-2">
                    <button
                      @click="openPdfInBrowser"
                      :disabled="openingPdf"
                      class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:opacity-50"
                    >
                      {{ openingPdf ? 'Opening...' : 'Open in Browser' }}
                    </button>
                    <button
                      @click="closePdfPrompt"
                      :disabled="openingPdf"
                      class="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 dark:bg-gray-500 dark:hover:bg-gray-600 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
```

- [ ] **Step 8: Commit changes**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(ui): replace PDF preview modal with browser open prompt

- Remove PdfPreviewModal component usage
- Add PDF prompt UI with progress bar
- Add openPdfInBrowser with streaming download progress

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 4: Cleanup

### Task 4: Delete PdfPreviewModal and Remove Dependency

**Files:**
- Delete: `frontend/src/components/PdfPreviewModal.vue`
- Modify: `frontend/package.json:24`

- [ ] **Step 1: Delete PdfPreviewModal.vue**

```bash
rm frontend/src/components/PdfPreviewModal.vue
```

- [ ] **Step 2: Remove pdfjs-dist from package.json**

Change line 24 from:
```json
    "pdfjs-dist": "^5.5.207",
```
to:
(Delete the line entirely)

The dependencies section should look like:
```json
  "dependencies": {
    "@monaco-editor/loader": "^1.7.0",
    "@types/highlight.js": "^9.12.4",
    "@types/markdown-it": "^14.1.2",
    "@vueuse/core": "^14.2.1",
    "@xterm/addon-fit": "^0.11.0",
    "@xterm/addon-webgl": "^0.19.0",
    "@xterm/xterm": "^6.0.0",
    "highlight.js": "^11.11.1",
    "markdown-it": "^14.1.1",
    "monaco-editor": "^0.45.0",
    "pinia": "^2.1.0",
    "splitpanes": "^4.0.4",
    "vue": "^3.4.0",
    "vue-router": "^4.2.0"
  },
```

- [ ] **Step 3: Install dependencies to update lock file**

```bash
cd frontend && npm install
```

Expected: `npm` removes pdfjs-dist from node_modules and updates package-lock.json

- [ ] **Step 4: Commit changes**

```bash
git add frontend/src/components/PdfPreviewModal.vue frontend/package.json frontend/package-lock.json
git commit -m "chore: remove pdfjs-dist dependency and PdfPreviewModal

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Testing Checklist

- [ ] Clicking a PDF file shows the prompt in editor area
- [ ] "Open in Browser" button opens PDF in new tab
- [ ] PDF displays correctly in browser
- [ ] Loading state shows during fetch
- [ ] Progress bar displays with percentage and file size for large files
- [ ] Progress bar animates smoothly during download
- [ ] Error message displays if fetch fails
- [ ] "Cancel" button dismisses the prompt
- [ ] Clicking a non-PDF file dismisses the prompt
- [ ] PdfPreviewModal.vue is deleted
- [ ] pdfjs-dist removed from package.json
- [ ] No console errors