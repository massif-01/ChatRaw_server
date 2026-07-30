# ChatRaw Server 管理员指南 / Administrator Guide

## 中文

### 1. 管理员负责什么

管理员控制一个共享 ChatRaw Server 实例：

- 查看和创建用户、调整角色、启用或停用账户，并重置其他用户的密码；
- 配置模型、插件与模块；
- 审批模块权限和版本变化；
- 查看安全审计记录；
- 组织 Server 与各模块的备份、恢复和升级；
- 判断本地工程验证与客户现场验收的边界。

管理员不是模块内部数据库的自动管理员。模块拥有自己的数据、依赖和恢复流程。

### 2. 首次安装

#### Source

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python scripts/prepare-server-secrets.py --data-dir data
DATA_DIR="$PWD/data" CHATRAW_LOOPBACK_DEV=1 \
  .venv/bin/python backend/main.py
```

#### Docker Compose

```bash
./scripts/create-module-network.sh
docker compose up -d --build
docker compose exec chatraw \
  python -c "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
```

访问 `/setup` 并创建首位管理员。Setup Token 只用于首次创建管理员；不要把它提交到 Git、聊天或工单。

生产环境要求：

- HTTPS 终止于可信反向代理；
- 反向代理保留正确的 Host 和 Origin；
- Server 数据目录或卷只对运行账户可写；
- 不设置 `CHATRAW_LOOPBACK_DEV=1`；
- 只发布 Server 端口，不发布模块或模块私有依赖端口。

`GET /health` 表示进程存活；`GET /ready` 还会验证数据库和 Schema。负载均衡应使用 `/ready`。

### 3. 用户与权限

ChatRaw 不提供公开的用户自助注册。管理员在“设置 → Users”中查看现有账户，创建
`admin` 或 `member`，并可在这两种角色之间调整其他账户：

- `admin` 可以管理用户、模型、插件和模块。
- `member` 可以使用共享数据和已启用功能，但不能管理插件或模块。

移除用户时应停用账户，而不是物理删除；停用的账户可以重新启用。角色变更和停用都会使目标用户的
现有会话失效；将管理员降级为普通用户或停用任一账户时，其未过期的任务型 Host Capability 也会
被撤销。管理员重置其他用户的密码后，该用户需要使用新密码重新登录。

管理员不能自降级、自停用，也不能从 Users 管理入口重置自己的密码；修改自己的密码应使用
“设置 → Account”。系统始终要求至少保留一个已启用管理员。操作前确认目标用户名和当前角色。
当前权限模型只有 `admin` 与 `member`，不提供自定义权限组或更细粒度角色。

管理界面支持 `English` 和 `中文`。语言选择保存在浏览器中，Users、Modules、Account、
插件、Resident Integration、任务状态以及操作结果应统一使用当前语言。认证和用户管理
API 会同时返回稳定的错误 `code` 与英文诊断 `detail`；前端按 `code` 显示本地化消息，
不要依赖解析 `detail` 文本。

### 4. 插件管理

插件是管理员安装的可信前端代码。它与 ChatRaw 页面运行在同一 JavaScript 上下文中，不是浏览器安全沙箱。

安装前检查：

- 来源和版本；
- `manifest.json` 的 hook、proxy、settings 和依赖；
- `main.js` 是否访问不需要的数据或外部地址；
- 是否确实需要其声明的能力；
- 是否是某个模块要求的配套插件版本。

普通用户能使用已启用插件，但不能安装、停用或删除。禁用或删除插件会移除前端入口，不会自动删除模块数据。

### 4.1 系统默认 Agent 规则

管理员可以在 Agent 配套插件中把新规则作用域选为“系统默认”或“个人”；新版插件对
管理员默认选中“系统默认”。系统规则只有在候选结构校验通过、管理员核对实际
Compiled 内容并二次确认激活后，才会进入所有用户后续创建的新任务。

激活前必须核对 Source 版本、Compiled 版本、哈希、`kind` 和策略字段。“结构校验通过”
只说明 JSON 契约有效，不代表模型已经验证业务正确性。系统规则只能激活当前 Source
版本生成的候选；旧 Source 候选不会显示激活操作，Server 也会拒绝越过检查。

任意当前管理员都能管理系统规则。普通用户只能看到名称、激活状态、版本和哈希，不能
读取 Source、编译模型原文、错误详情或历史候选。个人规则仍只由所有者管理，并在与
系统默认规则冲突时优先。系统规则与每位用户的个人规则合并后每任务最多 10 条；冲突
或超限会在激活事务中失败，不会静默截断。

规则变更只影响后续新任务。任务创建时已经冻结的作用域、版本和哈希不会漂移。升级到
Schema 16 前必须停止写入并备份；旧 Server 不能直接打开迁移后的数据库，回滚代码时
必须同时恢复匹配的迁移前快照。

未激活规则可由个人所有者或系统规则管理员删除；激活规则必须先明确停用，Server 不会
在删除时自动停用。删除只写入墓碑，普通列表和后续任务不再选择该规则，但历史及在途任务
仍可读取冻结版本；删除后可以新建同名规则。旧的 Compiled Rule v1.2
`deterministic_pagination` 与 v1 `tools[].iteration` 快照仍可读取，但不得新编译或重新
激活。回退 Agent 只支持聚合摘要或用户明确指定的一页明细；全量明细与导出必须交给独立的
批处理工作流。规则不能提高 Agent 固定的调用、并发、页大小或超时上限。

### 5. 连接和启用模块

1. 生成至少 16 个字符的一次性 Pairing Code，通过部署系统的环境变量或 Secret 注入模块后启动。模块不能把它输出到日志。
2. 在“设置 → Modules”输入模块在模块网桥中的地址和 Pairing Code。
3. ChatRaw 获取 manifest，但不会立即启用模块。
4. 审查：
   - `module_id`、版本和协议版本；
   - Action、最低角色和输入/输出 Schema；
   - 流式、取消、审批、产物和聊天投影能力；
   - 请求的 Host Capability；
   - 前端集成模式、ID 与版本范围；
   - 是否支持数据清理。
5. 批准 manifest。
6. 配置非秘密字段和秘密字段。已有秘密只显示“已配置”，不会回显。
7. Plugin 模式：安装并启用匹配版本的配套插件。Resident 模式：确认当前 Server 构建包含匹配的 Resident；WebUI 不会动态安装 Resident 源码。
8. 保存配置后，ChatRaw 会自动执行一次 Check，并在 WebUI 中对异步依赖进行有界复核；如果依赖仍未就绪，管理员应再次执行 Check，确认 Health、Ready、Config 和 Frontend Integration 都通过。
9. 启用模块。

任何影响权限边界的 manifest 变化都会进入 `review required`，原 Capability Grant 被撤销；管理员必须重新检查和批准。权限边界包括模块主版本、Action 契约和能力、Host Capability、前端集成模式/ID/版本约束、数据清理能力，以及完整的 `config_schema`。因此新增秘密配置字段也一定会重新触发审核。

`model.invoke.v2` 是高风险的任务级结构化模型能力。它允许模块提交受限 JSON Schema，
但不允许模块读取模型密钥或绕过 Server 直连模型；Server 会使用约束解码并在回传前再次
验证 Schema。只有确实需要稳定机器输出、且不能用确定性代码完成的模块才应获批。

### 6. 模块生命周期

| 操作 | 作用 | 数据 |
|---|---|---|
| Check/Refresh | 重新读取状态或 manifest | 保留 |
| Enable | 允许用户创建任务 | 保留 |
| Drain | 拒绝新任务，等待现有任务结束 | 保留 |
| Disable | 拒绝新任务 | 保留 |
| Disconnect | 删除 ChatRaw 中的连接凭证 | 模块数据保留 |
| Purge data | 请求模块删除自己的持久数据 | 删除，且不可撤销 |

不要把 Disconnect 当作卸载或删除。需要下线模块时：

1. Drain；
2. 等待活动任务结束；
3. Disable；
4. 备份模块数据；
5. Disconnect；
6. 停止模块服务。

只有明确要求永久清除时才执行 Purge data。

### 7. 网络边界

推荐 Compose 拓扑：

```text
浏览器 ──HTTPS──> ChatRaw Server
                    │
          chatraw-modules 外部网桥
                    │
                  Module
                    │
             模块私有 internal 网桥
                    │
              私有数据库/依赖
```

- Server 与模块加入 `chatraw-modules`。
- 模块私有依赖只加入模块自己的 internal 网络。
- 私有依赖不加入 `chatraw-modules`。
- 模块和私有依赖默认不发布宿主机端口。
- 浏览器只能访问 Server。

创建公共模块网桥：

```bash
./scripts/create-module-network.sh
```

### 7.1 模块任务临时资源

Module SDK 的临时输入资源与普通文档上传完全独立：它没有核心页面入口，不进入文档表、解析器或
索引。任何已登录用户都可以通过同源 Module SDK 上传临时资源；是否展示上传操作由插件决定，
不是 Server 对插件启用状态的额外授权。默认单文件上限为 100 MiB，可通过
`CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES` 调整；未设置时使用默认值，显式设置为非法值会使
Server 启动失败，不会静默回退。

未绑定任务的临时文件在 24 小时后清理。文件绑定任务后不能再次绑定；任务进入终态后保留 24 小时，
随后清理 Server 的临时输入文件及其记录。模块自己的输出文件仍由模块负责保存、过期和备份，Server
只保存授权所需的引用。

管理员应把 Server 数据目录视为敏感数据，不要公开临时资源目录。反向代理必须允许 `GET`、`HEAD`
和单段 Range，并保留 `Content-Length`、`Content-Range`、`Content-Type` 和
`Content-Disposition`；不要缓存带登录态的任务资源响应。

单文件上限不是按用户或全站累计配额。未绑定资源在清理期限内仍占用磁盘，因此管理员还应在反向代理
设置与 Server 一致或更小的请求体上限，并监控临时资源目录和数据卷剩余空间。不要通过增大单文件
上限代替容量规划。

### 8. 经典数据导入

先停止经典 ChatRaw。导入工具：

- 只读取经典目录；
- 要求 Server 目标目录不存在；
- 使用 SQLite 一致性快照；
- 在副本上执行迁移；
- 比较经典表的行数与内容摘要；
- 验证经典数据保持无归属；
- 再次确认经典源文件没有变化。

```bash
.venv/bin/python -m backend.server_data import-classic \
  --source-data-dir /srv/chatraw-classic \
  --server-data-dir /srv/chatraw-server \
  --confirm-source-quiesced
```

保留目标目录中的 `import-manifest.json`。导入不等于备份；上线前再创建一份 Server 备份。

### 9. Source 备份与恢复

停止 Server 和会写入 Server 数据的维护任务：

```bash
.venv/bin/python -m backend.server_data backup \
  --data-dir /srv/chatraw-server \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --confirm-source-quiesced

.venv/bin/python -m backend.server_data verify \
  --backup-dir /srv/backups/chatraw-2026-07-23
```

恢复到新目录：

```bash
.venv/bin/python -m backend.server_data restore \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --data-dir /srv/chatraw-restored \
  --confirm-destination-quiesced
```

先用恢复目录启动一个隔离实例，验证管理员登录、普通用户登录、聊天、文档、插件和模块注册记录，再切换正式服务。

### 10. Compose 备份与恢复

备份当前项目卷：

```bash
mkdir -p backups
docker compose stop chatraw
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup" \
  chatraw python /app/server_data.py backup \
  --data-dir /app/data \
  --backup-dir /backup/chatraw-2026-07-23 \
  --confirm-source-quiesced
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup:ro" \
  chatraw python /app/server_data.py verify \
  --backup-dir /backup/chatraw-2026-07-23
```

恢复时使用新的 Compose project，从而创建新卷：

```bash
COMPOSE_PROJECT_NAME=chatraw-restored docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup:ro" \
  chatraw python /app/server_data.py restore \
  --backup-dir /backup/chatraw-2026-07-23 \
  --data-dir /app/data \
  --confirm-destination-quiesced \
  --allow-empty-destination

COMPOSE_PROJECT_NAME=chatraw-restored docker compose up -d
```

`--allow-empty-destination` 只允许现有的**空目录或新卷**，仍拒绝覆盖任何文件。

每个模块必须单独备份。Server 备份只包含 Server 数据和模块注册信息，不包含 Agent、LinkDB 或其他模块的数据卷。

### 11. 升级与回滚

升级前：

1. 阅读目标版本的协议、Schema 和迁移变化。
2. Drain 高价值模块。
3. 停止写入。
4. 分别备份 Server 和每个模块。
5. 验证所有备份。
6. 记录当前镜像或 Git commit。

升级后检查：

- `/ready`；
- 管理员和普通用户登录；
- 经典导入数据；
- 模型验证；
- 插件加载；
- 模块 Health/Ready/Config/Plugin；
- 版本变化是否触发重新审批；
- Agent 全链路。

跨数据库迁移回滚时，代码和数据必须回到同一备份时间点。不要让旧代码打开已经升级到更高 Schema 的数据库。

### 12. 故障处理

#### Server 无法 Ready

检查日志、数据目录权限和数据库 Schema。不要删除数据库锁文件或手工修改 Schema；先停止服务并从已验证备份恢复。

#### 模块 Unreachable

检查模块进程、`chatraw-modules` 网络、服务别名和模块地址。不要把模块端口临时暴露到公网作为修复。

#### 模块 Not Ready

查看模块自己的依赖状态和缺失配置。Health 正常只表示模块进程存活。

#### Review required

比较新旧 manifest、权限摘要和前端集成版本。确认变化后重新批准，不要绕过审批状态。

#### 用户无法登录

确认用户未被停用、密码是否已重置、浏览器是否访问正确 HTTPS 域名。检查服务器时间和反向代理 Origin/Host。

### 13. 审计与验收

管理员应保留：

- 安装和升级版本；
- 备份 manifest 与 verify 输出；
- 模块审批和权限变化；
- Source/Compose conformance 输出；
- 现场验收人、环境和时间。

本地 fixture、模拟 API 和合成负载只能证明工程契约。客户数据、客户 Token、真实硬件/网络、生产 TLS/防火墙、真实上游行为与性能必须标记 `PENDING_ONSITE`，直到现场证据完成。

---

## English

### Administrator responsibilities

Administrators manage users, models, trusted frontend plugins, backend module connections, permission reviews, audit events, upgrades, and recovery for one shared Server instance. Module-owned databases and private dependencies remain the responsibility of each module.

### Installation

Use the Source or Compose commands in the [README](../README.md). Protect the one-time Setup Token. Production requires HTTPS, a trusted reverse proxy, a protected data volume, and no loopback development mode.

`/health` proves process liveness. `/ready` also checks the database and supported Schema and is the correct load-balancer target.

### Users

ChatRaw has no public self-registration. Under **Settings → Users**, administrators can list and
create accounts, change another account between `admin` and `member`, disable or re-enable it, and
reset another user's password. Members use shared data and enabled features but cannot manage
plugins or modules.

Removing access means disabling the account, not physically deleting it. Role changes and disabling
revoke the affected user's sessions. Demoting an administrator or disabling either role also revokes
outstanding task capability grants. An administrator cannot demote or disable their own account, or
reset their own password from Users; use **Settings → Account** for a self-service password change.
Keep at least one enabled administrator. ChatRaw does not define custom permission groups or roles
beyond `admin` and `member`.

### Plugins are trusted code

Plugins execute in the ChatRaw page JavaScript context. Review their source, manifest hooks, proxy declarations, dependencies, and companion-module compatibility before installation. Disabling a plugin removes its frontend entry point; it does not delete module data.

### System-default Agent rules

Administrators may create a personal or system-default Agent rule; the new
companion plugin defaults administrators to the system scope. A system rule
affects every user's future new tasks only after its candidate passes structural
validation and an administrator reviews and explicitly confirms activation.
“Structure validated” is not a business-correctness review: verify the Source
version, Compiled version, hash, `kind`, and policy fields. Server rejects a
system candidate compiled from an older Source version.

Any current administrator can manage system rules. Members see only name,
activation state, version, and hash. Personal rules remain owner-managed and
take precedence over conflicting system defaults. The combined limit remains
10 rules per task; conflicts and over-capacity activation fail transactionally
without truncation. Existing task snapshots never drift.

Back up the quiesced Server database before Schema 16. Inactive personal rules
may be deleted by their owner and inactive system rules by an administrator.
Server never deactivates a rule as a side effect of deletion. Deletion writes a
tombstone: ordinary lists and future tasks omit it, frozen in-flight and
historical snapshots remain readable, and the name may be reused. Legacy
Compiled Rule v1.2 `deterministic_pagination` and v1 `tools[].iteration`
snapshots remain readable, but cannot be compiled or reactivated. The fallback
Agent supports aggregate summaries or one explicitly requested detail page
only; bulk details and exports belong to a separate workflow. Rules cannot
raise fixed Agent call, concurrency, page-size, or timeout limits. Rolling back
to older Server code requires the matching pre-migration data snapshot.

### Module onboarding

Pair with a fresh one-time code, review the manifest, approve permissions, and configure values and secrets. For plugin mode, install the compatible companion plugin. For Resident mode, deploy a Server build containing the compatible source package; the WebUI does not install Resident code dynamically. After a configuration save, ChatRaw runs one automatic Check and the WebUI performs bounded follow-up checks for asynchronous dependencies. If a dependency is still not ready, run Check again. Confirm Health/Ready/Config/Frontend Integration, and then enable the module.

Permission-relevant manifest changes revoke grants and require a new review.
`model.invoke.v2` is a high-risk, task-scoped structured-model capability.
Approve it only when a module genuinely needs stable machine output that
deterministic code cannot produce. The module never receives model credentials
or a direct upstream address; Server constrains and revalidates the JSON object.

| Operation | Effect | Module data |
|---|---|---|
| Check/Refresh | Refresh status or manifest | Preserved |
| Enable | Allow new tasks | Preserved |
| Drain | Reject new tasks while current work finishes | Preserved |
| Disable | Reject new tasks | Preserved |
| Disconnect | Remove the Server credential | Preserved |
| Purge data | Ask the module to erase persistent data | Destroyed |

Drain, disable, back up, disconnect, and stop in that order. Purge only for an explicit permanent-erasure request.

### Network boundary

Only Server is browser-facing. Server and modules share the external `chatraw-modules` bridge. A module's databases and private dependencies belong on a separate internal network. Do not publish module or private-dependency ports by default.

Module task inputs use a dedicated temporary store and do not enter the normal document upload,
parser, or index. Any signed-in user can call the same-origin SDK upload; a plugin decides whether
to expose that operation, but its enabled state is not an additional Server authorization check.
The default limit is 100 MiB per file and can be changed with
`CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES`; an explicitly invalid value prevents startup instead of
falling back. Unbound inputs expire after 24 hours, and task-bound inputs become eligible for
cleanup 24 hours after the task reaches a terminal state. Preserve `GET`, `HEAD`, single-range, and
content metadata headers at the reverse proxy, and do not cache authenticated task resource
responses. The per-file limit is not a per-user or aggregate quota: set an equal or smaller request
body limit at the reverse proxy and monitor temporary storage and free disk space. Module-owned
output files require their own backup and retention policy.

### Classic import

Stop the classic service and import into a new destination:

```bash
.venv/bin/python -m backend.server_data import-classic \
  --source-data-dir /srv/chatraw-classic \
  --server-data-dir /srv/chatraw-server \
  --confirm-source-quiesced
```

The tool snapshots SQLite, migrates the copy, compares classic content, preserves ownerless legacy semantics, and verifies the source remained unchanged.

### Backup and restore

Stop writes, create a backup, and verify it before relying on it:

```bash
.venv/bin/python -m backend.server_data backup \
  --data-dir /srv/chatraw-server \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --confirm-source-quiesced

.venv/bin/python -m backend.server_data verify \
  --backup-dir /srv/backups/chatraw-2026-07-23
```

Restore into a new path:

```bash
.venv/bin/python -m backend.server_data restore \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --data-dir /srv/chatraw-restored \
  --confirm-destination-quiesced
```

For Compose, use the exact commands in the Chinese section above: stop the service, run the production image against the current volume to create and verify a backup, then restore into a new Compose project and its empty volume. `--allow-empty-destination` never permits overwriting files.

Server backups do not contain module-owned volumes. Back up and restore every module independently.

### Upgrade and incident rules

Before an upgrade, drain modules, stop writes, verify Server and module backups, and record the current image or commit. Afterward, verify both roles, imported data, models, plugins, module review state, and the Agent chain.

Never open a newer database with older code. Never expose a private module port as a quick incident workaround.

### Evidence boundary

Retain backup manifests, verification output, permission reviews, conformance output, and environment-specific acceptance records. Fixtures and synthetic loads are engineering evidence only. Customer data, credentials, hardware, networks, production TLS/firewall, upstream behavior, and performance remain `PENDING_ONSITE` until verified on site.
