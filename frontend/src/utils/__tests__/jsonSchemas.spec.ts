import { describe, it, expect } from 'vitest'
import { modelUriFor, __test } from '../jsonSchemas'

const { declaredSchema, toWorkspacePath, matchFor, resolveAgainstModel } = __test

describe('modelUriFor', () => {
  it('keeps the file path at the tail so fileMatch globs can match it', () => {
    expect(modelUriFor('m1', '.vscode/tasks.json')).toBe(
      'inmemory://code-review/m1/.vscode/tasks.json'
    )
  })

  it('scopes per editor instance so the same file in two panes cannot collide', () => {
    const a = modelUriFor('m1', 'package.json')
    const b = modelUriFor('m2', 'package.json')
    expect(a).not.toBe(b)
    expect(a.endsWith('/package.json')).toBe(true)
    expect(b.endsWith('/package.json')).toBe(true)
  })

  it('normalises a leading slash', () => {
    expect(modelUriFor('m1', '/a/b.json')).toBe('inmemory://code-review/m1/a/b.json')
  })
})

describe('matchFor', () => {
  it('matches the path shape of a model URI', () => {
    expect(matchFor('.vscode/tasks.json')).toBe('**/.vscode/tasks.json')
  })
})

describe('resolveAgainstModel', () => {
  it('resolves a sibling reference', () => {
    expect(
      resolveAgainstModel('inmemory://code-review/m1/.vscode/a.json', './b.json')
    ).toBe('inmemory://code-review/m1/.vscode/b.json')
  })

  it('resolves a nested reference', () => {
    expect(
      resolveAgainstModel('inmemory://code-review/m1/.vscode/a.json', './schemas/x.json')
    ).toBe('inmemory://code-review/m1/.vscode/schemas/x.json')
  })

  it('resolves .. segments', () => {
    expect(
      resolveAgainstModel('inmemory://code-review/m1/.vscode/a.json', '../schemas/x.json')
    ).toBe('inmemory://code-review/m1/schemas/x.json')
  })

  it('leaves an absolute URI alone', () => {
    const url = 'https://json.schemastore.org/package.json'
    expect(resolveAgainstModel('inmemory://code-review/m1/a.json', url)).toBe(url)
  })
})

describe('toWorkspacePath', () => {
  it('resolves a relative reference against the declaring file', () => {
    expect(toWorkspacePath('./schemas/x.json', '.vscode/a.json')).toBe('.vscode/schemas/x.json')
  })

  it('handles ..', () => {
    expect(toWorkspacePath('../schemas/x.json', '.vscode/a.json')).toBe('schemas/x.json')
  })

  it('strips a leading slash for a root-relative path', () => {
    expect(toWorkspacePath('/schemas/x.json', 'a/b.json')).toBe('schemas/x.json')
  })

  it('returns null for remote references so we never fetch them', () => {
    expect(toWorkspacePath('https://example.com/x.json', 'a.json')).toBeNull()
    expect(toWorkspacePath('http://example.com/x.json', 'a.json')).toBeNull()
    expect(toWorkspacePath('file:///tmp/x.json', 'a.json')).toBeNull()
  })
})

describe('declaredSchema', () => {
  it('reads $schema from valid JSON', () => {
    expect(declaredSchema('{"$schema": "./s.json"}')).toBe('./s.json')
  })

  it('reads it from JSONC that JSON.parse would reject', () => {
    expect(declaredSchema('{\n  // comment\n  "$schema": "./s.json"\n}')).toBe('./s.json')
  })

  it('returns null when there is none', () => {
    expect(declaredSchema('{"a": 1}')).toBeNull()
  })
})
