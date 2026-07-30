# Security Policy / 安全政策

## Supported Scope / 支持范围

ChatRaw security fixes target the current maintained branch and the latest public release line. The
project does not currently publish a long-term version support matrix.

ChatRaw 的安全修复面向当前维护分支和最新公开发布线。项目目前不维护长期版本支持矩阵。

## Reporting a Vulnerability / 报告漏洞

If you find a vulnerability, please use GitHub Security Advisories when available. If that is not
available, open a GitHub issue with minimal public detail and ask for a private contact path.

Please include:

- Affected ChatRaw version or commit.
- Whether the issue affects the web app, backend API, plugin runtime, local data directory, or packaged app.
- Reproduction steps with minimal sensitive data.
- Expected impact and any known workaround.

如果你发现漏洞，请优先使用 GitHub Security Advisories。如果不可用，请在 GitHub issue 中只公开最少细节，
并请求私下沟通渠道。

请提供：

- 受影响的 ChatRaw 版本或 commit。
- 问题影响范围：Web app、后端 API、插件 runtime、本地数据目录或打包应用。
- 使用最少敏感数据的复现步骤。
- 预期影响和已知规避方式。

## Identity and Administrator Controls / 身份与管理员控制

ChatRaw has two account roles: `admin` and `member`. There is no public self-registration endpoint.
Administrators can list and create accounts, change either role to the other, disable or re-enable an
account, and reset another user's password. Account removal is a reversible disable operation; the
Server does not physically delete users through the administration UI.

Role changes and disabling revoke the affected user's web sessions. Demotion from `admin` to
`member`, and disabling either role, also revoke outstanding task-scoped Host Capability grants.
An administrator cannot demote or disable their own account, or reset their own password through
the administrator controls; self-service password changes belong under **Settings → Account**.
The Server must always retain at least one enabled administrator.

ChatRaw 只有 `admin` 和 `member` 两种账户角色，不提供公开的用户自助注册接口。管理员可以查看和
创建账户、在两种角色之间调整账户、停用或重新启用账户，以及重置其他用户的密码。管理界面的“移除”
采用可恢复的停用，不物理删除用户。

角色变更和停用都会撤销目标用户的 Web 会话；将 `admin` 降级为 `member` 或停用任一角色时，还会
撤销其未过期的任务型 Host Capability。管理员不能自降级、自停用，也不能通过管理入口重置自己的
密码；自助修改密码应使用“设置 → Account”。系统必须始终保留至少一个已启用的管理员。

System-default Agent rules are Server-authorized configuration, not trusted
frontend state. Only a current administrator may create, read full details,
update, compile, activate, or deactivate a `system_default` document. Any
current administrator may manage it; the creator ID is audit metadata, not an
authorization owner. Members receive only system-rule activation metadata.
Personal documents remain owner-scoped.

Activation is explicit and transactional. Server rejects invalid or stale
system candidates, duplicate record-presentation policies in the same scope,
duplicate deterministic-pagination policies for the same exact tool and scope,
and any activation that would make a user's effective task rule set exceed 10.
Legacy deterministic-pagination and `tools[].iteration` snapshots remain
readable for audit, but Server rejects compiling or reactivating them. The
fallback Agent does not retrieve all detail pages in chat.
Deletion is a Server-enforced tombstone operation: an active rule returns a
stable conflict and is never implicitly deactivated; only the personal owner or
a current administrator for a system rule may delete it. Task snapshots store
scope and Compiled version independently of later document changes or deletion.
Neither personal nor system rules grant tools, permissions, budget increases,
or a way around platform safety controls.

系统默认 Agent 规则是由 Server 授权的配置，不能信任前端隐藏或浏览器提交。只有当前管理员
可以创建、读取完整详情、更新、编译、激活或停用 `system_default` 文档；任意当前管理员都
可以管理，最初创建者只作为审计信息，不是权限所有者。普通用户只能取得系统规则的激活元数据，
个人文档仍只归本人管理。

激活必须明确且在写事务中完成。Server 会拒绝无效或基于旧 Source 的系统候选、同一作用域
重复的 record-presentation 策略、同一作用域对同一准确工具重复的确定性分页策略，以及任何
会让某位用户有效规则超过 10 条的激活。删除由 Server 写入墓碑：激活规则稳定返回冲突且不会
隐式停用；个人规则只能由所有者删除，系统规则只能由当前管理员删除。任务快照独立保存作用域
和 Compiled 版本，后续文档变化或删除都不会改写。任何规则都不能授予工具、权限、扩大预算或
绕过平台安全限制。
旧的确定性分页和 `tools[].iteration` 快照只保留审计可读性；Server 不允许重新编译或激活，
回退 Agent 也不会在聊天内逐页取得全量明细。

## Plugins and Skills / 插件与 Skills

Plugins and Agent Skills are user-enabled local extensions. Treat third-party plugin code and skill
instructions as untrusted until you review their source.

插件和 Agent Skills 都是由用户启用的本地扩展。在审查来源前，请将第三方插件代码和 skill 指令视为不可信内容。

ChatRaw v1 security boundaries:

- Skill activation is explicit. There is no implicit skill matching by default.
- Skill Manager must be installed and enabled before active skills can be injected into chat requests.
- Disabled skills cannot be activated, even when marked `trusted`.
- Skill `scripts/` files are stored only as reference resources and are not executed by ChatRaw.
- `allowed-tools` in `SKILL.md` does not grant runtime permissions in ChatRaw v1.
- `trusted` is metadata for governance and future matching behavior. It does not bypass current checks.
- Skill resources are summarized by safe relative path; resource file contents are not read into chat automatically.

ChatRaw v1 的安全边界：

- Skill 必须显式激活。默认不做隐式 skill 匹配。
- 必须安装并启用 Skill 管理器后，active skills 才能注入聊天请求。
- 已禁用的 skills 不能被激活，即使标记为 `trusted`。
- Skill `scripts/` 文件只作为参考资源保存，ChatRaw 不会执行它们。
- `SKILL.md` 中的 `allowed-tools` 不会在 ChatRaw v1 中授予运行时权限。
- `trusted` 是治理和未来匹配行为的元数据，不会绕过当前检查。
- Skill 资源只摘要安全相对路径，资源文件内容不会自动读入聊天。

## Module Task Resources / 模块任务资源

Module task uploads use the current ChatRaw session and an opaque resource ID. Files are stored
under a dedicated temporary directory with a random storage name; the browser never receives the
storage path, module credential, or task-scoped Host Capability token. A temporary input can be
bound to one task only. The module reads it through the short-lived `resource.stream` capability,
which is scoped to the module, task, user, and resource and is revoked when the task becomes
terminal or the module/user is disabled.

Module output resources remain module-owned. ChatRaw exposes them only through the authenticated,
same-origin task resource endpoint. Access is limited to the task creator or an administrator;
`GET`, `HEAD`, and single-range responses must agree on declared media type and length. Invalid
metadata or range behavior fails closed and is not redirected to another upload or document path.

模块任务上传使用当前 ChatRaw Session 和不可猜测的资源 ID。文件以随机存储名写入独立临时目录；
浏览器不会获得存储路径、模块凭证或任务级 Host Capability Token。临时输入只能绑定一个任务。
模块通过短期 `resource.stream` Capability 读取文件，该权限与模块、任务、用户及资源绑定，并在
任务进入终态、模块停用或用户停用时撤销。

模块输出资源仍归模块所有。ChatRaw 只通过登录态保护的同源任务资源接口代理它们，并将访问限制为
任务创建者或管理员。`GET`、`HEAD` 和单段 Range 响应必须与声明的媒体类型和长度一致；元数据或
Range 行为不符合契约时直接失败，不回退到其他上传或文档路径。

## Structured Model Capability / 结构化模型能力

`model.invoke.v2` uses a task-scoped, expiring capability token. The module
supplies a bounded, closed-object JSON Schema; ChatRaw forwards it only to the
configured model backend as a constrained output contract and validates the
returned object again. All Schema references are rejected.
Model credentials, upstream addresses, raw failures, and capability tokens are
never returned to the module or browser.

`model.invoke.v2` 使用任务级短期 Capability Token。模块只能提交有大小限制的闭合对象
JSON Schema；ChatRaw 仅将其作为约束输出契约交给已配置模型，并再次校验返回对象。系统
拒绝所有 Schema 引用，不向模块或浏览器返回模型凭据、上游地址、原始错误或
Capability Token。

## Local Data / 本地数据

ChatRaw stores settings, chats, plugins, skills, and indexes under the configured `DATA_DIR`. Protect this
directory like application data. Do not share it publicly if it contains API keys, private chats, private
documents, installed plugins, or installed skills.

ChatRaw 会在配置的 `DATA_DIR` 下保存设置、聊天、插件、skills 和索引。请像保护应用数据一样保护该目录。
如果其中包含 API keys、私有聊天、私有文档、已安装插件或已安装 skills，请不要公开分享。

## Operational Guidance / 运行建议

- Install plugins and skills only from sources you trust.
- Review Skill Manager diagnostics before enabling or trusting a skill.
- Keep API keys scoped to the minimum provider permissions needed.
- Avoid exposing a local ChatRaw backend to untrusted networks.
- Keep backups of important local data before testing third-party extensions.
- Deploy the Server frontend as one verified release; never mix HTML,
  JavaScript, CSS, Resident output, or SDK contracts from different commits.

- 只从可信来源安装插件和 skills。
- 启用或信任 skill 前先查看 Skill 管理器诊断信息。
- API keys 应尽量使用最小权限范围。
- 不要把本地 ChatRaw 后端暴露给不可信网络。
- 测试第三方扩展前，请备份重要本地数据。
- Server 前端必须按完整、已校验的 release 部署；不得混用不同 commit 的 HTML、
  JavaScript、CSS、Resident 产物或 SDK Contract。
