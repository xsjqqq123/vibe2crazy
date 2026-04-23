# 局域网自动检测与切换设计

日期: 2026-04-08

## 概述

用户通过 FRP/ngrok 隧道从公网访问本地后端服务。当用户在局域网内时，应自动检测并切换到局域网直连，减轻公网服务器压力，提升响应速度。

## 目标

- **自动检测**：页面加载时检测局域网后端是否可达
- **自动切换**：发现可用局域网地址时自动切换
- **自动回退**：局域网不可达时自动回退到公网地址
- **持续优化**：定时检测，网络环境变化时自动适应

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ networkDetector │    │   API Client    │                    │
│  │                 │    │                 │                    │
│  │ - 获取局域网IP  │    │ - wrapRequest() │                    │
│  │ - 并行探测     │    │ - 自动回退      │                    │
│  │ - 管理切换     │    │ - 状态同步      │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
│           │                      │                              │
│           └──────────┬───────────┘                              │
│                      ↓                                          │
│              ┌───────────────┐                                  │
│              │   API_BASE    │                                  │
│              │ (动态切换)     │                                  │
│              └───────┬───────┘                                  │
│                      │                                          │
└──────────────────────┼──────────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ↓                           ↓
┌─────────────────┐        ┌─────────────────┐
│   局域网后端     │        │   公网代理       │
│ 192.168.x.x:8863│        │ (FRP/ngrok)     │
└─────────────────┘        └─────────────────┘
```

## 后端 API 扩展

### 1. 获取局域网信息

```
GET /api/tunnel/localinfo

Response:
{
  "ips": ["192.168.1.100", "192.168.1.101"],
  "port": 8863,
  "token_hash": "sha256:abc123..."
}
```

**实现要点：**
- 读取本机所有网卡 IPv4 地址
- 过滤掉 127.0.0.1 和公网 IP
- `token_hash` 用于验证前端连接的是正确的后端

### 2. Token 验证端点

```
GET /api/tunnel/token_hash

Response:
{
  "token_hash": "sha256:abc123..."
}
```

**特点：**
- 无需 Authorization 认证
- 用于前端验证连接的是同一个后端实例

### 后端实现位置

```
backend/app/routers/tunnel.py  # 新增路由
backend/app/services/network_service.py  # 网络信息获取服务
```

## 前端实现

### 1. 新增网络检测模块

**文件：** `frontend/src/utils/networkDetector.ts`

```typescript
interface NetworkDetector {
  // 初始化检测
  init(): Promise<void>

  // 启动定时检测
  startPeriodicCheck(intervalMs: number): void

  // 停止定时检测
  stopPeriodicCheck(): void

  // 手动触发检测
  detect(): Promise<string | null>

  // 获取当前 API_BASE
  getCurrentBase(): string

  // 强制使用公网地址
  forcePublic(): void
}
```

**核心方法：**

```typescript
async detect(): Promise<string | null> {
  // 1. 通过公网地址获取局域网信息
  const localInfo = await fetch(`${publicBase}/api/tunnel/localinfo`)

  // 2. 并行探测所有 IP
  const results = await Promise.all(
    localInfo.ips.map(ip => probeAddress(ip, localInfo.port, localInfo.token_hash))
  )

  // 3. 返回第一个匹配的地址
  const match = results.find(r => r.matched)
  return match ? `http://${match.ip}:${match.port}` : null
}

async probeAddress(ip: string, port: number, expectedHash: string): Promise<ProbeResult> {
  try {
    const response = await fetch(`http://${ip}:${port}/api/tunnel/token_hash`, {
      signal: AbortSignal.timeout(3000)  // 3秒超时
    })
    const data = await response.json()
    return { ip, port, matched: data.token_hash === expectedHash }
  } catch {
    return { ip, port, matched: false }
  }
}
```

### 2. 修改 API 客户端

**文件：** `frontend/src/api/client.ts`

```typescript
// 当前地址类型
type AddressType = 'lan' | 'public'

let currentBase: string
let currentType: AddressType
let publicBase: string  // 公网地址，不可变

// 包装请求，支持自动回退
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  try {
    return await doRequest<T>(currentBase, endpoint, options)
  } catch (error) {
    // 网络错误且当前是局域网，尝试回退
    if (isNetworkError(error) && currentType === 'lan') {
      console.log('[API] LAN request failed, falling back to public')
      switchToPublic()
      return await doRequest<T>(currentBase, endpoint, options)
    }
    throw error
  }
}

function switchToPublic() {
  currentBase = publicBase
  currentType = 'public'
  localStorage.setItem('lan_detector', JSON.stringify({
    preferred_base: null,
    public_base: publicBase,
    last_check: Date.now()
  }))
}

function switchToLan(base: string) {
  currentBase = base
  currentType = 'lan'
  localStorage.setItem('lan_detector', JSON.stringify({
    preferred_base: base,
    public_base: publicBase,
    last_check: Date.now()
  }))
}
```

### 3. 启动流程

**文件：** `frontend/src/main.ts`

```typescript
import { networkDetector } from './utils/networkDetector'

// 应用启动时
async function bootstrap() {
  // 1. 初始化网络检测
  await networkDetector.init()

  // 2. 启动定时检测（每 5 分钟）
  networkDetector.startPeriodicCheck(5 * 60 * 1000)

  // 3. 挂载 Vue 应用
  app.mount('#app')
}

bootstrap()
```

## 检测流程详解

### 启动时检测

```
页面加载
    │
    ├─→ localStorage 有 preferred_base?
    │       │
    │       ├─ 是 → 快速验证 (HEAD /api/tunnel/token_hash)
    │       │       │
    │       │       ├─ 成功 → 使用局域网地址
    │       │       │
    │       │       └─ 失败 → 使用公网地址
    │       │
    │       └─ 否 → 使用公网地址
    │
    └─→ 后台启动局域网探测（不阻塞页面渲染）
            │
            └─→ 发现可用局域网 → 切换并保存
```

### 定时检测

```
每 5 分钟触发
    │
    ├─→ 当前是局域网?
    │       │
    │       ├─ 是 → 跳过（已在最优状态）
    │       │
    │       └─ 否 → 执行局域网探测
    │               │
    │               └─→ 发现可用 → 切换
```

### 请求级回退

```
API 请求
    │
    ├─→ 成功 → 返回结果
    │
    └─→ 失败 (网络错误)
            │
            ├─→ 当前是局域网?
            │       │
            │       ├─ 是 → 切换公网 → 重试请求
            │       │
            │       └─ 否 → 返回错误
```

## localStorage 数据结构

```typescript
interface LanDetectorStorage {
  preferred_base: string | null  // 首选的局域网地址
  public_base: string            // 公网地址（用于回退）
  last_check: number             // 上次检测时间戳
}
```

**示例：**
```json
{
  "preferred_base": "http://192.168.1.100:8863",
  "public_base": "https://myserver.com/api",
  "last_check": 1712553600000
}
```

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 探测超时 | 3000ms | 单个 IP 探测超时时间 |
| 检测间隔 | 5 分钟 | 定时检测频率 |
| 启用检测 | true | 是否启用自动检测 |

## 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 公网地址不可达 | 不进行局域网检测，使用缓存或报错 |
| 所有局域网 IP 都不可达 | 保持使用公网地址 |
| 用户手动切换地址 | 清除自动检测状态，使用用户选择 |
| 多个局域网 IP 可达 | 使用第一个匹配的（按接口顺序） |
| 后端重启后 token_hash 变化 | 重新检测匹配新的 hash |

## 实现文件清单

### 后端新增/修改
```
backend/app/routers/tunnel.py      # 新增 localinfo 和 token_hash 端点
backend/app/services/network_service.py  # 新增：网络信息获取服务
backend/app/schemas/tunnel.py      # 新增响应 schema
```

### 前端新增/修改
```
frontend/src/utils/networkDetector.ts   # 新增：核心检测模块
frontend/src/api/client.ts              # 修改：增加回退逻辑
frontend/src/main.ts                    # 修改：初始化检测
frontend/src/types/network.ts           # 新增：类型定义
```

## 测试要点

1. **启动检测**：localStorage 有/无缓存时的启动行为
2. **定时检测**：验证 5 分钟间隔触发
3. **请求回退**：局域网不可达时自动切换公网
4. **并发探测**：多个 IP 并行探测，取第一个成功
5. **超时处理**：单个 IP 探测超时不影响其他
6. **token_hash 变化**：后端重启后重新匹配

## 实现顺序

```
阶段 1: 后端 API (0.5 天)
├── network_service.py 实现
├── tunnel.py 路由扩展
└── 测试端点

阶段 2: 前端检测模块 (1 天)
├── networkDetector.ts 核心逻辑
├── client.ts 回退逻辑
└── main.ts 初始化

阶段 3: 集成测试 (0.5 天)
├── 各种网络场景测试
└── 边界情况验证
```