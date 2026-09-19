/**
 * End-to-end check for the .vscode/tasks.json helper.
 *
 * Opens that file in the code editor and asserts the task list pops up, that
 * both commands are shown, and that copying works.
 *
 *   node scripts/verify-tasks-modal.mjs
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.V2C_BASE || 'http://localhost:5173'
const PASSWORD = process.env.V2C_PASSWORD || '13559969'
// The vibe2crazy project's worktree is this repository.
const PROJECT_ID = process.env.V2C_PROJECT || 'acbb3b53-0f90-411f-afdd-1a38b564ce80'
const OUT = 'screenshots/tasks-modal'

mkdirSync(OUT, { recursive: true })

const checks = []
const check = (name, ok, detail = '') => {
  checks.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`)
}

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  permissions: ['clipboard-read', 'clipboard-write']
})
const page = await context.newPage()
const pageProblems = []
page.on('console', (m) => m.type() === 'error' && pageProblems.push(m.text()))
page.on('pageerror', (e) => pageProblems.push(e.message))

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
await page.fill('input[type="password"]', PASSWORD)
await page.press('input[type="password"]', 'Enter')
await page.waitForURL('**/projects', { timeout: 15000 })

await page.goto(`${BASE}/projects/${PROJECT_ID}`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

const DIALOG = '.vt-overlay'

// -- open .vscode/tasks.json from the file tree ----------------------------
const treeItem = (name) => page.locator('.file-tree-item', { hasText: name }).first()

await treeItem('.vscode').click()
await page.waitForTimeout(1200)
check('.vscode is listed in the file tree', (await treeItem('.vscode').count()) > 0)

await treeItem('tasks.json').click()
await page.waitForSelector(DIALOG, { timeout: 10000 })
check('opening tasks.json pops the task list', true)

// -- contents ---------------------------------------------------------------
const rows = await page.locator('.vt-task').count()
check('lists every task', rows === 13, `${rows} rows`)

const text = await page.locator(DIALOG).innerText()
check('shows the vtr command', text.includes("vtr 'deploy: start'"), text.split('\n')[3])
check('shows the underlying command', text.includes('./deploy.sh start'))
check('shows a task with only dependsOn', text.includes('vtr ci'))
check('shows dependsOn metadata', text.includes('Runs after: typecheck: frontend, test: backend'))
check('warns about unexpanded variables', text.includes('will not expand them'))
check('shows group badges', text.includes('test') && text.includes('build'))

await page.screenshot({ path: `${OUT}/01-modal.png` })

// -- copy -------------------------------------------------------------------
const vtrRow = page.locator('.vt-task', { hasText: 'deploy: start' }).first()
const vtrCopy = vtrRow.locator('.vt-copy').first()
await vtrCopy.click()
await page.waitForTimeout(250)
check('copy button confirms itself', (await vtrCopy.innerText()).includes('Copied'),
  await vtrCopy.innerText())

const clipboard = await page.evaluate(() => navigator.clipboard.readText())
check('clipboard holds the vtr command', clipboard === "vtr 'deploy: start'", JSON.stringify(clipboard))

const rawCopy = vtrRow.locator('.vt-copy').nth(1)
await rawCopy.click()
await page.waitForTimeout(250)
const clipboard2 = await page.evaluate(() => navigator.clipboard.readText())
check('clipboard holds the raw command', clipboard2 === './deploy.sh start', JSON.stringify(clipboard2))

await page.screenshot({ path: `${OUT}/02-copied.png` })

// -- dismissal behaviour ----------------------------------------------------
await page.keyboard.press('Escape')
await page.waitForTimeout(400)
check('Escape closes the dialog', (await page.locator(DIALOG).count()) === 0)

// Reopening the same file brings it back.
await treeItem('CLAUDE.md').click()
await page.waitForTimeout(800)
await treeItem('tasks.json').click()
await page.waitForTimeout(1200)
check('reopening the file shows it again', (await page.locator(DIALOG).count()) === 1)
await page.keyboard.press('Escape')
await page.waitForTimeout(400)

// Opening a different file must not show it.
await treeItem('deploy.sh').click()
await page.waitForTimeout(1200)
check('other files do not trigger it', (await page.locator(DIALOG).count()) === 0)

console.log('\nSUMMARY')
const failed = checks.filter((c) => !c.ok)
console.log(`  ${checks.length - failed.length}/${checks.length} checks passed`)
if (failed.length) failed.forEach((f) => console.log(`  FAILED: ${f.name} — ${f.detail}`))
console.log(pageProblems.length ? `\nPAGE ERRORS:\n  ${pageProblems.join('\n  ')}` : '\nno page errors')

await browser.close()
process.exit(failed.length ? 1 : 0)
