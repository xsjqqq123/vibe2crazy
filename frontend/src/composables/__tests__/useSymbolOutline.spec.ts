// frontend/src/composables/__tests__/useSymbolOutline.spec.ts
import { describe, it, expect } from 'vitest'
import { useSymbolOutline } from '../useSymbolOutline'

describe('useSymbolOutline', () => {
  describe('extractSymbols', () => {
    it('extracts functions from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `function hello() {}
function world() {}`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'hello', kind: 'function', lineNumber: 1 })
      expect(symbols[1]).toMatchObject({ name: 'world', kind: 'function', lineNumber: 2 })
    })

    it('extracts classes from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `class UserService {}
class ProductService {}`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'UserService', kind: 'class', lineNumber: 1 })
    })

    it('extracts variables from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `const config = {}
let isLoading = false`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'config', kind: 'variable', lineNumber: 1 })
    })

    it('extracts imports from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `import { ref } from 'vue'
import axios from 'axios'`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols.length).toBeGreaterThanOrEqual(2)
      expect(symbols.some(s => s.kind === 'import')).toBe(true)
    })

    it('extracts constants (uppercase variables) from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `const API_URL = 'https://api.example.com'
const MAX_RETRIES = 3`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols.some(s => s.kind === 'constant')).toBe(true)
    })

    it('extracts functions from Python code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `def hello():
    pass

def world():
    pass`

      const symbols = extractSymbols(code, 'python')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'hello', kind: 'function', lineNumber: 1 })
    })

    it('extracts classes from Python code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `class User:
    pass

class Product:
    pass`

      const symbols = extractSymbols(code, 'python')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'User', kind: 'class', lineNumber: 1 })
    })

    it('extracts async functions from Python code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `async def fetch_data():
    pass

async def process():
    pass`

      const symbols = extractSymbols(code, 'python')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'fetch_data', kind: 'function', lineNumber: 1 })
    })

    it('extracts functions from JavaScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `function hello() {}
function world() {}`

      const symbols = extractSymbols(code, 'javascript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'hello', kind: 'function', lineNumber: 1 })
    })

    it('extracts functions from Vue code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `function setup() {}
function mounted() {}`

      const symbols = extractSymbols(code, 'vue')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'setup', kind: 'function', lineNumber: 1 })
    })

    it('extracts functions from Go code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `func main() {}
func helper() {}`

      const symbols = extractSymbols(code, 'go')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'main', kind: 'function', lineNumber: 1 })
    })

    it('extracts structs from Go code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `type User struct {}
type Product struct {}`

      const symbols = extractSymbols(code, 'go')

      expect(symbols.length).toBeGreaterThanOrEqual(2)
      expect(symbols.some(s => s.kind === 'class')).toBe(true)
    })

    it('extracts functions from Rust code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `fn main() {}
fn helper() {}`

      const symbols = extractSymbols(code, 'rust')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'main', kind: 'function', lineNumber: 1 })
    })

    it('extracts structs from Rust code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `struct User {}
struct Product {}`

      const symbols = extractSymbols(code, 'rust')

      expect(symbols.length).toBeGreaterThanOrEqual(2)
      expect(symbols.some(s => s.kind === 'class')).toBe(true)
    })

    it('returns empty array for code with no matching patterns', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `some random text without code symbols`

      const symbols = extractSymbols(code, 'unknown-lang')
      // Unknown languages fall back to TypeScript patterns, but no symbols are found
      expect(symbols).toEqual([])
    })

    it('returns empty array for empty code', () => {
      const { extractSymbols } = useSymbolOutline()

      const symbols = extractSymbols('', 'typescript')

      expect(symbols).toEqual([])
    })

    it('sorts symbols by line number', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `const a = 1
function b() {}
class C {}`

      const symbols = extractSymbols(code, 'typescript')

      const lineNumbers = symbols.map(s => s.lineNumber)
      expect(lineNumbers).toEqual([...lineNumbers].sort((a, b) => a - b))
    })

    it('limits symbols to 100 entries', () => {
      const { extractSymbols } = useSymbolOutline()
      // Generate code with 150 functions
      const code = Array.from({ length: 150 }, (_, i) => `function f${i}() {}`).join('\n')

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols.length).toBeLessThanOrEqual(100)
    })
  })
})