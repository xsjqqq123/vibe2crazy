# Referer 快速搜索导航功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 CodeReviewView 的 Files 区域添加 Referer tab，实现基于 ripgrep 的快速代码搜索导航功能。

**Architecture:** 前端搜索组件通过后端 API 调用 ripgrep，结果缓存到 /tmp 分页返回，前端管理分页状态。

**Tech Stack:** Vue 3, FastAPI, ripgrep, TypeScript

---

## 文件结构

```
新增文件:
- backend/app/routers/search.py          # 搜索 API 路由
- backend/app/services/grep_service.py   # ripgrep 服务
- frontend/src/api/search.ts             # 前端 API 客户端
- frontend/src/components/RefererSearch.vue  # 搜索组件

修改文件:
- backend/app/main.py                    # 注册 search 路由
- frontend/src/views/CodeReviewView.vue # 添加 Referer tab
```

---

## Task 1: 创建后端 grep_service.py

**Files:**
- Create: `backend/app/services/grep_service.py`

- [ ] **Step 1: 创建服务文件**

```python
import logging
import subprocess
import hashlib
import json
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = Path("/tmp")
CACHE_TTL = 3600  # 1小时

class GrepService:
    """Service for ripgrep-based code search"""

    @staticmethod
    def _get_cache_path(task_id: str, query: str, page: int) -> Path:
        """生成缓存文件路径"""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        return CACHE_DIR / f"referer_cache_{task_id}_{query_hash}_{page}.json"

    @staticmethod
    def _read_cache(cache_path: Path) -> Optional[dict]:
        """读取缓存"""
        if not cache_path.exists():
            return None
        # 检查过期
        age = cache_path.stat().st_mtime
        import time
        if time.time() - age > CACHE_TTL:
            cache_path.unlink()
            return None
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def _write_cache(cache_path: Path, data: dict):
        """写入缓存"""
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to write cache: {e}")

    @staticmethod
    def search(worktree_path: str, query: str, page: int = 1, per_page: int = 20) -> dict:
        """
        执行 ripgrep 搜索
        Returns: {
            "results": [{"file": str, "line": int, "content": str}],
            "groups": [{"file": str, "matches": [{"line": int, "content": str}]}],
            "total": int,
            "cached": bool
        }
        """
        cache_path = GrepService._get_cache_path(
            worktree_path.split('/')[-1], query, page
        )

        # 尝试读取缓存
        cached = GrepService._read_cache(cache_path)
        if cached:
            cached["cached"] = True
            return cached

        # 执行 ripgrep
        try:
            cmd = [
                "rg", "--json", "-n",
                "-g", "!node_modules",
                "-g", "!node_modules/**",
                "-g", "!.git",
                "-g", "!.git/**",
                query, worktree_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode not in (0, 1):  # 0=找到, 1=未找到
                logger.error(f"ripgrep failed: {result.stderr}")
                return {"results": [], "groups": [], "total": 0, "cached": False}

            # 解析 JSON 输出
            matches: List[dict] = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "match":
                        data = obj["data"]
                        matches.append({
                            "file": data["path"]["text"],
                            "line": data["line_number"],
                            "content": data["lines"]["text"].rstrip('\n')
                        })
                except Exception:
                    continue

            total = len(matches)

            # 按文件分组
            groups: List[dict] = []
            file_matches: dict = {}
            for m in matches:
                f = m["file"]
                if f not in file_matches:
                    file_matches[f] = {"file": f, "matches": []}
                file_matches[f]["matches"].append({"line": m["line"], "content": m["content"]})
            groups = list(file_matches.values())

            # 分页：按文件分页，每页per_page个文件
            start = (page - 1) * per_page
            end = start + per_page
            page_groups = groups[start:end]

            # 收集该页文件的所有匹配
            page_files = {g["file"] for g in page_groups}
            page_results = [m for m in matches if m["file"] in page_files]
            # 限制每文件只显示前3条
            limited_results = []
            file_count = {}
            for m in page_results:
                f = m["file"]
                file_count[f] = file_count.get(f, 0) + 1
                if file_count[f] <= 3:
                    limited_results.append(m)

            data = {
                "results": limited_results,
                "groups": page_groups,
                "total": total,
                "cached": False
            }

            # 写入缓存（使用page=0存储完整结果供后续分页使用）
            full_cache_path = GrepService._get_cache_path(
                worktree_path.split('/')[-1], query, 0
            )
            full_data = {
                "results": matches,
                "groups": groups,
                "total": total,
                "cached": False
            }
            GrepService._write_cache(full_cache_path, full_data)

            return data

        except subprocess.TimeoutExpired:
            logger.error("ripgrep timed out")
            return {"results": [], "groups": [], "total": 0, "cached": False, "error": "Search timed out"}
        except Exception as e:
            logger.error(f"ripgrep error: {e}")
            return {"results": [], "groups": [], "total": 0, "cached": False, "error": str(e)}

    @staticmethod
    def clear_cache(task_id: str):
        """清除指定任务的缓存"""
        import glob
        pattern = CACHE_DIR / f"referer_cache_{task_id}_*"
        for f in CACHE_DIR.glob(f"referer_cache_{task_id}_*"):
            try:
                f.unlink()
            except Exception:
                pass
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/grep_service.py
git commit -m "feat(search): add GrepService for ripgrep-based code search"
```

---

## Task 2: 创建后端 search.py 路由

**Files:**
- Create: `backend/app/routers/search.py`

- [ ] **Step 1: 创建路由文件**

```python
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.services.grep_service import GrepService

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    task_id: str
    query: str
    page: int = 1
    per_page: int = 20


class SearchMatch(BaseModel):
    file: str
    line: int
    content: str


class SearchResult(BaseModel):
    results: list[SearchMatch]
    total: int
    cached: bool


@router.post("/grep", response_model=SearchResult)
def grep_search(request: SearchRequest, db: Session = Depends(get_db)):
    """执行 ripgrep 搜索"""
    # 获取 task
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 执行搜索
    data = GrepService.search(
        worktree_path=task.worktree_path,
        query=request.query,
        page=request.page,
        per_page=request.per_page
    )

    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])

    return SearchResult(
        results=[SearchMatch(**r) for r in data["results"]],
        total=data["total"],
        cached=data["cached"]
    )


@router.delete("/cache")
def clear_cache(task_id: str, db: Session = Depends(get_db)):
    """清除搜索缓存"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    GrepService.clear_cache(task_id)
    return {"success": True}
```

- [ ] **Step 2: 注册路由到 main.py**

在 `backend/app/main.py` 添加:
```python
from app.routers import search
app.include_router(search.router)
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/search.py backend/app/main.py
git commit -m "feat(search): add search API endpoints"
```

---

## Task 3: 创建前端 search.ts API 客户端

**Files:**
- Create: `frontend/src/api/search.ts`

- [ ] **Step 1: 创建 API 客户端**

```typescript
import request from './client'

export interface SearchMatch {
  file: string
  line: number
  content: string
}

export interface SearchResult {
  results: SearchMatch[]
  total: number
  cached: boolean
}

export interface SearchRequest {
  task_id: string
  query: string
  page?: number
  per_page?: number
}

const searchApi = {
  grep: (data: SearchRequest) =>
    request<SearchResult>('/search/grep', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  clearCache: (taskId: string) =>
    request<{ success: boolean }>('/search/cache', {
      method: 'DELETE'
    })
}

export default searchApi
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/search.ts
git commit -m "feat(search): add search API client"
```

---

## Task 4: 创建 RefererSearch.vue 组件

**Files:**
- Create: `frontend/src/components/RefererSearch.vue`

- [ ] **Step 1: 创建组件**

```vue
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import searchApi, { type SearchMatch } from '@/api/search'

const props = defineProps<{
  taskId: string
}>()

const emit = defineEmits<{
  selectFile: [filePath: string, lineNumber: number]
}>()

const query = ref('')
const results = ref<SearchMatch[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const loading = ref(false)
const expandedFiles = ref<Set<string>>(new Set())

const totalPages = computed(() => Math.ceil(total.value / perPage))
const startIndex = computed(() => (page.value - 1) * perPage + 1)
const endIndex = computed(() => Math.min(page.value * perPage, total.value))

// 按文件分组结果
const groupedResults = computed(() => {
  const groups: Map<string, SearchMatch[]> = new Map()
  for (const r of results.value) {
    if (!groups.has(r.file)) {
      groups.set(r.file, [])
    }
    groups.get(r.file)!.push(r)
  }
  return Array.from(groups.entries()).map(([file, matches]) => ({
    file,
    matches: matches.slice(0, 3), // 只显示前3条
    totalMatches: matches.length
  }))
})

const toggleFile = (file: string) => {
  if (expandedFiles.value.has(file)) {
    expandedFiles.value.delete(file)
  } else {
    expandedFiles.value.add(file)
  }
}

const search = async (pageNum: number = 1) => {
  if (!query.value.trim()) return
  loading.value = true
  try {
    const data = await searchApi.grep({
      task_id: props.taskId,
      query: query.value,
      page: pageNum,
      per_page: perPage
    })
    results.value = data.results
    total.value = data.total
    page.value = pageNum
    expandedFiles.value.clear()
  } catch (e) {
    console.error('Search failed:', e)
  } finally {
    loading.value = false
  }
}

const clear = async () => {
  query.value = ''
  results.value = []
  total.value = 0
  page.value = 1
  expandedFiles.value.clear()
  try {
    await searchApi.clearCache(props.taskId)
  } catch (e) {
    console.error('Clear cache failed:', e)
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    search(1)
  }
}

const handleResultClick = (match: SearchMatch) => {
  emit('selectFile', match.file, match.line)
}

const prevPage = () => {
  if (page.value > 1) search(page.value - 1)
}

const nextPage = () => {
  if (page.value < totalPages.value) search(page.value + 1)
}
</script>

<template>
  <div class="referer-search h-full flex flex-col min-h-0">
    <!-- Search Bar -->
    <div class="p-3 border-b border-main shrink-0">
      <div class="flex gap-2">
        <input
          v-model="query"
          type="text"
          placeholder="Search..."
          class="input flex-1 text-sm"
          @keydown="handleKeydown"
        />
        <button @click="search(1)" class="btn btn-primary text-sm" :disabled="loading">
          Search
        </button>
        <button @click="clear" class="btn btn-secondary text-sm">
          Clear
        </button>
      </div>
      <div v-if="total > 0" class="text-xs text-muted mt-2">
        {{ total }} matches found
      </div>
    </div>

    <!-- Results List -->
    <div class="flex-1 overflow-y-auto min-h-0">
      <div v-if="loading" class="flex items-center justify-center py-8">
        <div class="spinner"></div>
      </div>

      <div v-else-if="results.length === 0 && query" class="text-center py-8 text-sm text-muted">
        No results found
      </div>

      <div v-else-if="results.length === 0" class="text-center py-8 text-sm text-muted">
        Enter a search term
      </div>

      <div v-else class="divide-y divide-main">
        <div
          v-for="group in groupedResults"
          :key="group.file"
          class="border-b border-main"
        >
          <!-- File Header (clickable to expand/collapse) -->
          <div
            class="px-3 py-2 text-sm cursor-pointer hover:bg-sub transition-colors"
            @click="toggleFile(group.file)"
          >
            <span class="text-primary font-medium">{{ group.file }}</span>
            <span class="text-muted ml-2">({{ group.totalMatches }} matches)</span>
            <svg
              class="inline w-4 h-4 ml-1 transition-transform"
              :class="{ 'rotate-90': expandedFiles.has(group.file) }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>

          <!-- Expanded Matches -->
          <div v-if="expandedFiles.has(group.file)" class="bg-sub/50">
            <div
              v-for="match in group.matches"
              :key="`${match.file}:${match.line}`"
              class="px-4 py-1 text-xs cursor-pointer hover:bg-primary/10 transition-colors font-mono"
              @click="handleResultClick(match)"
            >
              <span class="text-muted w-8 inline-block text-right mr-3 shrink-0">{{ match.line }}</span>
              <span class="text-main">{{ match.content }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > 0" class="p-3 border-t border-main shrink-0">
      <div class="flex items-center justify-between text-sm">
        <span class="text-muted">
          Showing {{ startIndex }}-{{ endIndex }} of {{ total }}
        </span>
        <div class="flex gap-2">
          <button
            @click="prevPage"
            :disabled="page <= 1"
            class="btn btn-secondary text-xs px-2 py-1"
          >
            Prev
          </button>
          <span class="text-muted self-center px-2">
            Page {{ page }}
          </span>
          <button
            @click="nextPage"
            :disabled="page >= totalPages"
            class="btn btn-secondary text-xs px-2 py-1"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.referer-search {
  background-color: var(--bg-secondary);
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/RefererSearch.vue
git commit -m "feat(search): add RefererSearch component"
```

---

## Task 5: 集成到 CodeReviewView

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue:56-70` (添加状态变量)
- Modify: `frontend/src/views/CodeReviewView.vue:1922-1960` (Tab 区域)
- Modify: `frontend/src/views/CodeReviewView.vue:1910-1925` (FileTree 部分)

- [ ] **Step 1: 添加状态变量**

在 `const activeTab = ref<'changes' | 'commits'>('changes')` 附近添加:
```typescript
const activeFilesTab = ref<'files' | 'referer'>('files')
```

- [ ] **Step 2: 添加 RefererSearch emit 处理**

在 methods 区域添加:
```typescript
const handleSearchSelect = (filePath: string, lineNumber: number) => {
  loadFile(filePath)
  // 等待编辑器加载后跳转到行
  nextTick(() => {
    const editor = monacoEditorRef.value
    if (editor) {
      editor.revealLineInCenter(lineNumber)
    }
  })
}
```

- [ ] **Step 3: 修改 Tab 区域**

将 `Files` 标题部分改为:
```html
<div class="flex items-center justify-between mb-2">
  <div class="flex gap-2">
    <button
      @click="activeFilesTab = 'files'"
      :class="activeFilesTab === 'files' ? 'tab-active' : 'text-sub hover:text-main'"
      class="text-sm font-medium px-2 py-1"
    >
      Files
    </button>
    <button
      @click="activeFilesTab = 'referer'"
      :class="activeFilesTab === 'referer' ? 'tab-active' : 'text-sub hover:text-main'"
      class="text-sm font-medium px-2 py-1"
    >
      Referer
    </button>
  </div>
  <button v-if="activeFilesTab === 'files'" @click="loadFileTree()" class="...">...</button>
</div>
```

- [ ] **Step 4: 条件渲染 FileTree 和 RefererSearch**

在文件树渲染部分添加:
```html
<!-- File Tree -->
<div v-if="activeFilesTab === 'files'" class="...">
  <FileTreeItem ... />
</div>

<!-- Referer Search -->
<RefererSearch
  v-else
  :task-id="taskId"
  @select-file="handleSearchSelect"
/>
```

- [ ] **Step 5: 导入 RefererSearch**

在文件顶部添加:
```typescript
import RefererSearch from '@/components/RefererSearch.vue'
```

- [ ] **Step 6: 注册组件**

```typescript
components: {
  ...
  RefererSearch
}
```

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(search): integrate RefererSearch into CodeReviewView"
```

---

## Task 6: 测试验证

- [ ] **Step 1: 启动服务**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
./deploy.sh start
```

- [ ] **Step 2: 测试搜索功能**

1. 打开浏览器访问 CodeReviewView
2. 切换到 Referer tab
3. 输入搜索关键字（如 "const"）
4. 验证结果正确显示
5. 测试翻页
6. 测试清除按钮
7. 测试点击结果跳转到文件

---

## 自检清单

- [ ] Spec 覆盖：所有设计规格都有对应实现
- [ ] 无占位符：没有 TBD、TODO、未完成的代码
- [ ] 类型一致性：前端 API 类型与后端响应一致
- [ ] 提交记录：每个 Task 有对应提交