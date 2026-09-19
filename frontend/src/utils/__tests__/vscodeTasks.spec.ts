import { describe, it, expect } from 'vitest'
import { isTasksJsonPath, parseTasksJson } from '../vscodeTasks'

const wrap = (tasks: unknown[]) => JSON.stringify({ version: '2.0.0', tasks })

describe('isTasksJsonPath', () => {
  it('matches .vscode/tasks.json', () => {
    expect(isTasksJsonPath('.vscode/tasks.json')).toBe(true)
    expect(isTasksJsonPath('packages/app/.vscode/tasks.json')).toBe(true)
    expect(isTasksJsonPath('C:\\repo\\.vscode\\tasks.json')).toBe(true)
  })

  it('rejects a tasks.json outside .vscode', () => {
    expect(isTasksJsonPath('tasks.json')).toBe(false)
    expect(isTasksJsonPath('config/tasks.json')).toBe(false)
  })

  it('rejects similar names', () => {
    expect(isTasksJsonPath('.vscode/tasks.json.bak')).toBe(false)
    expect(isTasksJsonPath('.vscodetasks/tasks.json')).toBe(false)
  })

  it('handles empty input', () => {
    expect(isTasksJsonPath(null)).toBe(false)
    expect(isTasksJsonPath(undefined)).toBe(false)
    expect(isTasksJsonPath('')).toBe(false)
  })
})

describe('parseTasksJson', () => {
  it('reads label, command and args', () => {
    const { tasks, error } = parseTasksJson(
      wrap([{ label: 'build', type: 'shell', command: 'npm', args: ['run', 'build'] }])
    )
    expect(error).toBeNull()
    expect(tasks).toHaveLength(1)
    expect(tasks[0].label).toBe('build')
    expect(tasks[0].vtrCommand).toBe('vtr build')
    expect(tasks[0].rawCommand).toBe('npm run build')
  })

  it('accepts a bare array of tasks', () => {
    const { tasks, error } = parseTasksJson(JSON.stringify([{ label: 'lint', command: 'eslint' }]))
    expect(error).toBeNull()
    expect(tasks[0].rawCommand).toBe('eslint')
  })

  it('resolves the npm task type through `npm run <script>`', () => {
    const { tasks } = parseTasksJson(wrap([{ label: 'test', type: 'npm', script: 'test:unit' }]))
    expect(tasks[0].rawCommand).toBe('npm run test:unit')
  })

  it('quotes a label containing spaces for vtr', () => {
    const { tasks } = parseTasksJson(wrap([{ label: 'run all tests' }]))
    expect(tasks[0].vtrCommand).toBe("vtr 'run all tests'")
  })

  it('escapes a single quote inside a label', () => {
    const { tasks } = parseTasksJson(wrap([{ label: "it's here" }]))
    expect(tasks[0].vtrCommand).toBe("vtr 'it'\\''s here'")
  })

  it('quotes args containing spaces', () => {
    const { tasks } = parseTasksJson(
      wrap([{ label: 'x', command: 'echo', args: ['hello world', '--flag=1'] }])
    )
    expect(tasks[0].rawCommand).toBe("echo 'hello world' --flag=1")
  })

  it('leaves a task with only dependsOn without a raw command', () => {
    const { tasks } = parseTasksJson(wrap([{ label: 'all', dependsOn: ['build', 'test'] }]))
    expect(tasks[0].rawCommand).toBeNull()
    expect(tasks[0].vtrCommand).toBe('vtr all')
    expect(tasks[0].dependsOn).toEqual(['build', 'test'])
  })

  it('reads group as a plain string or an object', () => {
    const { tasks } = parseTasksJson(
      wrap([
        { label: 'a', command: 'x', group: 'build' },
        { label: 'b', command: 'y', group: { kind: 'test', isDefault: true } }
      ])
    )
    expect(tasks[0].group).toBe('build')
    expect(tasks[0].isDefaultBuild).toBe(false)
    expect(tasks[1].group).toBe('test')
    expect(tasks[1].isDefaultBuild).toBe(true)
  })

  it('carries detail, cwd and background flag', () => {
    const { tasks } = parseTasksJson(
      wrap([
        {
          label: 'serve',
          command: 'npm',
          detail: 'Start the dev server',
          options: { cwd: '${workspaceFolder}/web' },
          isBackground: true
        }
      ])
    )
    expect(tasks[0].detail).toBe('Start the dev server')
    expect(tasks[0].cwd).toBe('${workspaceFolder}/web')
    expect(tasks[0].isBackground).toBe(true)
  })

  it('flags unexpanded variables in the raw command', () => {
    const { tasks } = parseTasksJson(
      wrap([{ label: 'x', command: 'node', args: ['${workspaceFolder}/cli.js'] }])
    )
    expect(tasks[0].hasVariables).toBe(true)
  })

  it('does not flag a command without variables', () => {
    const { tasks } = parseTasksJson(wrap([{ label: 'x', command: 'ls', args: ['-la'] }]))
    expect(tasks[0].hasVariables).toBe(false)
  })

  it('collects input ids', () => {
    const { tasks } = parseTasksJson(
      wrap([{ label: 'report', command: 'gen', args: ['--format=${input:format}'] }])
    )
    expect(tasks[0].inputIds).toEqual(['format'])
  })

  it('skips entries without a label', () => {
    const { tasks } = parseTasksJson(
      wrap([{ command: 'no-label' }, { label: 'ok', command: 'yes' }])
    )
    expect(tasks).toHaveLength(1)
    expect(tasks[0].label).toBe('ok')
  })

  it('parses JSONC with line comments and a trailing comma', () => {
    const jsonc = `{
      // Tasks for this repo.
      "version": "2.0.0",
      "tasks": [
        {
          "label": "build",
          "command": "npm", // inline comment
          "args": ["run", "build"],
          /* block comment */
        },
      ],
    }`
    const { tasks, error } = parseTasksJson(jsonc)
    expect(error).toBeNull()
    expect(tasks).toHaveLength(1)
    expect(tasks[0].rawCommand).toBe('npm run build')
  })

  it('does not treat comment markers inside strings as comments', () => {
    const { tasks, error } = parseTasksJson(
      wrap([
        { label: 'curl', command: 'curl', args: ['http://localhost:8863/health'] },
        { label: 'slashes', command: 'echo', args: ['a//b'] }
      ])
    )
    expect(error).toBeNull()
    expect(tasks[0].rawCommand).toBe('curl http://localhost:8863/health')
    expect(tasks[1].rawCommand).toBe('echo a//b')
  })

  it('keeps a comma that is inside a string value', () => {
    const { tasks } = parseTasksJson(
      wrap([{ label: 'x', command: 'echo', args: ['a,}', 'b'] }])
    )
    expect(tasks[0].rawCommand).toBe("echo 'a,}' b")
  })

  it('reports invalid JSON', () => {
    const { tasks, error } = parseTasksJson('{ not json')
    expect(tasks).toHaveLength(0)
    expect(error).toMatch(/Invalid JSON/)
  })

  it('reports an empty file', () => {
    expect(parseTasksJson('   ').error).toMatch(/empty/i)
  })

  it('reports a missing tasks array', () => {
    const { error } = parseTasksJson(JSON.stringify({ version: '2.0.0' }))
    expect(error).toMatch(/No "tasks" array/)
  })

  it('reports when no entry has a label', () => {
    const { tasks, error } = parseTasksJson(wrap([{ command: 'a' }, { command: 'b' }]))
    expect(tasks).toHaveLength(0)
    expect(error).toMatch(/label/)
  })

  it('returns an empty list without error for an empty tasks array', () => {
    const { tasks, error } = parseTasksJson(wrap([]))
    expect(tasks).toEqual([])
    expect(error).toBeNull()
  })
})
