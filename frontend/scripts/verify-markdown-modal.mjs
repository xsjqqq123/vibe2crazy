/**
 * Regression check for MarkdownPreviewModal after the MarkdownPane extraction.
 *
 * Logs in, imports test-mermaid.md through the Projects page, then screenshots
 * the preview in all four themes. Run with the app up:
 *
 *   node scripts/verify-markdown-modal.mjs
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.V2C_BASE || 'http://localhost:5173'
const PASSWORD = process.env.V2C_PASSWORD || '13559969'
const MD_FILE = process.env.V2C_MD || '/home/xusongjie/workspace/vibe2death/vibe2crazy/test-mermaid.md'
const OUT = 'screenshots/markdown-modal'

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const problems = []
page.on('console', (m) => {
  if (m.type() === 'error') problems.push(`console: ${m.text()}`)
})
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))

// -- login --
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
await page.fill('input[type="password"]', PASSWORD)
await page.press('input[type="password"]', 'Enter')
await page.waitForURL('**/projects', { timeout: 15000 })

// -- open the markdown import dialog --
await page.click('button[title="Preview Markdown"]')
await page.waitForSelector('text=Import Markdown')

// -- upload the fixture --
const [chooser] = await Promise.all([
  page.waitForEvent('filechooser'),
  page.click('text=Drag & drop a .md file, or click to select'),
])
await chooser.setFiles(MD_FILE)

// -- the preview modal should take over --
await page.waitForSelector('.md-modal-container', { timeout: 10000 })
// 15 diagrams take a while to hydrate; wait for the last one rather than a fixed nap.
await page.waitForFunction(
  () => {
    const nodes = document.querySelectorAll('.md-content .mermaid')
    return nodes.length > 0 && [...nodes].every((n) => n.querySelector('svg'))
  },
  { timeout: 20000 }
)

const checks = {
  headings: await page.locator('.md-content h1').count(),
  headingsWithId: await page.locator('.md-content h1[id]').count(),
  codeBlocks: await page.locator('.md-content pre.hljs').count(),
  tables: await page.locator('.md-content table').count(),
  mermaidPlaceholders: await page.locator('.md-content .mermaid').count(),
  mermaidSvgs: await page.locator('.md-content .mermaid svg').count(),
  outlineItems: await page.locator('.md-outline-item').count(),
  outlineActive: await page.locator('.md-outline-item.is-active').count(),
}
console.log('checks:', JSON.stringify(checks, null, 2))

// -- screenshot every theme --
for (const theme of ['light', 'dark', 'green', 'parchment']) {
  await page.evaluate((t) => {
    const root = document.documentElement
    root.classList.remove('theme-light', 'theme-dark', 'theme-green', 'theme-parchment', 'dark')
    root.classList.add(`theme-${t}`)
    if (t === 'dark') root.classList.add('dark')
  }, theme)
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/${theme}.png` })
  console.log(`shot: ${OUT}/${theme}.png`)
}

// -- outline click should scroll --
const before = await page.locator('.md-scroll-content').evaluate((el) => el.scrollTop)
await page.locator('.md-outline-item').last().click()
await page.waitForTimeout(900)
const after = await page.locator('.md-scroll-content').evaluate((el) => el.scrollTop)
console.log(`outline scroll: ${before} -> ${after}`, after > before ? 'OK' : 'NO MOVEMENT')

if (problems.length) {
  console.log('\nPAGE PROBLEMS:')
  problems.forEach((p) => console.log('  -', p))
} else {
  console.log('\nno console/page errors')
}

await browser.close()
