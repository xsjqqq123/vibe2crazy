/**
 * Parser for VS Code task definitions (`.vscode/tasks.json`).
 *
 * Produces, for each task, two commands:
 *   - `vtrCommand`  — `vtr <label>`, for the vscode-task-runner CLI
 *     (https://github.com/NathanVaughn/vscode-task-runner). It resolves
 *     `${...}` variables and `dependsOn` itself, so this is the command that
 *     behaves the way VS Code does.
 *   - `rawCommand`  — the underlying shell command with args spliced in, for
 *     people who do not have vtr installed. Variables are left untouched, so
 *     the caller should warn when `hasVariables` is set.
 */

export interface VscodeTask {
  label: string
  type: string | null
  detail: string | null
  /** `build` | `test` | `none` when the group is given as a plain string. */
  group: string | null
  isDefaultBuild: boolean
  dependsOn: string[]
  cwd: string | null
  isBackground: boolean
  /** `vtr <label>` */
  vtrCommand: string
  /** The task's own command, or null when it cannot be resolved (e.g. only dependsOn). */
  rawCommand: string | null
  /** The raw command contains `${...}`; a bare shell will not expand those. */
  hasVariables: boolean
  /** The raw command needs `${input:id}`; vtr reads those from `VTR_INPUT_<id>`. */
  inputIds: string[]
}

export interface ParsedTasks {
  tasks: VscodeTask[]
  /** Set when the file could not be parsed; `tasks` is then empty. */
  error: string | null
}

/** True for `.vscode/tasks.json` at any depth — the location vtr looks in. */
export function isTasksJsonPath(path: string | null | undefined): boolean {
  if (!path) return false
  return /(^|\/)\.vscode\/tasks\.json$/i.test(path.replace(/\\/g, '/'))
}

// Characters that are safe to leave unquoted in a POSIX shell word.
const SAFE_ARG = /^[A-Za-z0-9_@%+=:,./-]+$/

/** Quote a word for a POSIX shell, using single quotes when needed. */
function quoteArg(value: string): string {
  if (value === '') return "''"
  if (SAFE_ARG.test(value)) return value
  return `'${value.replace(/'/g, `'\\''`)}'`
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((v): v is string => typeof v === 'string')
}

/** `"build"` or `{ kind: "build", isDefault: true }` -> `"build"` + default flag. */
function readGroup(value: unknown): { group: string | null; isDefaultBuild: boolean } {
  if (typeof value === 'string') return { group: value, isDefaultBuild: false }
  if (value && typeof value === 'object') {
    const raw = value as Record<string, unknown>
    return {
      group: asString(raw.kind),
      isDefaultBuild: raw.isDefault === true
    }
  }
  return { group: null, isDefaultBuild: false }
}

/**
 * Build the command a plain shell would run.
 *
 * Handles the two shapes VS Code supports: a shell/process task with
 * `command` + `args`, and the npm task type, which carries `script` instead.
 */
function buildRawCommand(task: Record<string, unknown>): string | null {
  const type = asString(task.type)
  const args = asStringArray(task.args).map(quoteArg)
  const command = asString(task.command)

  if (type === 'npm' || (!command && asString(task.script))) {
    const script = asString(task.script)
    if (!script) return null
    return ['npm', 'run', quoteArg(script), ...args].join(' ')
  }

  if (!command) return null
  return [command, ...args].join(' ')
}

function toTask(raw: unknown): VscodeTask | null {
  if (!raw || typeof raw !== 'object') return null
  const task = raw as Record<string, unknown>

  const label = asString(task.label)
  if (!label) return null // Without a label there is no vtr invocation.

  const rawCommand = buildRawCommand(task)
  const { group, isDefaultBuild } = readGroup(task.group)
  const options = (task.options ?? {}) as Record<string, unknown>
  const dependsOn = asStringArray(task.dependsOn)
  const inputIds = rawCommand
    ? [...rawCommand.matchAll(/\$\{input:([^}]+)\}/g)].map((m) => m[1])
    : []

  return {
    label,
    type: asString(task.type),
    detail: asString(task.detail),
    group,
    isDefaultBuild,
    dependsOn,
    cwd: asString(options.cwd),
    isBackground: task.isBackground === true,
    vtrCommand: `vtr ${quoteArg(label)}`,
    rawCommand,
    hasVariables: rawCommand !== null && /\$\{/.test(rawCommand),
    inputIds
  }
}

/**
 * Strip `//` and block comments. A scanner rather than a regex, so comment
 * markers inside string values (a command containing "http://…" or "a//b")
 * survive.
 */
function stripJsonComments(input: string): string {
  let out = ''
  let inString = false
  let inLineComment = false
  let inBlockComment = false

  for (let i = 0; i < input.length; i++) {
    const ch = input[i]
    const next = input[i + 1]

    if (inLineComment) {
      if (ch === '\n') {
        inLineComment = false
        out += ch
      }
      continue
    }

    if (inBlockComment) {
      if (ch === '*' && next === '/') {
        inBlockComment = false
        i++
      }
      continue
    }

    if (inString) {
      out += ch
      if (ch === '\\') {
        out += next ?? ''
        i++
      } else if (ch === '"') {
        inString = false
      }
      continue
    }

    if (ch === '"') {
      inString = true
      out += ch
      continue
    }

    if (ch === '/' && next === '/') {
      inLineComment = true
      i++
      continue
    }

    if (ch === '/' && next === '*') {
      inBlockComment = true
      i++
      continue
    }

    out += ch
  }

  return out
}

/**
 * Drop commas that sit directly before a closing brace or bracket, but only
 * when they are outside a string — a command argument of "a,}" must survive.
 *
 * Runs after comment removal, since a comment can sit between the comma and
 * the brace.
 */
function stripTrailingCommas(input: string): string {
  let out = ''
  let inString = false

  for (let i = 0; i < input.length; i++) {
    const ch = input[i]

    if (inString) {
      out += ch
      if (ch === '\\') {
        out += input[i + 1] ?? ''
        i++
      } else if (ch === '"') {
        inString = false
      }
      continue
    }

    if (ch === '"') {
      inString = true
      out += ch
      continue
    }

    if (ch === ',') {
      let lookahead = i + 1
      while (lookahead < input.length && /\s/.test(input[lookahead])) lookahead++
      if (input[lookahead] === '}' || input[lookahead] === ']') continue // drop it
    }

    out += ch
  }

  return out
}

/** tasks.json is JSONC: VS Code itself writes comments into it. */
function stripJsonc(input: string): string {
  return stripTrailingCommas(stripJsonComments(input))
}

export function parseTasksJson(content: string): ParsedTasks {
  if (!content.trim()) {
    return { tasks: [], error: 'The file is empty.' }
  }

  let parsed: unknown
  try {
    // tasks.json is JSONC: VS Code itself writes comments into it.
    parsed = JSON.parse(stripJsonc(content))
  } catch (e: any) {
    return { tasks: [], error: e?.message ? `Invalid JSON: ${e.message}` : 'Invalid JSON.' }
  }

  // Both `{ version, tasks: [...] }` and a bare array are seen in the wild.
  const rawTasks = Array.isArray(parsed)
    ? parsed
    : (parsed as Record<string, unknown>)?.tasks

  if (!Array.isArray(rawTasks)) {
    return { tasks: [], error: 'No "tasks" array found in this file.' }
  }

  const tasks = rawTasks.map(toTask).filter((t): t is VscodeTask => t !== null)
  if (tasks.length === 0 && rawTasks.length > 0) {
    return { tasks: [], error: 'None of the entries have a "label", so there is nothing to run.' }
  }
  return { tasks, error: null }
}
