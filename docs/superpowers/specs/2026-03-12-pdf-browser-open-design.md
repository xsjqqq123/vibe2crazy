# PDF Browser Open Design

## Overview

Remove the in-app PDF preview functionality. When users click a PDF file, display a prompt in the editor area with an "Open in Browser" button. Clicking the button fetches the PDF as a blob and opens it in a new browser tab using the browser's native PDF viewer.

## Motivation

- Simplify the codebase by removing PDF.js dependency
- Reduce bundle size
- Leverage browser's native PDF viewing capabilities (which are more reliable and feature-complete)

## Changes

### 1. Delete Files

| File | Reason |
|------|--------|
| `frontend/src/components/PdfPreviewModal.vue` | No longer needed |

### 2. Remove Dependencies

**File:** `frontend/package.json`

Remove `pdfjs-dist` from dependencies.

### 3. Modify CodeReviewView.vue

#### Remove
- Import of `PdfPreviewModal` component
- `showPdfPreview` ref state
- `pdfPreviewPath` ref state
- `<PdfPreviewModal .../>` component in template

#### Add State
```typescript
const pdfPromptFile = ref<string | null>(null)  // File path when PDF clicked
const openingPdf = ref(false)  // Loading state during blob fetch
const pdfError = ref<string | null>(null)  // Error message if fetch fails
const pdfDownloadProgress = ref<{ loaded: number; total: number } | null>(null)  // Download progress
```

#### Modify loadFile Function
When a PDF file is clicked:
```typescript
if (filePath.endsWith('.pdf')) {
  pdfPromptFile.value = filePath
  return
}
```

Also reset `pdfPromptFile` to `null` when loading non-PDF files.

#### Add Function
```typescript
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

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
    // Note: Blob URL will be cleaned up by browser when the window closes
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

#### Add Template Section
In the editor area, show when `pdfPromptFile` is set:
```vue
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

### 4. Modify API Client

**File:** `frontend/src/api/client.ts`

Add a new function to fetch blob with progress support:

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

### 5. Modify Files API

**File:** `frontend/src/api/files.ts`

Update `getRawFile` to support progress callback:

```typescript
import request, { requestBlob, requestBlobWithProgress } from './client'

// Add progress callback type
type ProgressCallback = (progress: { loaded: number; total: number }) => void

const filesApi = {
  // ... existing methods ...

  getRawFile: (taskId: string, filePath: string, onProgress?: ProgressCallback) => {
    if (onProgress) {
      return requestBlobWithProgress(`/tasks/${taskId}/files/${filePath}?raw=true`, onProgress)
    }
    return requestBlob(`/tasks/${taskId}/files/${filePath}?raw=true`)
  },

  // ... rest of methods ...
}
```

### 6. Backend

No changes required. The existing `getRawFile` API at `/api/tasks/{task_id}/files/{file_path}?raw=true` already supports header-based authentication and returns the file as a blob with `Content-Length` header for progress tracking.

## Data Flow

1. User clicks a `.pdf` file in the file tree
2. `loadFile()` detects PDF extension, sets `pdfPromptFile` to the file path
3. Editor area shows the PDF prompt UI
4. User clicks "Open in Browser" button
5. `openPdfInBrowser()` fetches the file as blob with auth headers
6. Creates a blob URL via `URL.createObjectURL()`
7. Opens the blob URL in a new browser tab
8. Browser displays PDF using native viewer

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