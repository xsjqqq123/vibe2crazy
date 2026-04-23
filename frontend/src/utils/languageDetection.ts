// frontend/src/utils/languageDetection.ts

/**
 * Detect programming language from file extension
 * Used by MonacoEditor for syntax highlighting and SymbolOutline for symbol extraction
 * Monaco Editor has built-in syntax highlighting for all these languages
 */

export type SupportedLanguage =
  // Web technologies
  | 'typescript'
  | 'javascript'
  | 'html'
  | 'css'
  | 'scss'
  | 'sass'
  | 'less'
  | 'vue'
  // Programming languages
  | 'python'
  | 'java'
  | 'c'
  | 'cpp'
  | 'csharp'
  | 'go'
  | 'rust'
  | 'ruby'
  | 'php'
  | 'swift'
  | 'kotlin'
  | 'scala'
  | 'objective-c'
  | 'perl'
  | 'lua'
  | 'r'
  | 'clojure'
  | 'fsharp'
  | 'dart'
  | 'elixir'
  | 'haskell'
  | 'pascal'
  | 'scheme'
  // Shell/Scripting
  | 'shell'
  | 'powershell'
  | 'bat'
  | 'dockerfile'
  | 'makefile'
  // Data/Config formats
  | 'json'
  | 'xml'
  | 'yaml'
  | 'toml'
  | 'ini'
  | 'properties'
  // Markup/Documentation
  | 'markdown'
  | 'html'
  | 'xml'
  // Database
  | 'sql'
  | 'mysql'
  | 'pgsql'
  | 'plsql'
  // Other
  | 'protobuf'
  | 'graphql'
  | 'vb'
  | 'coffeescript'
  | 'handlebars'
  | 'razor'
  | 'twig'
  | 'plaintext'

export function detectLanguage(path: string): SupportedLanguage {
  const ext = path.split('.').pop()?.toLowerCase() || ''
  const filename = path.split('/').pop()?.toLowerCase() || ''

  // Language map: file extension -> Monaco language identifier
  const languageMap: Record<string, SupportedLanguage> = {
    // JavaScript/TypeScript
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'mts': 'typescript',
    'cts': 'typescript',
    'es6': 'javascript',

    // Python
    'py': 'python',
    'pyw': 'python',
    'pyi': 'python',
    'pyx': 'python',

    // Java
    'java': 'java',

    // C/C++
    'c': 'c',
    'cpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'h': 'cpp',
    'hpp': 'cpp',
    'hxx': 'cpp',
    'hh': 'cpp',
    'ino': 'cpp',

    // C#
    'cs': 'csharp',
    'csx': 'csharp',

    // Go
    'go': 'go',

    // Rust
    'rs': 'rust',

    // Ruby
    'rb': 'ruby',
    'rake': 'ruby',
    'gemspec': 'ruby',
    'podspec': 'ruby',

    // PHP
    'php': 'php',
    'phtml': 'php',
    'php3': 'php',
    'php4': 'php',
    'php5': 'php',
    'php7': 'php',

    // Swift
    'swift': 'swift',

    // Kotlin
    'kt': 'kotlin',
    'kts': 'kotlin',

    // Scala
    'scala': 'scala',
    'sc': 'scala',
    'sbt': 'scala',

    // Objective-C
    'm': 'objective-c',
    'mm': 'objective-c',

    // Perl
    'pl': 'perl',
    'pm': 'perl',
    't': 'perl',

    // Lua
    'lua': 'lua',

    // R
    'r': 'r',
    'rmd': 'r',

    // Clojure
    'clj': 'clojure',
    'cljs': 'clojure',
    'cljc': 'clojure',
    'edn': 'clojure',

    // F#
    'fs': 'fsharp',
    'fsi': 'fsharp',
    'fsx': 'fsharp',

    // Dart
    'dart': 'dart',

    // Elixir
    'ex': 'elixir',
    'exs': 'elixir',

    // Haskell
    'hs': 'haskell',
    'lhs': 'haskell',

    // Pascal
    'pas': 'pascal',
    'pp': 'pascal',

    // Scheme
    'scm': 'scheme',
    'ss': 'scheme',

    // Shell/Scripting
    'sh': 'shell',
    'bash': 'shell',
    'zsh': 'shell',
    'ksh': 'shell',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'bat': 'bat',
    'cmd': 'bat',

    // Web
    'vue': 'vue',
    'html': 'html',
    'htm': 'html',
    'xhtml': 'html',
    'shtml': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'sass',
    'less': 'less',

    // Data/Config
    'json': 'json',
    'jsonc': 'json',
    'json5': 'json',
    'xml': 'xml',
    'xsl': 'xml',
    'xslt': 'xml',
    'svg': 'xml',
    'xsd': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'toml': 'toml',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    'properties': 'properties',

    // Markup/Docs
    'md': 'markdown',
    'markdown': 'markdown',
    'mdown': 'markdown',
    'mkd': 'markdown',
    'rst': 'markdown',

    // Database
    'sql': 'sql',
    'ddl': 'sql',
    'dml': 'sql',
    'mysql': 'mysql',
    'pgsql': 'pgsql',
    'plsql': 'plsql',

    // Other
    'proto': 'protobuf',
    'graphql': 'graphql',
    'gql': 'graphql',
    'vb': 'vb',
    'coffee': 'coffeescript',
    'litcoffee': 'coffeescript',
    'hbs': 'handlebars',
    'handlebars': 'handlebars',
    'cshtml': 'razor',
    'vbhtml': 'razor',
    'twig': 'twig',
  }

  // Special files by name
  const specialFiles: Record<string, SupportedLanguage> = {
    'dockerfile': 'dockerfile',
    'dockerfile.dockerignore': 'dockerfile',
    'makefile': 'makefile',
    'gnumakefile': 'makefile',
    'cmakelists.txt': 'makefile',
    'gemfile': 'ruby',
    'rakefile': 'ruby',
    'podfile': 'ruby',
    'vagrantfile': 'ruby',
    'procfile': 'ruby',
    '.env': 'properties',
    '.gitignore': 'properties',
    '.dockerignore': 'properties',
    '.editorconfig': 'ini',
    '.prettierrc': 'json',
    '.eslintrc': 'json',
    '.babelrc': 'json',
    'tsconfig.json': 'json',
    'package.json': 'json',
    'composer.json': 'json',
    'cargo.toml': 'toml',
    'pyproject.toml': 'toml',
  }

  // Check special files first
  if (specialFiles[filename]) {
    return specialFiles[filename]
  }

  return languageMap[ext] || 'plaintext'
}

/**
 * Languages supported by symbol extraction regex patterns
 */
export const SYMBOL_EXTRACTION_LANGUAGES: Set<string> = new Set([
  'typescript',
  'javascript',
  'python',
  'vue',
  'go',
  'rust',
  'c',
  'cpp',
])

/**
 * Check if a language supports symbol extraction
 */
export function supportsSymbolExtraction(language: string): boolean {
  return SYMBOL_EXTRACTION_LANGUAGES.has(language)
}