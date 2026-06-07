# Mermaid 图表测试

> 用于验证 Markdown 预览的 Mermaid.js 集成是否正常工作

## 1. 流程图 (Flowchart)

```mermaid
graph TD
    A[开始] --> B{是否有效?}
    B -->|是| C[处理请求]
    B -->|否| D[返回错误]
    C --> E[结束]
    D --> E
```

```mermaid
graph LR
    subgraph 前端
        A[Vue 组件] --> B[API 调用]
    end
    subgraph 后端
        B --> C[FastAPI 路由]
        C --> D[Service 层]
        D --> E[数据库]
    end
    B --> F[WebSocket]
    F --> G[tmux 终端]
```

## 2. 时序图 (Sequence Diagram)

```mermaid
sequenceDiagram
    participant 用户
    participant 前端
    participant 后端
    participant Git

    用户->>前端: 创建任务
    前端->>后端: POST /api/tasks
    后端->>Git: git worktree add
    后端-->>前端: 任务创建成功
    前端->>用户: 显示新任务
    用户->>前端: 编辑文件
    前端->>后端: PUT /api/files
    后端-->>前端: 保存成功
```

## 3. 类图 (Class Diagram)

```mermaid
classDiagram
    class Project {
        +int id
        +string name
        +string path
        +create_worktree()
    }
    class Task {
        +int id
        +string title
        +string status
        +start()
        +stop()
    }
    class Terminal {
        +string session_id
        +connect()
        +send_input()
        +resize()
    }
    Project "1" --> "*" Task
    Task "1" --> "1" Terminal
```

## 4. 状态图 (State Diagram)

```mermaid
stateDiagram-v2
    [*] --> 待处理
    待处理 --> 进行中: 开始任务
    进行中 --> 待审查: 提交代码
    待审查 --> 进行中: 需要修改
    待审查 --> 已完成: 审查通过
    已完成 --> [*]
```

## 5. 饼图 (Pie Chart)

```mermaid
pie title 项目语言分布
    "Python" : 40
    "TypeScript" : 30
    "Vue" : 15
    "Shell" : 10
    "其他" : 5
```

## 6. 甘特图 (Gantt Diagram)

```mermaid
gantt
    title 项目计划
    dateFormat  YYYY-MM-DD
    section 前端
    UI 设计           :a1, 2024-01-01, 7d
    组件开发          :a2, after a1, 14d
    集成测试          :a3, after a2, 7d
    section 后端
    API 开发          :b1, 2024-01-05, 14d
    数据库设计        :b2, 2024-01-01, 5d
    部署上线          :b3, after a3 b1, 5d
```

## 7. Git 分支图 (Gitgraph)

```mermaid
gitGraph
    commit
    branch feature
    checkout feature
    commit
    commit
    checkout main
    commit
    merge feature
    commit
```

## 8. 实体关系图 (Entity Relationship)
## 8.1 子标题

```mermaid
erDiagram
    PROJECT ||--o{ TASK : contains
    PROJECT {
        int id PK
        string name
        string path
    }
    TASK ||--o{ SESSION : has
    TASK {
        int id PK
        string title
        string status
    }
    SESSION {
        int id PK
        string tmux_id
        datetime created_at
    }
```

## 9. 用户旅程图 (User Journey)

```mermaid
journey
    title 用户创建任务流程
    section 创建任务
        填写信息: 5: 用户
        选择项目: 4: 用户
        提交创建: 3: 系统
    section 开发
        编辑代码: 5: 开发者
        运行命令: 4: 开发者
        查看结果: 5: 开发者
```

## 10. 思维导图 (Mindmap)

```mermaid
mindmap
  root((vibe2crazy))
    前端
      Vue 3
      Monaco Editor
      Tailwind CSS
      WebSocket 终端
    后端
      FastAPI
      SQLAlchemy
      tmux 管理
      Git 操作
    功能
      代码审查
      终端访问
      Git 集成
      文件浏览
```

## 11. 复杂流程图 - 请求处理

```mermaid
flowchart TB
    Client([客户端请求]) --> LB{负载均衡器}
    LB -->|路由规则| API1[API 服务器 1]
    LB -->|路由规则| API2[API 服务器 2]
    API1 --> Cache{缓存}
    Cache -->|命中| Return[直接返回]
    Cache -->|未命中| DB[(数据库)]
    DB --> Worker[后台Worker]
    Worker --> Queue[消息队列]
    Queue --> Processor[处理器]
    Processor -->|成功| Done[完成]
    Processor -->|失败| Retry[重试队列]
    Retry -->|最多3次| Processor
    Retry -->|超过次数| Dead[死信队列]
```

## 12. 象限图 (Quadrant Chart)

```mermaid
quadrantChart
    title 技术栈评估
    x-axis 低复杂度 --> 高复杂度
    y-axis 低价值 --> 高价值
    quadrant-1 重点投入
    quadrant-2 保持
    quadrant-3 考虑淘汰
    quadrant-4 按需使用
    Vue: [0.3, 0.8]
    React: [0.6, 0.7]
    Python: [0.4, 0.9]
    Rust: [0.9, 0.6]
    jQuery: [0.2, 0.3]
    C: [0.8, 0.2]
```

## 13. 时间线图 (Timeline)

```mermaid
timeline
    title 项目里程碑
    2024 Q1 : 需求分析
            : 技术选型
    2024 Q2 : 原型开发
            : 核心功能
    2024 Q3 : 测试优化
            : 文档编写
    2024 Q4 : 发布上线
            : 迭代维护
```

## 14. 架构图中的区块图 (Block Diagram)

```mermaid
block-beta
    columns 3
    Browser["浏览器"]:1
    Internet["互联网"]:1
    Server["服务器"]:1
    space:1
    Database[("数据库")]:2
    space:1
    Cache[("缓存")]:2

    Browser --> Internet --> Server
    Server --> Database
    Server --> Cache
```

## 15. 普通代码块（应该不受影响）

```python
def hello():
    print("Hello, World!")
```

```javascript
const greet = (name) => {
    console.log(`Hello, ${name}!`);
};
```

---

> 以上包含了 Mermaid 支持的所有主流图表类型，用于验证 `MarkdownPreviewModal.vue` 中的 Mermaid.js 集成是否正确。
