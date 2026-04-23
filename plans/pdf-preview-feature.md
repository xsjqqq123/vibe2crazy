# PDF Preview Feature Implementation Plan

## Overview
Add PDF file preview functionality to Vibe2Crazy. When users click on a `.pdf` file in the Files list, a full-screen modal will open showing the PDF with basic browsing (page navigation, zoom), text search, and text selection capabilities.

## Requirements Summary

| Requirement | Detail |
|-------------|--------|
| Display Location | Full-screen modal when clicking PDF in Files list |
| Features | Basic browsing (page navigation, zoom), text search, text selection/copy |
| Technology | PDF.js |
| File Detection | `.pdf` extension only |
| Initial Zoom | 100% |
| Loading | Backend API + PDF.js rendering |

## Implementation Steps

### Step 1: Install PDF.js Dependency
**File:** `frontend/package.json`

Add `pdfjs-dist` to dependencies:
```bash
cd frontend
npm install pdfjs-dist
```

**Acceptance Criteria:**
- `pdfjs-dist` added to `package.json` dependencies
- `npm install` completes successfully

### Step 2: Backend - Add Raw File Endpoint
**File:** `backend/app/routers/files.py`

Add new endpoint to serve raw file content (for binary files like PDF):

```python
@router.get("/{task_id}/files/{file_path:path}/raw")
async def read_file_raw(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Read file as raw bytes (for binary files like PDF)"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    import os
    full_path = os.path.join(task.worktree_path, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(full_path)
```

**Acceptance Criteria:**
- New endpoint `/api/tasks/{task_id}/files/{file_path:path}/raw` works
- Returns file content as `FileResponse`
- Validates task exists
- Validates file exists

### Step 3: Frontend API - Add Raw File Method
**File:** `frontend/src/api/files.ts`

Add new API method to fetch raw file content:

```typescript
getRawFile: (taskId: string, filePath: string) =>
  fetch(`/api/tasks/${taskId}/files/${filePath}/raw`, {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`
    }
  }).then(res => {
    if (!res.ok) throw new Error('Failed to fetch file')
    return res.blob()
  })
```

**Acceptance Criteria:**
- `getRawFile` method added to `filesApi`
- Returns `Promise<Blob>`
- Handles authentication token

### Step 4: Create PdfPreviewModal Component
**File:** `frontend/src/components/PdfPreviewModal.vue` (new file)

Create a new Vue component with the following structure:

```typescript
<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'

interface Props {
  taskId: string
  filePath: string
  show: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

// State
const pdfDocument = ref<pdfjsLib.PDFDocumentProxy | null>(null)
const currentPage = ref(1)
const totalPages = ref(0)
const scale = ref(1.0)
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const currentSearchIndex = ref(-1)

const canvasRef = ref<HTMLCanvasElement>()
const textLayerRef = ref<HTMLDivElement>()

// Initialize PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@4.0.379/build/pdf.worker.mjs`

// Methods to implement:
// - loadPdf(): Fetch and parse PDF
// - renderPage(pageNum): Render page to canvas
// - goToNextPage(), goToPrevPage(), goToPage(pageNum)
// - zoomIn(), zoomOut(), resetZoom()
// - searchText(): Search text in PDF
// - goToNextSearchResult(), goToPrevSearchResult()
// - handleKeyDown(): ESC to close, arrow keys for navigation

// Watch for show prop
watch(() => props.show, (newShow) => {
  if (newShow) {
    loadPdf()
  } else {
    // Cleanup
  }
})
</script>

<template>
  <div v-if="show" class="fixed inset-0 bg-black/90 z-50 flex flex-col">
    <!-- Toolbar -->
    <div class="bg-gray-900 text-white p-4 flex items-center gap-4 border-b border-gray-700">
      <span class="text-sm truncate max-w-md">{{ filePath }}</span>
      <!-- Page navigation -->
      <button @click="goToPrevPage" :disabled="currentPage <= 1">◀</button>
      <span>Page {{ currentPage }} / {{ totalPages }}</span>
      <button @click="goToNextPage" :disabled="currentPage >= totalPages">▶</button>
      <!-- Zoom controls -->
      <button @click="zoomOut">−</button>
      <span>{{ Math.round(scale * 100) }}%</span>
      <button @click="zoomIn">+</button>
      <button @click="resetZoom">Reset</button>
      <!-- Search -->
      <input v-model="searchQuery" @keyup.enter="searchText" placeholder="Search..." />
      <button @click="searchText">🔍</button>
      <button @click="goToPrevSearchResult" :disabled="currentSearchIndex < 0">◀</button>
      <span v-if="searchResults.length > 0">{{ currentSearchIndex + 1 }} / {{ searchResults.length }}</span>
      <button @click="goToNextSearchResult" :disabled="currentSearchIndex < 0">▶</button>
      <!-- Close button -->
      <button @click="$emit('close')" class="ml-auto">✕</button>
    </div>

    <!-- PDF viewer -->
    <div class="flex-1 overflow-auto flex justify-center items-center bg-gray-800">
      <div v-if="loading" class="text-white">Loading...</div>
      <div v-else-if="error" class="text-red-400">{{ error }}</div>
      <div v-else class="relative">
        <canvas ref="canvasRef"></canvas>
        <div ref="textLayerRef" class="text-layer"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.text-layer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  opacity: 0.2;
  line-height: 1;
}

.text-layer > span {
  color: transparent;
  position: absolute;
  white-space: pre;
  cursor: text;
  transform-origin: 0% 0%;
}
</style>
```

**Acceptance Criteria:**
- Component displays full-screen modal with dark background
- PDF loads and renders to canvas
- Page navigation works (prev, next, page number)
- Zoom controls work (in, out, reset)
- Text search works with results navigation
- Text selection and copy works
- ESC key closes modal
- Deep mode styling works

### Step 5: Modify CodeReviewView.vue
**File:** `frontend/src/views/CodeReviewView.vue`

Add PDF preview state and modify `loadFile` method:

```typescript
// Add imports
import PdfPreviewModal from '@/components/PdfPreviewModal.vue'

// Add state
const showPdfPreview = ref(false)
const pdfPreviewPath = ref('')

// Modify loadFile method
const loadFile = async (filePath: string | null, mode: 'editor' | 'diff' = 'editor') => {
  if (!filePath) {
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // CHECK FOR PDF: If file is PDF, show preview modal
  if (filePath.endsWith('.pdf')) {
    showPdfPreview.value = true
    pdfPreviewPath.value = filePath

    // Close sidebar and show editor on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // ... rest of existing logic
}

// Add keyboard handler for ESC when PDF preview is open
const handleKeyDown = (e: KeyboardEvent) => {
  // Existing keyboard handlers...
  if (e.key === 'Escape' && showPdfPreview.value) {
    showPdfPreview.value = false
  }
}
```

Add component to template:
```vue
<!-- PDF Preview Modal -->
<PdfPreviewModal
  v-if="showPdfPreview"
  :task-id="taskId"
  :file-path="pdfPreviewPath"
  :show="showPdfPreview"
  @close="showPdfPreview = false"
/>
```

**Acceptance Criteria:**
- Clicking `.pdf` file opens modal
- Modal closes when clicking close button or pressing ESC
- State management for PDF preview works correctly

### Step 6: Styling Polish
**File:** `frontend/src/components/PdfPreviewModal.vue`

Ensure consistent styling with existing app:
- Use same color scheme (gray/dark variants)
- Match button styles with existing buttons
- Ensure responsive layout works on mobile

**Acceptance Criteria:**
- Styling matches existing app design
- Mobile layout is usable
- Dark mode works correctly

## Testing Checklist

- [ ] Click on `.pdf` file in Files list opens modal
- [ ] PDF loads and displays correctly
- [ ] Page navigation works (prev/next buttons)
- [ ] Page number input works
- [ ] Zoom in/out buttons work
- [ ] Reset zoom button works
- [ ] Text search finds matches
- [ ] Search results navigation works
- [ ] Text can be selected and copied
- [ ] ESC key closes modal
- [ ] Close button closes modal
- [ ] Modal works in dark mode
- [ ] Modal works on mobile

## Notes

1. **PDF.js Worker**: The worker is loaded from unpkg CDN. For production, consider bundling the worker locally.

2. **Search Implementation**: PDF.js text search requires iterating through pages and building text content indexes. This can be resource-intensive for large PDFs.

3. **Text Selection**: Requires implementing a text layer over the canvas using PDF.js's `textContent` and text coordinates.

4. **Performance**: For very large PDFs, consider:
   - Lazy loading pages
   - Page caching
   - Virtual scrolling

5. **Security**: The backend endpoint already validates the path is within the worktree, preventing directory traversal.