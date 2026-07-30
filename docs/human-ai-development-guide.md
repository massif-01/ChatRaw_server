# ChatRaw Human + AI Development Guide

本指南把模块、配套插件与 Resident Integration 的开发约束写成同时适合人和 AI 执行的工作协议。它不替代机器可读契约。

## 1. 开始前必须回答

先用一句话回答以下问题：

1. 这个功能为什么不能只做成普通插件？
2. 独立模块真正需要的后端能力是什么？
3. 哪些数据属于 ChatRaw，哪些数据属于模块？
4. 普通用户能做什么，管理员能做什么？
5. 模块需要哪些 Host Capability？为什么每一项都不可再减少？
6. 哪一部分是公开 Module Protocol，哪一部分必须保持模块私有？
7. Source 和 Compose 分别如何持久化和恢复？

如果这些边界无法明确，不要开始写代码。

## 2. 选择插件还是模块

```text
只增加前端交互或轻量转换？
  ├─ 是 → 插件
  └─ 否
      需要独立后端、数据库、长任务、原生依赖或高权限？
        ├─ 是 → 模块
        └─ 否 → 先证明为什么现有插件能力不够
```

确定需要模块后，再选择前端交付：

```text
管理员需要在 WebUI 动态安装、启停或升级入口？
  ├─ 是 → 配套插件（工具栏或侧栏入口）
  └─ 否
      入口必须随 Server 源码审查、构建和发布？
        ├─ 是 → 源码级 Resident Integration
        └─ 否 → 配套插件
```

模块功能可以通过配套插件或 Resident 扩展 ChatRaw 前端；独立运行的模块进程不能在运行时注入或改写 ChatRaw Core。插件和 Resident 都不能直连模块，只能通过 ChatRaw Module SDK 和 Server 网关连接。

## 3. AI 必读顺序

人或 AI 在生成代码前，按顺序完整读取：

1. [module-manifest-v1.schema.json](../backend/contracts/module-manifest-v1.schema.json)
2. [module-management-v1.schema.json](../backend/contracts/module-management-v1.schema.json)
3. [module-task-v1.schema.json](../backend/contracts/module-task-v1.schema.json)
4. [module-conformance-fixture-v1.schema.json](../backend/contracts/module-conformance-fixture-v1.schema.json)
5. [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json)
6. 修改 Plugin UI 公共接口或使用主内容区 Workspace 时，完整阅读 [Plugin UI SDK](../backend/contracts/plugin-ui-sdk-v1.json)
7. 如果选择 Resident，完整阅读 [Resident descriptor](../backend/contracts/resident-integration-v1.schema.json)、[Resident Host SDK](../backend/contracts/resident-integration-sdk-v1.json) 和 [Resident Guide](resident-module-integration-guide.md)
8. [plugin manifest example](../examples/reference-module/manifest.example.json) 或 [Resident manifest example](../examples/reference-module/manifest.resident.example.json)
9. [conformance-fixture.json](../examples/reference-module/conformance-fixture.json)
10. [reference module app.py](../examples/reference-module/app.py)
11. [reference Compose](../examples/reference-module/compose.yml)
12. [Plugin Developer Guide](plugin-developer-guide.md)
13. [Module Developer Guide](module-developer-guide.md)

不要只阅读示例代码而跳过 Schema。示例证明一种实现，Schema 定义允许的契约。

## 4. 推荐仓库结构

大型功能使用独立模块后端，再选择一种前端交付：

```text
feature-module/
├── module_manifest.json
├── src/
│   ├── api.*
│   ├── tasks.*
│   ├── storage.*
│   └── private_backend.*
├── tests/
│   ├── test_manifest.*
│   ├── test_management_api.*
│   ├── test_tasks.*
│   ├── test_restart.*
│   └── test_security_negative.*
├── deploy/
│   └── module.env.example
├── Dockerfile
├── compose.yml
└── README.md

feature-companion-plugin/
├── feature-plugin/
│   ├── manifest.json
│   ├── main.js
│   └── icon.png
├── tests/
│   └── plugin-contract.test.mjs
└── feature-plugin.zip

ChatRaw_server/ResidentIntegrations/feature-workbench/
├── integration.json
├── main.js
├── styles.css
└── tests/
```

模块的私有协议实现放在模块仓库内部，不复制到 Server、插件或公共指南。
配套插件和 Resident 二选一；不要为同一个 manifest 同时声明两种前端集成。

## 5. 最小 manifest 模板

复制后只替换明确的占位符：

```json
{
  "schema_version": "1",
  "module_id": "com.example.feature",
  "module_version": "0.1.0",
  "protocol_version": "1.0.0",
  "name": "Example Feature",
  "description": "One sentence describing the backend capability.",
  "actions": [
    {
      "action_id": "feature.run",
      "action_version": "1.0.0",
      "minimum_role": "member",
      "input_schema": {
        "type": "object",
        "additionalProperties": false,
        "required": ["text"],
        "properties": {
          "text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 4000
          }
        }
      },
      "output_schema": {
        "type": "object",
        "additionalProperties": false,
        "required": ["answer"],
        "properties": {
          "answer": {
            "type": "string",
            "maxLength": 8192
          }
        }
      },
      "supports_stream": false,
      "supports_cancel": false,
      "supports_approval": false,
      "supports_artifacts": false,
      "supports_resources": false,
      "supports_chat_projection": true
    }
  ],
  "config_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  },
  "requested_host_capabilities": [],
  "companion_plugin": {
    "id": "example-feature-companion",
    "version_range": ">=1.0.0,<2.0.0"
  },
  "administration": {
    "supports_data_purge": false
  }
}
```

不要先把所有 capability 和可选能力设为 `true`。只有实现、持久化和验收完成的能力才能声明。

上述 `companion_plugin` 是向后兼容写法。Resident 模式改为：

```json
{
  "frontend_integration": {
    "mode": "resident",
    "id": "example-feature-workbench",
    "version_range": ">=1.0.0,<2.0.0"
  }
}
```

然后严格按 [Resident Module Integration Guide](resident-module-integration-guide.md) 创建独立目录。不得让模块进程提供前端代码。

## 6. 最小配套插件模板

```js
(function () {
    'use strict';

    const PLUGIN_ID = 'example-feature-companion';
    const MODULE_ID = 'com.example.feature';
    const ACTION_ID = 'feature.run';

    async function run() {
        const status =
            await window.ChatRaw.modules.getFeatureStatus(MODULE_ID);
        if (!status.available) {
            ChatRawPlugin.utils.showToast(
                status.reason?.message || 'Feature unavailable',
                'error'
            );
            return;
        }
        const chatId = ChatRawPlugin.utils.getCurrentChatId();
        const request = {
            module_id: MODULE_ID,
            action_id: ACTION_ID,
            input: { text: 'hello' }
        };
        if (chatId) {
            request.chat_id = chatId;
            request.user_message = 'hello';
        }
        await window.ChatRaw.modules.startTask(
            request,
            chatId ? { presentation: 'conversation' } : undefined
        );
    }

    ChatRawPlugin.ui.registerToolbarButton(
        {
            id: 'run',
            icon: 'ri-pulse-line',
            label: { en: 'Example', zh: '示例' },
            order: 70,
            onClick: run
        },
        PLUGIN_ID
    );
})();
```

不得添加模块 URL、模块 Token、`fetch(moduleUrl)`、旧 proxy 隧道或用户身份字段。

## 7. 机器可读错误码

代码根据 `code` 处理，UI 显示 `message`。不得解析 message 文本。

Module SDK 本地错误：

| Code | 含义 |
|---|---|
| `invalid_sdk_argument` | 插件传给 SDK 的参数错误 |
| `module_request_failed` | Server 请求失败且没有更具体代码 |
| `module_event_stream_failed` | SSE 连接恢复失败 |
| `module_event_stream_incomplete` | SSE 在 task 终态前结束；保留 task 并等待 SDK 重连 |
| `artifact_download_failed` | 产物下载失败 |
| `invalid_event_cursor` | 模块事件 ID 无效 |

常见 Server 功能错误：

| Code | 插件应该做什么 |
|---|---|
| `module_not_enabled` | 显示不可用，不直连模块 |
| `module_not_ready` | 提示管理员检查依赖和配置 |
| `module_review_required` | 提示等待管理员审批 |
| `plugin_missing` | 提示管理员安装配套插件 |
| `plugin_disabled` | 提示管理员启用插件 |
| `plugin_incompatible` | 提示版本不兼容 |
| `resident_missing` | 提示管理员部署包含该 Resident 的 Server 构建 |
| `resident_incompatible` | 提示管理员升级匹配的 Server 或模块版本 |
| `module_action_not_found` | 停止并检查 Action ID/版本 |
| `module_action_forbidden` | 不重试，不提升用户身份 |
| `invalid_task_request` | 修正插件或输入 |
| `task_not_found` | 清除本地 task ID |
| `task_control_forbidden` | 不允许当前用户控制该任务 |
| `invalid_approval` | 刷新任务摘要 |
| `artifact_not_found` | 刷新任务或提示产物不存在 |
| `artifact_expired` | 提示产物已过期 |

完整集合以 [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json) 的 `errors` 为准。模块内部错误通过稳定的 `outcome_code` 暴露，不把堆栈、SQL、私有地址或上游响应原文传给用户。

## 8. 实现顺序

按以下顺序提交代码，禁止倒序用 UI 掩盖后端缺口：

1. 定义数据归属、角色和能力边界。
2. 写 manifest，并通过离线 conformance。
3. 实现一次性 Pair 和 Bearer 鉴权。
4. 实现 Health、Ready 和脱敏 Config。
5. 实现持久 task、幂等创建和 GET 摘要。
6. 实现持久 SSE 与断线续传。
7. 逐项实现并测试 cancel、approval、artifact 和 resource；未实现的保持 `false`。
8. 实现 Host Capability，最小化申请范围。
9. 完成 Source 部署和重启恢复。
10. 完成 Compose 网络、卷和健康检查。
11. 最后按已冻结的模式写配套插件或独立 Resident 目录，只使用公共 SDK。
12. 真实浏览器验证管理员和普通用户。
13. 完成备份恢复和安全负向检查。
14. 代码与协议稳定后再更新正式文档。

Agent 规则作用域变更必须保持归属分层：Server 管理 `personal` /
`system_default` 授权、激活容量和不可变任务快照；Agent 校验并执行冻结的 Compiled
Rule；配套插件只显示 Server 返回的 `editable` 和管理能力。不得把系统规则权限放在
前端，也不得向公共 Module Task v1 `active_rules` 增加 Agent 专用字段。Agent 专用
`rule.read` 可以向后兼容地返回冻结的 `scope`。
规则删除必须由 Server 以墓碑实现：所有新建任务与管理查询排除 `deleted_at`，但
`rule.read` 仍按 task activation 读取冻结版本。不能用物理删除、级联删除或前端隐藏
代替，也不能在删除时隐式停用。新增 Compiled Rule 行为必须提升 schema 版本并保持旧
版本解析语义不变。旧 v1.2 确定性分页与 v1 `tools[].iteration` 只保留历史解析和审计
兼容，不得回填进 v1.0/v1.1，也不得重新编译、激活或由回退 Agent 执行。

## 9. Conformance 命令

Server 仓库：

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python scripts/export-openapi.py --check
.venv/bin/python scripts/module-conformance.py contracts
.venv/bin/python scripts/module-conformance.py manifest \
  /path/to/module_manifest.json
./scripts/run-backend-tests.sh
npm run check:frontend
./scripts/run-t6-source-gate.sh
./scripts/run-t6-compose-gate.sh
```

未配对测试实例：

```bash
.venv/bin/python scripts/module-conformance.py probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE \
  --fixture /path/to/conformance-fixture.json
```

配套插件：

```bash
node --check feature-plugin/main.js
node --test tests/plugin-contract.test.mjs
unzip -t feature-plugin.zip
```

Resident：

```bash
npm run build:frontend
npm run check:frontend
npm run test:frontend
T6_FRONTEND_MODE=resident \
T6_SOURCE_SERVER_PORT=51122 \
T6_SOURCE_MODULE_PORT=8766 \
./scripts/run-t6-source-gate.sh
```

项目可以增加自己的命令，但不能删除上述契约层级。

## 10. 自动化验收清单

AI 在报告完成前逐项给出命令、退出码和证据：

### Manifest 与管理面

- [ ] Schema 验证通过。
- [ ] Pairing Code 有效期和单次消费通过。
- [ ] Pairing Code 必须显式注入，缺失时启动失败，且不出现在日志。
- [ ] Access Token 只返回一次，持久化摘要。
- [ ] 错误 Token 返回 401。
- [ ] Health 与 Ready 能区分。
- [ ] Config 不回显秘密，revision 冲突返回 409。
- [ ] Disconnect 保留数据。
- [ ] Purge 仅在声明支持时可用。

### Task

- [ ] 同 task ID + 同 digest 幂等。
- [ ] 同 task ID + 不同 digest 返回冲突。
- [ ] task/event 重启后存在。
- [ ] Event ID 严格递增。
- [ ] `Last-Event-ID` 重放无缺失、无重复副作用。
- [ ] 终态摘要和 `task.terminal` 一致。
- [ ] output 符合 manifest Schema。
- [ ] 所有 `true` 能力均有正向、拒绝和竞争测试。
- [ ] `supports_resources: true` 时覆盖临时输入单次绑定、原始字节读取和输出资源
      GET/HEAD/Range；为 `false` 时拒绝资源。

### 权限与秘密

- [ ] 未登录不能访问业务 API。
- [ ] member 不能管理插件和模块。
- [ ] member 不能创建、读取完整详情或管理系统默认 Agent 规则。
- [ ] 任意当前 admin 能管理系统规则，创建者字段不成为授权所有权。
- [ ] 系统规则与个人规则的激活冲突和合并后 10 条上限在写事务中失败关闭。
- [ ] member 能使用启用后的功能。
- [ ] Host Capability 与 task/scope/用户绑定。
- [ ] `resource.stream` Token 不进入浏览器，任务终态、模块停用或用户停用后失效。
- [ ] 普通用户不能绑定或读取其他用户的临时资源，输出资源仅任务创建者或管理员可读。
- [ ] conformance fixture 覆盖 manifest 请求的全部 Host Capability，并证明每项发生真实回调。
- [ ] `config_schema` 变化会改变权限摘要并触发管理员复审。
- [ ] 浏览器、插件、manifest、OpenAPI、日志没有模块 Token。
- [ ] 公共文件没有私有协议、私有 URL 或客户秘密。

### 部署与恢复

- [ ] 全新 Source 安装。
- [ ] 全新 Compose 安装。
- [ ] Server 重启。
- [ ] 模块重启。
- [ ] `compose down/up` 后卷数据保留。
- [ ] 模块离线时功能 fail closed，普通聊天可用。
- [ ] 私有依赖离线时 Ready/任务错误正确。
- [ ] Server 与模块分别备份。
- [ ] 恢复到新位置后管理员和 member 登录。
- [ ] 恢复后真实模块任务成功。

### 浏览器

- [ ] 管理员能看到管理入口和状态。
- [ ] 管理员新建 Agent 规则默认系统作用域并可切换为个人；系统激活有版本、哈希和影响范围确认。
- [ ] member 只看到系统规则名称、激活状态、版本和哈希，不能打开完整编辑器。
- [ ] member 看不到安装、停用、删除入口。
- [ ] member 能使用已启用的配套插件或 Resident。
- [ ] Resident 对符合角色但不可用的用户保持可见并置灰。
- [ ] Resident 对低于 `minimum_role` 的用户隐藏。
- [ ] Resident 的 `embedded` 任务不自动打开核心任务中心。
- [ ] `conversation` 任务只在对话内显示，不进入全局任务提示。
- [ ] 工具 Activity 按 `run_id + activity_id` 更新，最终 Markdown 只有一份。
- [ ] 审批、取消、产物按声明展示。
- [ ] 刷新后任务恢复。
- [ ] 控制台无错误。
- [ ] 网络请求只到 ChatRaw Server origin。

## 11. 禁止事项

AI 和人都不得：

- 为单个模块在 ChatRaw Server 中增加专用业务路由。
- 让模块进程在运行时注入代码、改写 ChatRaw Core 或向浏览器提供可执行 UI。
- 让 Resident 在安装时动态改写 ChatRaw Core 文件。
- 让插件直接连接模块或私有后端。
- 让 Resident 直接连接模块或私有后端。
- 在浏览器中保存模块 Token、任务输入、任务输出或秘密配置。
- 在浏览器中保存临时资源路径、Host Capability Token 或模块输出资源的私有地址。
- 伪造真实浏览器、客户数据、生产网络或硬件证据。
- 用 mock 通过冒充全链路验收。
- 将合成负载称为生产性能。
- 为了通过测试降低权限、删除失败路径或关闭鉴权。
- 在未实现时把 manifest capability 写成 `true`。
- 靠无限重试掩盖确定性错误。
- 自动覆盖已有数据目录或备份。
- 把 Agent–LinkDB 或任何商业私有协议写进公共指南。

## 12. AI 完成报告格式

```text
Outcome:
- What became true for the user.

Public contract:
- module_id, module version, protocol version
- actions and capability flags
- requested Host Capabilities
- frontend integration mode, ID, and range

Persistence and recovery:
- Source data path
- Compose volume
- restart evidence
- backup and restore evidence

Security:
- auth and role evidence
- browser secret-negative evidence
- private-boundary evidence

Validation:
- exact commands and results
- real browser flows
- Source and Compose flows

PENDING_ONSITE:
- customer data
- customer credentials
- customer hardware/network
- production TLS/firewall
- real upstream behavior
- production performance
```

没有证据的项目写“未验证”，不能写“应该没问题”。

---

# English execution summary

Humans and AI must derive behavior from the committed OpenAPI snapshot, JSON Schemas, Module and Resident SDK contracts, reference module, and conformance commands. Decide the plugin/module boundary and then the companion-plugin/Resident delivery mode before coding. Implement persistent protocol behavior before UI. Request the minimum Host Capabilities. Keep private dependencies private. Resident work stays inside its independent directory and stops when it needs an undocumented Core mount or SDK.

Completion requires exact command output, real Source and Compose runtime evidence, both roles in a real browser, outage behavior, restart recovery, separate Server/module backup restoration, and negative secret checks. Synthetic fixtures are engineering evidence only. Any missing customer environment, credential, network, hardware, upstream, or production-performance evidence remains `PENDING_ONSITE`.
