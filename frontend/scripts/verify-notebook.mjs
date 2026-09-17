/**
 * End-to-end check for the Markdown notebook.
 *
 * Drives the real UI through create / rename / move / pin / reorder / search /
 * delete and asserts the on-disk result at each step.
 *
 *   node scripts/verify-notebook.mjs
 */
import { chromium } from 'playwright'
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'fs'
import { join } from 'path'
import { tmpdir } from 'os'

const BASE = process.env.V2C_BASE || 'http://localhost:5173'
const PASSWORD = process.env.V2C_PASSWORD || '13559969'
const NOTES_ROOT = '/home/xusongjie/workspace/vibe2death/vibe2crazy/backend/notebooks'
// Matches DEFAULT_GROUP_NAME in backend/app/services/notebook_service.py
const DEFAULT_GROUP = 'Unsorted'
const OUT = 'screenshots/notebook'

mkdirSync(OUT, { recursive: true })

const checks = []
const check = (name, ok, detail = '') => {
  checks.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`)
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const pageProblems = []
// A 409 is expected from the deliberate duplicate-rename step.
page.on('console', (m) => {
  const text = m.text()
  if (m.type() === 'error' && !text.includes('409')) pageProblems.push(text)
})
page.on('pageerror', (e) => pageProblems.push(e.message))

// The test needs an empty notebook root. Move whatever is there aside and put
// it back afterwards, so running this never destroys real notes.
//
// The backup lives outside the notes root so a failed restore cannot cascade,
// and restoreNotes() is idempotent because it runs both explicitly and from the
// exit handler.
const BACKUP = join(tmpdir(), 'v2c-verify-notebooks-backup')

function discardBackup() {
  rmSync(BACKUP, { recursive: true, force: true })
}

let movedAside = false
let restored = false

discardBackup()
if (existsSync(NOTES_ROOT)) {
  renameSync(NOTES_ROOT, BACKUP)
  movedAside = true
  console.log(`notes moved to ${BACKUP}; will be restored at the end`)
}

function restoreNotes() {
  if (restored) return
  restored = true

  if (!movedAside) {
    // Nothing was moved, so anything present was created by this run.
    rmSync(NOTES_ROOT, { recursive: true, force: true })
    return
  }

  if (!existsSync(BACKUP)) {
    console.error(`!! backup missing at ${BACKUP}; leaving ${NOTES_ROOT} untouched`)
    return
  }
  rmSync(NOTES_ROOT, { recursive: true, force: true })
  renameSync(BACKUP, NOTES_ROOT)
  console.log('notes restored')
}

process.on('exit', restoreNotes)
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    restoreNotes()
    process.exit(1)
  })
}

// -- login + navigate -------------------------------------------------------
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
await page.fill('input[type="password"]', PASSWORD)
await page.press('input[type="password"]', 'Enter')
await page.waitForURL('**/projects', { timeout: 15000 })

await page.click('button[title="Markdown Notebook"]')
await page.waitForURL('**/notebook', { timeout: 10000 })
check('entry button navigates to /notebook', true)

// The footer buttons render before the first tree fetch resolves — wait for a row.
await page.waitForSelector('aside .group-header', { timeout: 15000 })
check('sidebar renders the default group',
  (await page.locator('aside .group-header', { hasText: 'Unsorted' }).count()) > 0)

// -- create a group ---------------------------------------------------------
const DIALOG = '[role="dialog"]'

const newGroup = async (name) => {
  await page.click('aside button[title="New group"]')
  await page.waitForSelector(DIALOG)
  await page.fill(`${DIALOG} input`, name)
  await page.click(`${DIALOG} .btn-primary`)
  await page.waitForSelector(DIALOG, { state: 'detached' })
  await page.waitForTimeout(500)
}

await newGroup('工作')
check('group directory created on disk', existsSync(join(NOTES_ROOT, '工作')))
await newGroup('学习')

// -- create a note ----------------------------------------------------------
const newNote = async (title) => {
  await page.click('aside button:has-text("New note")')
  await page.waitForSelector(DIALOG)
  await page.fill(`${DIALOG} input`, title)
  await page.click(`${DIALOG} .btn-primary`)
  await page.waitForSelector(DIALOG, { state: 'detached' })
  await page.waitForTimeout(700)
}

const openDialogInput = async (label) => {
  await page.fill(`${DIALOG} input`, label)
  await page.click(`${DIALOG} .btn-primary`)
  await page.waitForTimeout(800)
}

await newNote('架构设计')
check('note file created on disk', existsSync(join(NOTES_ROOT, DEFAULT_GROUP, '架构设计.md')))

// -- edit + autosave --------------------------------------------------------
await page.waitForSelector('.monaco-editor', { timeout: 10000 })
await page.click('.monaco-editor .view-lines')
await page.keyboard.press('Control+A')
await page.keyboard.type('# 架构总览\n\n## 第二节\n\n正文段落。\n\n```js\nconst a = 1\n```\n')
await page.waitForTimeout(2600) // autosave is 1.5s debounce
const saved = readFileSync(join(NOTES_ROOT, DEFAULT_GROUP, '架构设计.md'), 'utf8')
check('autosave wrote content to disk', saved.includes('# 架构总览'), JSON.stringify(saved.slice(0, 30)))
check('save indicator shows saved', (await page.locator('text=✓ Saved').count()) > 0)

// -- modes ------------------------------------------------------------------
await page.click('button[title="Preview only"]')
await page.waitForTimeout(500)
check('preview mode renders heading', (await page.locator('.md-content h2').count()) > 0)
check('preview mode renders highlighted code', (await page.locator('.md-content pre.hljs').count()) > 0)
check('preview mode shows outline', (await page.locator('.md-outline-item').count()) > 0)
await page.screenshot({ path: `${OUT}/01-preview.png` })

await page.click('button[title="Editor with live preview"]')
await page.waitForTimeout(700)
check('split mode shows editor and preview', (await page.locator('.monaco-editor').count()) > 0 &&
  (await page.locator('.md-content').count()) > 0)
await page.screenshot({ path: `${OUT}/02-split.png` })

await page.click('button[title="Editor only"]')
await page.waitForTimeout(500)

// -- pin + reorder ----------------------------------------------------------
for (const t of ['API草稿', '排错笔记']) await newNote(t)
const noteTitles = async () =>
  page.locator('.group-notes .note-item span:not(.pinned-icon)').allInnerTexts()

let titles = await noteTitles()
check('notes listed in creation order', titles.join(',') === '架构设计,API草稿,排错笔记', titles.join(','))

await page.click('button[title="Preview only"]')
await page.locator('.note-item', { hasText: '排错笔记' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Move up' }).click()
await page.waitForTimeout(700)
titles = await noteTitles()
// "上移" swaps with the adjacent note, it does not jump to the front.
check('reorder swaps with the previous note', titles.join(',') === '架构设计,排错笔记,API草稿', titles.join(','))

// A second move takes it to the front.
await page.locator('.note-item', { hasText: '排错笔记' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Move up' }).click()
await page.waitForTimeout(700)
titles = await noteTitles()
check('a second reorder reaches the front', titles.join(',') === '排错笔记,架构设计,API草稿', titles.join(','))

await page.locator('.note-item', { hasText: '排错笔记' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Pin' }).click()
await page.waitForTimeout(700)
check('pin shows an icon', (await page.locator('.note-item .pinned-icon').count()) === 1)

await page.locator('.note-item', { hasText: '排错笔记' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Unpin' }).click()
await page.waitForTimeout(700)
titles = await noteTitles()
// Pinning does not rewrite position, so unpinning lands back where the moves left it.
check('unpin restores the pre-pin position', titles.join(',') === '排错笔记,架构设计,API草稿', titles.join(','))

// -- rename -----------------------------------------------------------------
await page.locator('.note-item', { hasText: 'API草稿' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Rename' }).click()
await page.waitForSelector(DIALOG)
await openDialogInput('API设计草稿')
check('rename moves the file on disk',
  existsSync(join(NOTES_ROOT, DEFAULT_GROUP, 'API设计草稿.md')) &&
  !existsSync(join(NOTES_ROOT, DEFAULT_GROUP, 'API草稿.md')))

// rename onto an existing name must be refused
await page.locator('.note-item', { hasText: 'API设计草稿' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Rename' }).click()
await page.waitForSelector(DIALOG)
await openDialogInput('排错笔记')
const conflictShown = (await page.locator('text=already exists').count()) > 0
check('duplicate rename is refused with an error', conflictShown)
await page.click(`${DIALOG} .btn-secondary`) // cancel
await page.waitForSelector(DIALOG, { state: 'detached' })

// -- move between groups ----------------------------------------------------
await page.locator('.note-item', { hasText: '排错笔记' }).click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Move to group' }).click()
await page.waitForSelector(DIALOG)
await page.locator(`${DIALOG} label`, { hasText: '工作' }).click()
await page.click(`${DIALOG} .btn-primary`)
await page.waitForSelector(DIALOG, { state: 'detached' })
await page.waitForTimeout(700)
check('move puts the file in the target group directory',
  existsSync(join(NOTES_ROOT, '工作', '排错笔记.md')) &&
  !existsSync(join(NOTES_ROOT, DEFAULT_GROUP, '排错笔记.md')))

// -- search -----------------------------------------------------------------
await page.fill('input[placeholder="Search names and contents…"]', '架构')
await page.waitForTimeout(900)
const nameHit = await page.locator('.search-result').first().innerText()
check('search finds by filename', (await page.locator('.search-result').count()) > 0)
check('filename match is labelled', nameHit.includes('Name'), nameHit.replace(/\n/g, ' ').slice(0, 40))
check('search shows a match badge', (await page.locator('.match-badge').count()) > 0)
await page.screenshot({ path: `${OUT}/03-search.png` })

await page.fill('input[placeholder="Search names and contents…"]', '正文段落')
await page.waitForTimeout(900)
const bodyHit = await page.locator('.search-result').first().innerText()
check('search finds by content with a snippet', bodyHit.includes('正文段落'), bodyHit.replace(/\n/g, ' ').slice(0, 60))
check('content match is labelled', bodyHit.includes('Body'))
await page.fill('input[placeholder="Search names and contents…"]', '')
await page.waitForTimeout(500)
check('clearing the query restores the tree', (await page.locator('.group-header').count()) >= 2)

// -- external changes -------------------------------------------------------
writeFileSync(join(NOTES_ROOT, DEFAULT_GROUP, '来自终端.md'), '# 外部写入\n', 'utf8')
mkdirSync(join(NOTES_ROOT, '终端组'), { recursive: true })
await page.click('button[title="Refresh (rescan disk)"]')
await page.waitForTimeout(900)
check('reconcile picks up an external file', (await page.locator('.note-item', { hasText: '来自终端' }).count()) > 0)
check('reconcile picks up an external directory', (await page.locator('.group-header', { hasText: '终端组' }).count()) > 0)

rmSync(join(NOTES_ROOT, DEFAULT_GROUP, '来自终端.md'))
await page.click('button[title="Refresh (rescan disk)"]')
await page.waitForTimeout(900)
check('reconcile drops a deleted file', (await page.locator('.note-item', { hasText: '来自终端' }).count()) === 0)

// -- delete -----------------------------------------------------------------
await page.locator('.note-item', { hasText: '架构设计' }).first().click()
await page.waitForTimeout(700)
await page.locator('.note-item', { hasText: '架构设计' }).first().click({ button: 'right' })
await page.waitForSelector('.context-menu')
await page.locator('.context-menu-item', { hasText: 'Delete' }).click()
await page.waitForTimeout(500)
check('delete asks for confirmation', (await page.locator('.dialog .btn-danger', { hasText: 'Delete' }).count()) > 0)
await page.click('.dialog .btn-danger')
await page.waitForTimeout(1000)
check('delete removes the file from disk', !existsSync(join(NOTES_ROOT, DEFAULT_GROUP, '架构设计.md')))

// -- sidebar toggle + divider theming --------------------------------------
const splitterStyle = () =>
  page.evaluate(() => {
    const el = document.querySelector('.splitpanes__splitter')
    if (!el) return null
    const cs = getComputedStyle(el)
    return {
      borderLeftWidth: cs.borderLeftWidth,
      borderLeftColor: cs.borderLeftColor,
      backgroundColor: cs.backgroundColor,
      visible: cs.display !== 'none'
    }
  })

const editorWidth = () =>
  page.evaluate(() => {
    const panes = document.querySelectorAll('.splitpanes__pane')
    const el = panes[panes.length - 1]
    return el ? Math.round(el.getBoundingClientRect().width) : 0
  })

const sidebarVisible = () =>
  page.evaluate(() => {
    const pane = document.querySelector('.splitpanes__pane')
    return !!pane && getComputedStyle(pane).display !== 'none'
  })

// The divider must not inherit splitpanes' bundled `border-left: 1px solid #eee`,
// which read as a bright line on the dark themes.
const divider = await splitterStyle()
check('divider has no light border', divider?.borderLeftWidth === '0px',
  `border-left=${divider?.borderLeftWidth} ${divider?.borderLeftColor}`)
check('divider uses a theme colour', divider?.backgroundColor !== 'rgb(238, 238, 238)' &&
  divider?.backgroundColor !== 'rgb(255, 255, 255)', `bg=${divider?.backgroundColor}`)

const widthWithSidebar = await editorWidth()
check('sidebar starts visible', await sidebarVisible())

await page.click('button[title="Hide note list"]')
await page.waitForTimeout(600)
check('sidebar hides', !(await sidebarVisible()))
const widthWithoutSidebar = await editorWidth()
check('editor grows to full width', widthWithoutSidebar > widthWithSidebar,
  `${widthWithSidebar} -> ${widthWithoutSidebar}`)
await page.screenshot({ path: `${OUT}/05-sidebar-hidden.png` })

await page.click('button[title="Show note list"]')
await page.waitForTimeout(600)
check('sidebar shows again', await sidebarVisible())
check('editor shrinks back', Math.abs((await editorWidth()) - widthWithSidebar) < 30,
  `${await editorWidth()} vs ${widthWithSidebar}`)

// the choice must survive a reload
await page.click('button[title="Hide note list"]')
await page.waitForTimeout(400)
await page.reload({ waitUntil: 'networkidle' })
await page.waitForSelector('button[title="Show note list"]', { timeout: 15000 })
await page.waitForTimeout(900)
check('hidden sidebar state persists across a reload', !(await sidebarVisible()))
await page.click('button[title="Show note list"]')
await page.waitForTimeout(500)

// -- unsaved content survives a note switch --------------------------------
// Type, then switch within the 1.5s autosave window: the write must be flushed
// on the way out rather than dropped.
await page.click('button[title="Editor only"]')
await page.waitForSelector('.monaco-editor .view-lines')
await page.locator('.note-item', { hasText: '排错笔记' }).first().click()
await page.waitForTimeout(700)
await page.click('.monaco-editor .view-lines')
await page.keyboard.press('Control+A')
await page.keyboard.type('# 切换前写入的内容\n')
await page.waitForTimeout(200) // well inside the autosave debounce
await page.locator('.note-item', { hasText: 'API设计草稿' }).first().click()
await page.waitForTimeout(1200)

const flushed = readFileSync(join(NOTES_ROOT, '工作', '排错笔记.md'), 'utf8')
check('switching notes flushes the pending edit', flushed.includes('切换前写入的内容'),
  JSON.stringify(flushed.slice(0, 40)))

// and it must still be on disk after switching back
await page.locator('.note-item', { hasText: '排错笔记' }).first().click()
await page.waitForTimeout(1200)
const reloaded = await page.locator('.monaco-editor .view-lines').innerText()
check('the flushed content reloads into the editor', reloaded.includes('切换前写入的内容'))

// -- external edit conflict ------------------------------------------------
// Edit in the app, change the file underneath from "outside", then let
// autosave fire: it must notice and ask rather than clobber.
await page.click('button[title="Editor only"]')
await page.waitForSelector('.monaco-editor .view-lines')
await page.locator('.note-item', { hasText: 'API设计草稿' }).first().click()
await page.waitForTimeout(800)

const conflictFile = join(NOTES_ROOT, DEFAULT_GROUP, 'API设计草稿.md')
await page.click('.monaco-editor .view-lines')
await page.keyboard.press('Control+A')
await page.keyboard.type('来自编辑器的新内容\n')

// Same instant, from outside the app.
writeFileSync(conflictFile, '来自外部工具的内容\n', 'utf8')

await page.waitForTimeout(2600) // let autosave fire
const dialogShown = (await page.locator('.dialog', { hasText: 'File changed on disk' }).count()) > 0
check('an external edit raises a conflict prompt', dialogShown)
await page.screenshot({ path: `${OUT}/04-conflict.png` })

if (dialogShown) {
  // Choosing overwrite must win.
  await page.locator('.dialog .btn-danger').click()
  await page.waitForTimeout(1200)
  const after = readFileSync(conflictFile, 'utf8')
  check('choosing overwrite writes the editor content', after.includes('来自编辑器的新内容'),
    JSON.stringify(after.slice(0, 30)))
}

// -- themes -----------------------------------------------------------------
const themeClass = () =>
  page.evaluate(() =>
    [...document.documentElement.classList].find((c) => c.startsWith('theme-')) || ''
  )

/** Cycle the theme button until the requested theme is active. */
const setTheme = async (target) => {
  for (let attempt = 0; attempt < 5; attempt++) {
    if ((await themeClass()) === `theme-${target}`) return true
    await page.click('button[title="Cycle theme"]')
    await page.waitForTimeout(350)
  }
  return false
}

// Seed the preview with content so the theme screenshots show rendered markdown.
await page.locator('.note-item', { hasText: 'API设计草稿' }).click()
await page.waitForTimeout(800)
await page.click('button[title="Editor only"]')
await page.waitForSelector('.monaco-editor .view-lines')
await page.click('.monaco-editor .view-lines')
await page.keyboard.press('Control+A')
await page.keyboard.type('# 主题检查\n\n## 二级标题\n\n正文文本。\n\n```js\nconst a = 1\n```\n')
await page.waitForTimeout(2600)
await page.click('button[title="Preview only"]')
await page.waitForTimeout(600)

const before = await themeClass()
await page.click('button[title="Cycle theme"]')
await page.waitForTimeout(400)
check('theme button changes the theme', (await themeClass()) !== before, `${before} -> ${await themeClass()}`)

for (const theme of ['light', 'dark', 'green', 'parchment']) {
  check(`theme ${theme} applies`, await setTheme(theme))
  await page.screenshot({ path: `${OUT}/theme-${theme}.png` })
}

// -- final state ------------------------------------------------------------
console.log('\nSUMMARY')
const failed = checks.filter((c) => !c.ok)
console.log(`  ${checks.length - failed.length}/${checks.length} checks passed`)
if (failed.length) failed.forEach((f) => console.log(`  FAILED: ${f.name} — ${f.detail}`))
console.log(pageProblems.length ? `\nPAGE ERRORS:\n  ${pageProblems.join('\n  ')}` : '\nno page errors')

await browser.close()
restoreNotes()
process.exit(failed.length ? 1 : 0)
