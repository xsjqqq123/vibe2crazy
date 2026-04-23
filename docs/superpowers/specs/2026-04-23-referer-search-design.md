# Referer 快速搜索导航功能设计

## 概述

在 CodeReviewView 的 Files 区域添加 Referer tab，提供基于 ripgrep 的快速代码搜索导航功能。

## UI 布局

### Tab 位置
- Files pane 内，与 Files tab 共用区域
- Tab 切换显示 Files 或 Referer

### Referer Tab 组件结构
```
┌──────────────────────────────────────┐
│ Files          Referer               │  ← Tab Bar
├──────────────────────────────────────┤
│ [Search input] [Search] [Clear]      │  ← 搜索栏
│ Results: 45 matches                   │  ← 结果计数
├──────────────────────────────────────┤
│ ▶ src/file.ts (12 matches)           │  ← 可折叠结果项
│   15 │ const searchResults = ...     │
│   23 │ const searchResults = ...     │
│   31 │ const searchResults = ...     │
├──────────────────────────────────────┤
│ ▶ src/utils/helper.ts (3 matches)   │  ← 折叠状态
├──────────────────────────────────────┤
│ Showing 1-20 of 45    [Prev] [Next]  │  ← 翻页控制
└──────────────────────────────────────┘
```

## 功能规格

### 搜索流程
1. 用户输入关键字
2. 前端调用后端 API `/api/search/grep`
3. 后端在任务 worktree 目录执行 ripgrep
4. 结果写入 `/tmp/referer_cache_{taskId}_{queryHash}_{page}.json`
5. 前端分页展示，每页 20 条

### 缓存策略
- **缓存键**：`{taskId}_{queryHash}_{page}`
- **查询哈希**：搜索关键字的 MD5
- **命中条件**：同一 taskId + 同一关键字 + 同一页码
- **缓存文件**：`/tmp/referer_cache_{taskId}_{queryHash}_{page}.json`
- **清除**：Clear 按钮删除所有以 `referer_cache_{taskId}_` 开头的文件

### 结果格式
```typescript
interface SearchResult {
  file: string       // 相对路径
  line: number       // 行号
  content: string    // 匹配行内容
}

interface SearchResponse {
  results: SearchResult[]
  total: number      // 总匹配数
  cached: boolean    // 是否来自缓存
}
```

### 交互行为
| 操作 | 行为 |
|------|------|
| 输入关键字 + 回车/点击 Search | 执行搜索，跳转到第1页 |
| 点击结果行 | 打开文件并跳转到该行 |
| 点击文件头（折叠项） | 展开显示前3条匹配 |
| 点击文件头（展开项） | 折叠 |
| 点击 Previous/Next | 翻页（不重新搜索） |
| 点击 Clear | 清除前后端缓存，清空结果 |

### 折叠状态
- **默认**：折叠，仅显示 `文件名 (匹配数)`
- **展开**：显示前3条匹配行（行号 + 内容）
- **行号显示**：右对齐，灰色
- **匹配高亮**：当前匹配行用背景色标注

## 后端 API

### `POST /api/search/grep`
**请求体**：
```json
{
  "task_id": "string",
  "query": "string",
  "page": 1,
  "per_page": 20
}
```

**响应**：
```json
{
  "results": [
    {"file": "src/main.ts", "line": 42, "content": "const x = 1;"},
    ...
  ],
  "total": 45,
  "cached": false
}
```

**实现**：
1. 生成缓存文件名：`/tmp/referer_cache_{taskId}_{queryHash}_{page}.json`
2. 检查缓存文件是否存在
3. 如存在且未过期（1小时），直接返回
4. 否则执行 ripgrep：
   ```bash
   rg --json -n "{query}" {worktreePath}
   ```
5. 结果写入缓存文件
6. 返回分页结果

### `DELETE /api/search/cache`
**请求体**：
```json
{
  "task_id": "string"
}
```
**行为**：删除该 task 的所有 referer 缓存文件

## 组件设计

### 新增文件
- `frontend/src/views/RefererSearch.vue` - 搜索组件
- `backend/app/routers/search.py` - 搜索路由
- `backend/app/services/grep_service.py` - ripgrep 服务

### 修改文件
- `frontend/src/views/CodeReviewView.vue`：
  - 添加 `activeFilesTab: 'files' | 'referer'` 状态
  - Tab bar 增加 Files/Referer 切换
  - 条件渲染 FileTree 或 RefererSearch
- `frontend/src/api/` - 新增 search API 客户端
- `backend/app/main.py` - 注册 search 路由

## 技术细节

### ripgrep 选项
```bash
rg --json -n -g '!node_modules' -g '!.git' "{query}" {path}
```
- `--json`：结构化输出
- `-n`：显示行号
- `-g`：排除目录

### 分组逻辑
后端执行一次 ripgrep 获取所有结果，按文件分组后缓存：
```json
{
  "groups": [
    {
      "file": "src/a.ts",
      "matches": [
        {"line": 10, "content": "..."},
        {"line": 20, "content": "..."}
      ]
    }
  ],
  "total": 45
}
```

### Monaco 跳转
点击结果行时：
1. 调用 `loadFile(filePath)`
2. 跳转后执行 `editor.revealLineInCenter(lineNumber)`

## 验收标准

1. 搜索结果正确显示文件路径、行号、匹配内容
2. 翻页不重新执行搜索（使用缓存）
3. Clear 按钮同时清除前后端缓存
4. 折叠/展开功能正常
5. 点击结果行跳转到正确文件和行号
6. 主题适配（light/dark）