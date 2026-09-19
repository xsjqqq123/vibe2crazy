/**
 * JSON Schema support for the code editor.
 *
 * Once a schema is attached to a document, Monaco shows the schema's
 * `description` on hover, validates against it, and completes property names.
 *
 * Schemas are resolved from the workspace, never fetched from the network:
 *   - the document's own `$schema`, when it points at a file in the worktree
 *   - `.vscode/settings.json` -> `json.schemas` (the VS Code mechanism)
 *
 * Monaco's JSON worker serves these features and already runs in this app —
 * the AMD loader resolves it from `/vs`, so no build changes are needed.
 */
import { loader } from '@guolao/vue-monaco-editor'
import filesApi from '@/api/files'

/** Base for editor model URIs. Kept in one place: schema `fileMatch` globs are
 *  matched against the URI's path, so the path has to carry the file path. */
const MODEL_SCHEME = 'inmemory://code-review'
const SCHEMA_URI_PREFIX = 'inmemory://v2c-schema/'

export interface SchemaMapping {
  uri: string
  /** Optional. Schemas referenced by a document's `$schema` are matched by URI. */
  fileMatch?: string[]
  schema: unknown
}

/** Model URI for a file. `scope` must be unique per editor instance so the
 *  same file open in several panes does not collide (createModel throws). */
export function modelUriFor(scope: string, filePath: string): string {
  const clean = filePath.replace(/^\/+/, '')
  return `${MODEL_SCHEME}/${scope}/${clean}`
}

/** Model URIs currently open for a workspace-relative path (one per pane). */
function modelUrisForPath(monaco: any, filePath: string): string[] {
  const suffix = '/' + filePath.replace(/^\/+/, '')
  return monaco.editor
    .getModels()
    .map((m: any) => m.uri.toString())
    .filter((u: string) => u.endsWith(suffix))
}

/**
 * Resolve a `$schema` reference against a model URI.
 *
 * Monaco resolves the document's `$schema` against the document URI, then looks
 * for a *registered* schema under that exact URI before trying to fetch it. A
 * declared `$schema` also takes precedence over any `fileMatch` schema, so this
 * is the only way to attach a schema to a document that declares one.
 */
function resolveAgainstModel(modelUri: string, reference: string): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(reference)) return reference
  const base = modelUri.split('/').slice(0, -1)
  for (const segment of reference.split('/')) {
    if (segment === '.' || segment === '') continue
    if (segment === '..') base.pop()
    else base.push(segment)
  }
  return base.join('/')
}

let configured = false

/**
 * Apply the diagnostics options once.
 *
 * Explicitly needed even though Monaco's defaults look correct: until this is
 * called the options are never pushed to the JSON worker, which leaves
 * `allowComments` unset there and makes a valid JSONC file (`.vscode/tasks.json`
 * and friends) report "Comments are not permitted in JSON." on every comment
 * line. VS Code treats all `.json` files as JSONC, so comments and trailing
 * commas are allowed.
 */
export async function ensureJsonConfigured(): Promise<any> {
  const monaco = await loader.init()
  if (configured) return monaco
  monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
    validate: true,
    allowComments: true,
    trailingCommas: 'ignore',
    comments: 'ignore',
    // Off by design: schemas are read from the worktree, not the network.
    enableSchemaRequest: false,
    schemas: []
  })
  configured = true
  return monaco
}

const mappings = new Map<string, SchemaMapping>()

function applyMappings(monaco: any) {
  const schemas = [...mappings.values()].map((entry) => ({
    uri: entry.uri,
    fileMatch: entry.fileMatch,
    schema: entry.schema
  }))
  monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
    validate: true,
    allowComments: true,
    trailingCommas: 'ignore',
    comments: 'ignore',
    enableSchemaRequest: false,
    schemas
  })
}

/**
 * Glob that matches a workspace-relative path. Model URIs carry the file path
 * at their tail, so a leading double-star wildcard is enough to match one.
 */
function matchFor(filePath: string): string {
  return `**/${filePath.replace(/^\/+/, '')}`
}

/** Read a JSON file from the worktree, or null when it is absent/invalid. */
async function readWorkspaceJson(taskId: string, path: string): Promise<unknown | null> {
  try {
    const result = await filesApi.read(taskId, path)
    return JSON.parse(result.content)
  } catch {
    return null
  }
}

/** Resolve a `$schema`/`url` value to a worktree path, or null if it is remote. */
function toWorkspacePath(reference: string, fromFile: string): string | null {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(reference)) return null // http(s), file:, …
  if (reference.startsWith('/')) return reference.slice(1)

  // Relative to the directory of the file that declared it.
  const base = fromFile.split('/').slice(0, -1)
  for (const segment of reference.split('/')) {
    if (segment === '.' || segment === '') continue
    if (segment === '..') base.pop()
    else base.push(segment)
  }
  return base.join('/')
}

/** The `$schema` a document declares, if any. */
function declaredSchema(content: string): string | null {
  try {
    const parsed = JSON.parse(content)
    const value = (parsed as Record<string, unknown>)?.['$schema']
    return typeof value === 'string' ? value : null
  } catch {
    // JSONC or a file being edited — fall back to a tolerant scan.
    const match = content.match(/"\$schema"\s*:\s*"([^"]+)"/)
    return match ? match[1] : null
  }
}

interface SettingsEntry {
  fileMatch: string[]
  url: string
}

async function settingsMappings(taskId: string): Promise<SettingsEntry[]> {
  const settings = await readWorkspaceJson(taskId, '.vscode/settings.json')
  const entries = (settings as Record<string, unknown>)?.['json.schemas']
  if (!Array.isArray(entries)) return []
  return entries
    .filter((e): e is Record<string, unknown> => !!e && typeof e === 'object')
    .map((e) => ({
      fileMatch: Array.isArray(e.fileMatch) ? (e.fileMatch as string[]) : [],
      url: typeof e.url === 'string' ? e.url : ''
    }))
    .filter((e) => e.fileMatch.length > 0 && e.url)
}

/**
 * Resolve and register every schema that applies to `filePath`.
 *
 * Cheap enough to call on each open: it reads at most a couple of small files
 * and re-applies the accumulated mapping list.
 */
export async function syncSchemasForFile(
  taskId: string,
  filePath: string,
  content: string
): Promise<void> {
  const monaco = await ensureJsonConfigured()
  const match = matchFor(filePath)

  // 1. The document's own $schema.
  const declared = declaredSchema(content)
  if (declared) {
    const schemaPath = toWorkspacePath(declared, filePath)
    if (schemaPath) {
      const schema = await readWorkspaceJson(taskId, schemaPath)
      if (schema) {
        // A declared $schema wins over fileMatch, and Monaco looks it up by the
        // URI it resolves to — register under exactly that URI for every pane
        // currently showing the file.
        for (const modelUri of modelUrisForPath(monaco, filePath)) {
          const uri = resolveAgainstModel(modelUri, declared)
          mappings.set(uri, { uri, schema })
        }
        // Also keep a fileMatch entry: it covers the window before the model
        // URI is known, and documents that lost their $schema.
        const fallbackUri = `${SCHEMA_URI_PREFIX}${encodeURIComponent(match)}`
        mappings.set(fallbackUri, { uri: fallbackUri, fileMatch: [match], schema })
      }
    }
  }

  // 2. .vscode/settings.json -> json.schemas
  for (const entry of await settingsMappings(taskId)) {
    const schemaPath = toWorkspacePath(entry.url, '.vscode/settings.json')
    if (!schemaPath) continue
    const schema = await readWorkspaceJson(taskId, schemaPath)
    if (schema) {
      const key = entry.fileMatch.join(',')
      const uri = `${SCHEMA_URI_PREFIX}${encodeURIComponent(key)}`
      mappings.set(uri, { uri, fileMatch: entry.fileMatch, schema })
    }
  }

  applyMappings(monaco)
}

/** Exposed for tests. */
export const __test = {
  declaredSchema,
  toWorkspacePath,
  matchFor,
  resolveAgainstModel,
  MODEL_SCHEME
}
