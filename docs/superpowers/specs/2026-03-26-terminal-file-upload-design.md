# Terminal File Upload Feature Design

## Overview

Add file upload capability to the terminal control bar, allowing users to upload files to a temp directory via file selection, drag-and-drop, or clipboard image paste.

## Requirements

1. **Upload button** in terminal control bar
2. **Modal dialog** with:
   - Drag-and-drop zone
   - Click to select files
   - Clipboard image paste support (Ctrl+V)
3. **Upload progress** display with progress bar, percentage, and speed
4. **Results display** showing saved file paths with copy buttons
5. Files saved to **fixed temp directory**

## Configuration

- **Upload size limit**: 100MB per file (configurable via `MAX_UPLOAD_SIZE` env var, default 104857600 bytes)
- **Temp directory**: `/tmp/vibe2crazy-upload` (configurable via `TEMP_UPLOAD_DIR` env var)
- **Cleanup policy**: Temp files are NOT automatically deleted. Users should manually clean or use system temp cleanup.

## Technical Design

### Frontend

#### 1. New Component: `UploadModal.vue`

Location: `frontend/src/components/Terminal/UploadModal.vue`

```vue
<script setup lang="ts">
interface Props {
  taskId: string
}

interface UploadResult {
  filename: string
  path: string
  size: number
  success: boolean
  error?: string
}

// State
const isUploading = ref(false)
const progress = ref(0)
const uploadSpeed = ref('')
const results = ref<UploadResult[]>([])

// Drag state
const isDragging = ref(false)

// Methods
const handleFileSelect = (files: FileList) => { ... }
const handleDrop = (e: DragEvent) => { ... }
const handlePaste = async (e: ClipboardEvent) => { ... }
const uploadFiles = async (files: File[]) => { ... }
const copyPath = (path: string) => { ... }
const reset = () => { ... }
</script>
```

**UI Layout:**

```
┌─────────────────────────────────────────────┐
│  Upload Files                          [X]  │
├─────────────────────────────────────────────┤
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │    ☁️                                │   │
│   │    Drag files here                   │   │
│   │    or click to select                │   │
│   │    Ctrl+V to paste image             │   │
│   └─────────────────────────────────────┘   │
│                                             │
├─────────────────────────────────────────────┤
│  Uploading... 45%                           │
│  [████████████░░░░░░░░░░░] 2.3 MB/s        │
├─────────────────────────────────────────────┤
│  Results:                                   │
│                                             │
│  ✓ example.txt                             │
│    /tmp/vibe2crazy-upload/.../example.txt  │
│    14.2 KB                      [Copy]     │
│                                             │
│  ✓ screenshot-20260326-103045.png          │
│    /tmp/vibe2crazy-upload/.../screenshot.. │
│    256.8 KB                     [Copy]     │
│                                             │
│  [Upload More]                              │
└─────────────────────────────────────────────┘
```

#### 2. Terminal.vue Changes

Add to terminal control bar (after TODO button):

```vue
<button
  @click="showUploadModal = true"
  :disabled="!connected"
  class="control-btn control-btn-action"
  title="Upload files"
>
  UPLOAD
</button>
```

Add modal state and component:

```vue
const showUploadModal = ref(false)

<UploadModal
  v-if="showUploadModal"
  :task-id="taskId"
  @close="showUploadModal = false"
/>
```

#### 3. API Client Addition

Add to `frontend/src/api/files.ts`:

```typescript
interface TempUploadResult {
  filename: string
  path: string
  size: number
}

interface TempUploadResponse {
  success: boolean
  results: TempUploadResult[]
  temp_dir: string
}

uploadToTemp: async (taskId: string, files: FileList, onProgress?: ProgressCallback): Promise<TempUploadResponse> => {
  const formData = new FormData()
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i])
  }

  const token = localStorage.getItem('auth_token')
  const xhr = new XMLHttpRequest()

  // ... XHR upload with progress tracking
}
```

### Backend

#### New Endpoint: `POST /tasks/{task_id}/upload-temp`

Location: `backend/app/routers/files.py`

```python
import tempfile
import os
from datetime import datetime

TEMP_UPLOAD_DIR = "/tmp/vibe2crazy-upload"

@router.post("/{task_id}/upload-temp", response_model=TempUploadResponse)
async def upload_to_temp(
    task_id: str,
    files: List[UploadFile] = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth)
):
    """
    Upload files to a temporary directory.
    Returns paths for user to reference in terminal.
    """
    # Create task-specific temp directory
    task_temp_dir = os.path.join(TEMP_UPLOAD_DIR, task_id)
    os.makedirs(task_temp_dir, exist_ok=True)

    results = []
    for file in files:
        # Generate unique filename if needed
        filename = generate_unique_filename(task_temp_dir, file.filename)
        file_path = os.path.join(task_temp_dir, filename)

        # Save file
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        results.append({
            "filename": filename,
            "path": file_path,
            "size": len(content)
        })

    return {
        "success": True,
        "results": results,
        "temp_dir": task_temp_dir
    }
```

#### Filename Generation

```python
def generate_unique_filename(directory: str, filename: str) -> str:
    """Generate unique filename, appending number if needed."""
    base, ext = os.path.splitext(filename)
    counter = 1
    result = filename

    while os.path.exists(os.path.join(directory, result)):
        result = f"{base}-{counter}{ext}"
        counter += 1

    return result

def generate_screenshot_filename() -> str:
    """Generate timestamped filename for clipboard images."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"screenshot-{timestamp}.png"
```

### File Naming Rules

| Source | Filename Pattern |
|--------|-----------------|
| File picker/drag | Original filename (append `-N` if duplicate) |
| Clipboard image | `screenshot-{YYYYMMDD-HHmmss}.png` |

### Progress Tracking

Using XMLHttpRequest for progress events:

```typescript
xhr.upload.onprogress = (e) => {
  if (e.lengthComputable) {
    const percentComplete = (e.loaded / e.total) * 100
    progress.value = Math.round(percentComplete)

    // Calculate speed
    const timeElapsed = (Date.now() - startTime) / 1000
    const speed = e.loaded / timeElapsed
    uploadSpeed.value = formatSpeed(speed)
  }
}
```

### Error Handling

- Network error: Show error message, offer retry
- File too large: Show size limit message
- Permission denied: Show error in results
- Partial failure: Show successful uploads with paths, failed ones with error

## Files to Create/Modify

| File | Action |
|------|--------|
| `frontend/src/components/Terminal/UploadModal.vue` | Create |
| `frontend/src/components/Terminal/Terminal.vue` | Modify |
| `frontend/src/api/files.ts` | Modify |
| `backend/app/routers/files.py` | Modify |

## Verification

1. Click Upload button → Modal opens
2. Drag file onto drop zone → Upload starts, progress shows
3. Click drop zone → File picker opens
4. Ctrl+V with image in clipboard → Image uploads with timestamped filename
5. Upload completes → Results show with paths
6. Click Copy button → Path copied to clipboard
7. Verify files exist at displayed paths in terminal
8. Test multiple files → All uploaded, all paths shown
9. Test duplicate filenames → Number appended correctly