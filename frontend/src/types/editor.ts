/**
 * Shared editor types for CodeReviewView, EditorView, and EditorHistoryDropdown
 */

/**
 * History entry structure for tracking file navigation history
 */
export interface HistoryEntry {
  filePath: string
  cursorPosition: { line: number; column: number }
  scrollPosition: { top: number; left: number }
  timestamp: number
}

/**
 * Editor view state for tracking file content and position
 */
export interface EditorViewState {
  filePath: string | null
  fileContent: string
  originalContent: string
  editorMode: 'editor' | 'diff' | 'commit-diff' | 'deleted' | 'conflict'
  history: HistoryEntry[]
  cursorPosition: { line: number; column: number } | null
  scrollPosition: { top: number; left: number } | null
  isFileDeleted: boolean
}

/**
 * View type for the editor
 * - main: Primary editor view (editable)
 * - preview1: First preview pane (read-only)
 * - preview2: Second preview pane (read-only)
 */
export type ViewType = 'main' | 'preview1' | 'preview2'