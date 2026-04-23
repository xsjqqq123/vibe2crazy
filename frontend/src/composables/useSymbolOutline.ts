// frontend/src/composables/useSymbolOutline.ts
import { ref, type Ref } from 'vue'

export interface SymbolInfo {
  name: string
  kind: 'function' | 'class' | 'variable' | 'import' | 'constant'
  lineNumber: number
}

interface SymbolPattern {
  pattern: RegExp
  kind: SymbolInfo['kind']
  matchIndex: number // Which capture group contains the symbol name
}

// Language-specific patterns
const LANGUAGE_PATTERNS: Record<string, SymbolPattern[]> = {
  typescript: [
    { pattern: /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:export\s+)?class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?interface\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?type\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm, kind: 'variable', matchIndex: 1 },
    { pattern: /^import\s+.*?from\s+['"]([^'"]+)['"]/gm, kind: 'import', matchIndex: 1 },
  ],
  javascript: [
    { pattern: /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:export\s+)?class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm, kind: 'variable', matchIndex: 1 },
    { pattern: /^import\s+.*?from\s+['"]([^'"]+)['"]/gm, kind: 'import', matchIndex: 1 },
  ],
  python: [
    { pattern: /^(?:async\s+)?def\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^import\s+(\w+)/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^from\s+(\w+)/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^(\w+)\s*=\s*(?!.*def|.*class)/gm, kind: 'variable', matchIndex: 1 },
  ],
  vue: [
    // Use TypeScript patterns for Vue (script section typically uses TS/JS)
    { pattern: /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:export\s+)?class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?interface\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm, kind: 'variable', matchIndex: 1 },
  ],
  go: [
    { pattern: /^func\s+(?:\([^)]+\)\s+)?(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^type\s+(\w+)\s+struct/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^type\s+(\w+)\s+interface/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^import\s+["']([^"']+)["']/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^(\w+)\s*:=/gm, kind: 'variable', matchIndex: 1 },
  ],
  rust: [
    { pattern: /^(?:pub\s+)?fn\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?struct\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?enum\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?trait\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?const\s+(\w+)/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^use\s+([^;]+)/gm, kind: 'import', matchIndex: 1 },
  ],
  c: [
    // Match standard function definitions: type name(params) { or type name(params) on its own line
    { pattern: /^(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+\*?\s*(\w+)\s*\([^)]*\)\s*\{?/gm, kind: 'function', matchIndex: 1 },
    // Match macro-based function declarations like: MACRO(type) name(params)
    { pattern: /^\w+\([^)]*\)\s+(\w+)\s*\([^)]*\)/gm, kind: 'function', matchIndex: 1 },
    // Match #define constants (uppercase)
    { pattern: /^#define\s+([A-Z_][A-Z0-9_]*)/gm, kind: 'constant', matchIndex: 1 },
    // Match #include
    { pattern: /^#include\s+[<"]([^>"]+)[>"]/gm, kind: 'import', matchIndex: 1 },
    // Match struct/enum definitions
    { pattern: /^(?:typedef\s+)?struct\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:typedef\s+)?enum\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
  ],
  cpp: [
    { pattern: /^(?:static\s+)?(?:inline\s+)?(?:virtual\s+)?(?:explicit\s+)?(?:constexpr\s+)?(?:\w+\s+)+\*?\s*(\w+)\s*\([^)]*\)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:typedef\s+)?struct\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:typedef\s+)?enum\s+(?:class\s+)?(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:constexpr\s+)?const\s+([A-Z_][A-Z0-9_]*)/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^#define\s+([A-Z_][A-Z0-9_]*)/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^#include\s+[<"]([^>"]+)[>"]/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^namespace\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
  ],
}

const MAX_SYMBOLS = 100

/**
 * Remove comments from code while preserving line numbers
 * Replaces comments with whitespace of same length
 */
function removeComments(code: string, language: string): string {
  // Languages that use C-style comments
  const cStyleLanguages = ['typescript', 'javascript', 'c', 'cpp', 'java', 'csharp', 'go', 'rust', 'vue']
  // Languages that use Python-style comments
  const pythonStyleLanguages = ['python']

  let result = code

  if (cStyleLanguages.includes(language)) {
    // Remove single-line comments (// ...)
    result = result.replace(/\/\/[^\n]*/g, (match) => ' '.repeat(match.length))
    // Remove multi-line comments (/* ... */)
    result = result.replace(/\/\*[\s\S]*?\*\//g, (match) => {
      // Preserve newlines for line number calculation
      return match.replace(/[^\n]/g, ' ')
    })
  }

  if (pythonStyleLanguages.includes(language)) {
    // Remove single-line comments (# ...)
    result = result.replace(/#[^\n]*/g, (match) => ' '.repeat(match.length))
    // Remove multi-line strings (triple quotes) which are often used as docstrings
    result = result.replace(/'''[\s\S]*?'''/g, (match) => {
      return match.replace(/[^\n]/g, ' ')
    })
    result = result.replace(/"""[\s\S]*?"""/g, (match) => {
      return match.replace(/[^\n]/g, ' ')
    })
  }

  return result
}

export function useSymbolOutline() {
  const symbols: Ref<SymbolInfo[]> = ref([])

  function extractSymbols(code: string, language: string): SymbolInfo[] {
    const patterns = LANGUAGE_PATTERNS[language] || LANGUAGE_PATTERNS.typescript
    const found: SymbolInfo[] = []

    // Remove comments to avoid matching symbols in comments
    const codeWithoutComments = removeComments(code, language)

    for (const { pattern, kind, matchIndex } of patterns) {
      // Reset regex state
      pattern.lastIndex = 0
      let match
      while ((match = pattern.exec(codeWithoutComments)) !== null) {
        if (found.length >= MAX_SYMBOLS) break

        // Calculate line number from character index
        const charIndex = match.index
        const lineNumber = codeWithoutComments.substring(0, charIndex).split('\n').length
        const name = match[matchIndex]

        // Avoid duplicates (same name, same line)
        if (!found.some(s => s.name === name && s.lineNumber === lineNumber)) {
          found.push({ name, kind, lineNumber })
        }
      }
      if (found.length >= MAX_SYMBOLS) break
    }

    // Sort by line number
    found.sort((a, b) => a.lineNumber - b.lineNumber)
    symbols.value = found
    return found
  }

  return {
    symbols,
    extractSymbols
  }
}