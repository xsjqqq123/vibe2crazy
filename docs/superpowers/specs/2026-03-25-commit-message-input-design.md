# Commit Message Input and Display Feature Design

## Overview

When accepting changes, prompt user for a commit message. Display the commit message as the title in the commits list.

## User Flow

1. User clicks "Accept Changes" button
2. Modal dialog appears with textarea pre-filled with default message
3. User edits message or accepts default
4. On confirm, changes are committed with the custom message
5. Commits list shows commit message as title, with date moved to top right

## Technical Design

### Frontend Changes

**File: `frontend/src/views/CodeReviewView.vue`**

Replace the existing `showConfirm` in `handleAccept` with a custom modal:

```typescript
// Add state for commit message modal
const commitMessageModal = ref({
  show: false,
  message: ''
})

// Update handleAccept to show modal instead of confirm dialog
const handleAccept = () => {
  commitMessageModal.value = {
    show: true,
    message: `Accept changes for ${task.value?.name}`
  }
}

// New function to confirm with message
const confirmAccept = async () => {
  await tasksApi.accept(taskId.value, commitMessageModal.value.message)
  // ... rest of accept logic
}
```

Add modal template with textarea.

**File: `frontend/src/components/CommitsList.vue`**

Update layout:

```vue
<!-- Header: Hash and Date -->
<div class="flex items-center justify-between mb-1">
  <code class="text-xs font-mono text-accent">{{ commit.hash.slice(0, 8) }}</code>
  <span class="text-xs text-muted">{{ formatLocalDateTime(commit.date) }}</span>
</div>

<!-- Title: Commit message -->
<p class="text-sm text-main mb-2">
  {{ commit.message || 'No message' }}
</p>

<!-- Files... -->
```

### Backend

No changes needed. Backend already:
- Accepts `message` parameter in `/tasks/{task_id}/accept` endpoint
- Returns `message` in `CommitInfo` from commits API

## Component Reuse

- Reuse existing modal styling pattern from confirmation dialogs
- Use existing textarea styling from settings forms