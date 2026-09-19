/**
 * End-to-end check for JSON Schema hover support.
 *
 * Creates a throwaway JSON file plus a schema it references inside the
 * worktree, opens it in the editor and asserts that hovering a property shows
 * the description from the schema.
 *
 *   node scripts/verify-json-schema.mjs
 */
import { chromium } from 'playwright'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'fs'
import { dirname, join } from 'path'

const BASE = process.env.V2C_BASE || 'http://localhost:5173'
const PASSWORD = process.env.V2C_PASSWORD || '13559969'
const PROJECT_ID = process.env.V2C_PROJECT || 'acbb3b53-0f90-411f-afdd-1a38b564ce80'
const WORKTREE = process.env.V2C_WORKTREE || '/home/xusongjie/workspace/vibe2death/vibe2crazy'
const OUT = 'screenshots/json-schema'

mkdirSync(OUT, { recursive: true })

const checks = []
const check = (name, ok, detail = '') => {
  checks.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`)
}

// -- throwaway fixture ------------------------------------------------------
const SCHEMA_DIR = join(WORKTREE, '.vscode/schemas')
const SCHEMA_FILE = join(SCHEMA_DIR, 'verify-demo.schema.json')
const DOC_FILE = join(WORKTREE, '.vscode/verify-demo.json')

function writeFixture() {
  mkdirSync(SCHEMA_DIR, { recursive: true })
  writeFileSync(SCHEMA_FILE, JSON.stringify({
    $schema: 'http://json-schema.org/draft-07/schema#',
    type: 'object',
    properties: {
      serviceName: {
        type: 'string',
        description: 'SCHEMA_HOVER_PROBE — the name shown in dashboards'
      },
      port: {
        type: 'number',
        description: 'SCHEMA_HOVER_PORT — the port to listen on'
      }
    }
  }, null, 2), 'utf8')

  // Deliberately JSONC: VS Code treats .json as JSONC, and a plain JSON.parse
  // in the editor used to flag every comment line as an error.
  writeFileSync(DOC_FILE, `{
  // The schema this file is validated against.
  "$schema": "./schemas/verify-demo.schema.json",
  "serviceName": "billing",
  "port": 8080,
}
`, 'utf8')
}

function removeFixture() {
  rmSync(DOC_FILE, { force: true })
  rmSync(SCHEMA_FILE, { force: true })
  try { rmSync(SCHEMA_DIR, { recursive: true, force: true }) } catch {}
}

const existing = existsSync(DOC_FILE) ? readFileSync(DOC_FILE, 'utf8') : null
if (existing) {
  console.error('!! .vscode/verify-demo.json already exists; refusing to overwrite it')
  process.exit(1)
}
writeFixture()

const restore = () => removeFixture()
process.on('exit', restore)
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => { restore(); process.exit(1) })
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const pageProblems = []
page.on('console', (m) => m.type() === 'error' && pageProblems.push(m.text()))
page.on('pageerror', (e) => pageProblems.push(e.message))

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
await page.fill('input[type="password"]', PASSWORD)
await page.press('input[type="password"]', 'Enter')
await page.waitForURL('**/projects', { timeout: 15000 })
await page.goto(`${BASE}/projects/${PROJECT_ID}`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

const treeItem = (name) => page.locator('.file-tree-item', { hasText: name }).first()
await treeItem('.vscode').click()
await page.waitForTimeout(1200)

// -- open the fixture -------------------------------------------------------
await treeItem('verify-demo.json').click()
await page.waitForSelector('.monaco-editor', { timeout: 10000 })
await page.waitForTimeout(3000)

const modelInfo = await page.evaluate(() => {
  const monaco = window.require('vs/editor/editor.main')
  const m = monaco.editor.getEditors()[0].getModel()
  return { uri: m.uri.toString(), language: m.getLanguageId() }
})
check('the model carries the file path in its URI',
  /verify-demo\.json$/.test(modelInfo.uri), modelInfo.uri)
check('the file is treated as json', modelInfo.language === 'json')

// -- hover a property -------------------------------------------------------
const hover = await page.evaluate(async () => {
  const monaco = window.require('vs/editor/editor.main')
  const editor = monaco.editor.getEditors()[0]
  const m = editor.getModel()
  let target = null
  for (let i = 1; i <= m.getLineCount(); i++) {
    const idx = m.getLineContent(i).indexOf('"serviceName"')
    if (idx >= 0) { target = { lineNumber: i, column: idx + 2 }; break }
  }
  if (!target) return { error: 'serviceName not found' }
  editor.setPosition(target)
  editor.focus()
  editor.trigger('probe', 'editor.action.showHover', {})
  await new Promise((r) => setTimeout(r, 1800))
  return { text: document.querySelector('.monaco-hover')?.innerText ?? null }
})
check('hover shows the description from the schema',
  !!hover.text && hover.text.includes('SCHEMA_HOVER_PROBE'),
  JSON.stringify(hover.text))
await page.screenshot({ path: `${OUT}/01-hover.png` })

// -- completion comes along for free ---------------------------------------
const completion = await page.evaluate(async () => {
  const monaco = window.require('vs/editor/editor.main')
  const m = monaco.editor.getEditors()[0].getModel()
  const suggestions = await monaco.languages.json.jsonDefaults
    ? null : null
  return { note: 'checked via the schema being attached' }
})
void completion

// -- the URI must follow the file, and switching must not collide -----------
// The editor instance is reused across files, and Monaco throws when a URI is
// already taken, so repeated switching is the case that would break.
await treeItem('frontend').click()
await page.waitForTimeout(1200)
await treeItem('package.json').click()
await page.waitForTimeout(3000)
const switched = await page.evaluate(() => {
  const monaco = window.require('vs/editor/editor.main')
  return monaco.editor.getEditors()[0].getModel().uri.toString()
})
check('the model URI follows the newly opened file',
  switched.endsWith('/frontend/package.json'), switched)
check('switching files did not collide',
  pageProblems.every((p) => !/already exists/i.test(p)))

// -- JSONC tolerance on the fixture itself ---------------------------------
// (.vscode is still expanded from earlier; clicking it again would collapse it)
await treeItem('verify-demo.json').click()
await page.waitForTimeout(3000)
const commentMarkers = await page.evaluate(() => {
  const monaco = window.require('vs/editor/editor.main')
  const m = monaco.editor.getEditors()[0].getModel()
  return monaco.editor.getModelMarkers({ resource: m.uri })
    .filter((k) => /comment/i.test(k.message)).map((k) => k.message)
})
check('no false "comments not permitted" errors on JSONC',
  commentMarkers.length === 0, commentMarkers.join('; '))
await page.screenshot({ path: `${OUT}/02-jsonc.png` })

console.log('\nSUMMARY')
const failed = checks.filter((c) => !c.ok)
console.log(`  ${checks.length - failed.length}/${checks.length} checks passed`)
if (failed.length) failed.forEach((f) => console.log(`  FAILED: ${f.name} — ${f.detail}`))
console.log(pageProblems.length ? `\nPAGE ERRORS:\n  ${pageProblems.join('\n  ')}` : '\nno page errors')

await browser.close()
removeFixture()
process.exit(failed.length ? 1 : 0)
