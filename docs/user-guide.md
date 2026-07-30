# ChatRaw Server 用户指南 / User Guide

## 中文

### 1. 先理解这是一个共享平台

ChatRaw Server 的所有用户使用同一个平台。聊天、文档、模型能力、插件和模块不是按用户创建独立副本。

- 你必须登录后才能进入主界面或访问业务 API。
- 普通用户可以使用管理员已经启用的功能。
- 普通用户不能安装、停用或删除插件与模块。
- 经典版导入的数据没有创建者，普通用户可以使用，但只能由管理员改名或删除。
- 新数据会记录创建者，用于防止普通用户互相修改；这不代表数据对其他用户不可见。

如果业务需要公司或客户之间的强数据隔离，应部署不同的 ChatRaw Server 实例，而不是在同一实例中创建多个用户。

### 2. 登录和账户

打开管理员提供的 ChatRaw Server 地址。未登录时，所有业务页面和 `/api/*` 数据接口都会要求认证。
平台不提供公开的用户自助注册；账户由管理员创建。管理员可以调整账户角色、停用或重新启用账户，
也可以重置其他用户的密码。角色变更、停用或管理员重置密码后，现有登录会话会失效，需要重新登录。

登录后可以在“设置 → Account”中：

- 查看用户名和角色；
- 修改自己的密码；
- 退出登录。

登录页和首次初始化页右上角可直接选择 `English` 或 `中文`。进入主界面后，
只有管理员可以在“设置 → 界面设置”中切换语言；选择会保存在当前浏览器中，并应用到核心界面的
标签、按钮、状态、确认提示、警告和错误消息。插件或 Resident Integration 提供的功能也应跟随
同一语言设置；模块协议返回的机器状态值不会直接作为界面文案显示。

修改密码后现有会话会失效，需要使用新密码重新登录。不要共享账号，不要把浏览器 Cookie 当作 API Token 保存。

### 3. 聊天与共享数据

基本聊天流程与经典 ChatRaw 相同：

1. 新建或打开聊天。
2. 选择管理员配置好的模型。
3. 按需附加图片、文档、网页内容或知识库。
4. 发送消息。

首轮回复成功保存后，Server 会使用管理员配置的聊天模型为对话生成简短标题。
普通聊天与模块任务使用同一命名流程；模型不可用或返回无效标题时会回退到首条消息摘要。
如果你已经手动改名，自动命名不会覆盖该标题。

平台用户可以看到共享聊天和文档。你可以管理自己创建的聊天和文档；经典版导入的无归属数据只能由管理员管理。

模型消息和所有模块 conversation 结果显示在左侧，模型头像位于正文左边。用户消息显示在右侧，
用户头像位于正文右边；多行 Markdown 和代码仍在各自消息内部左对齐。刷新或重新打开聊天后，
正文从 Server 已保存的消息恢复，模块执行过程不会复制最终答案。

消息中的宽 Markdown 表格会限制在消息区域内，并提供独立的横向滚动。可以在表格上使用触控板、
Magic Mouse 的横向手势，或按住 Shift 使用鼠标滚轮。ChatRaw 会在整个页面接管横向手势：
位于可横向滚动区域时只滚动该区域，位于首页或普通内容时直接停止，因此滚到边缘或在空白处
继续滑动都不会拉出 Safari 的前进/后退页面。普通纵向滚动和捏合缩放不受影响。

### 4. 功能套件：插件和模块

一个大型功能通常由后端模块和一种前端入口组成：

- **配套插件**：由管理员在 WebUI 安装和启停的按钮、开关或结果展示。
- **Resident Integration**：随 Server 源码构建的侧边栏或输入区常驻入口。
- **后端模块**：在独立服务中执行真正的任务。

普通用户不需要分别配置它们。管理员完成安装和连接后，功能入口会自动可用。

已启用的侧边栏功能入口位于对话区顶部，并由分隔线与“新对话”和对话列表分开。没有可用的
侧边栏功能时，不显示空功能区或分隔线，侧栏直接从“新对话”开始。功能入口较多时，仅顶部
功能区独立滚动，“新对话”、对话列表和底部操作保持可访问。

配套插件可以在主内容区打开交互工作台。工作台可能出现在聊天右侧、上侧、下侧，或占据整个
主区域；右、上、下模式不会阻止继续操作聊天。窄屏设备会统一显示为主区域；高度很低时，
上、下模式也会显示为主区域。工作台关闭后，
当前聊天和消息不会丢失；刷新页面后工作台保持关闭。标题栏和关闭按钮由 ChatRaw 提供，
用户点击或用键盘激活 ChatRaw 提供的所属插件入口时，键盘焦点会进入工作台关闭按钮，关闭后
返回原入口。模块任务、定时器、插件内其他控件或其他后台流程打开工作台时，当前焦点保持不变。
工作台内的表单、列表和业务状态由对应插件提供。

以 Agent 为例：

1. 聊天工具栏显示 Agent 图标。
2. 点击图标启用 Agent 模式。
3. 发送消息后，插件通过 ChatRaw Module SDK 创建任务。
4. ChatRaw 在同一条助手消息中展示执行计划、工具调用和脱敏结果。
5. 成功后执行过程默认折叠，最终 Markdown 只在当前聊天中出现一次。

插件不会直接连接 Agent，也拿不到 Agent、LinkDB 或其他模块的地址和凭证。

#### Agent 规则作用域

每位用户可以创建和管理自己的个人规则。管理员还可以发布系统默认规则；激活后，
它会进入所有用户后续新建的 Agent 任务。普通用户能看到系统规则的名称、激活状态、
版本和哈希，但不能打开 Source、编译原文、错误详情或历史候选。

创建 Source、保存新版本或编译候选都不会自动生效，必须明确激活。每个任务在创建时
冻结当时有效的规则作用域、Compiled 版本和哈希，因此修改或停用规则不会改变在途或
历史任务；同一聊天中的下一次发送会创建新任务并读取最新规则。个人规则与系统默认
规则冲突时，个人规则优先，但不能覆盖平台安全限制。

未激活的个人规则可以删除；激活规则必须先停用。删除后规则会从列表消失并允许同名
新建，但不会影响已经冻结该版本的在途或历史任务。管理员对系统规则遵循同样的
“先停用、再删除”要求；普通成员没有系统规则删除权限。

### 5. 任务状态

模块任务可能出现：

| 状态 | 含义 |
|---|---|
| Queued | 已提交，等待模块处理 |
| Running | 模块正在执行 |
| Waiting approval | 等待你批准或拒绝敏感步骤 |
| Cancel requested | ChatRaw 已请求取消，等待模块确认 |
| Succeeded | 已成功完成 |
| Failed | 已失败，界面显示安全的错误说明 |
| Cancelled | 已取消 |

并非所有模块都支持取消、审批、流式输出或产物下载。界面只会展示模块在 manifest 中声明并通过管理员审批的能力。

刷新页面后，ChatRaw 会根据任务 ID恢复仍在执行的任务。浏览器不保存模块地址、模块 Token、任务输入或任务输出。
右下角任务入口只显示仍在运行或有尚未查看结果的任务；查看终态后入口消失。直接在对话或
Resident 工作区中展示的任务不会重复出现在这个全局入口中。

对话内的“执行过程”只包含模块明确提供的计划和工具活动，不是模型隐藏思维链。工具参数和结果是
经过脱敏、截断的预览；最终答案使用同一条消息中的唯一正文区域。

### 6. 功能不可用时

如果功能入口显示不可用：

- `Plugin missing/disabled/incompatible`：配套插件未安装、未启用或版本不兼容。
- `Resident missing/incompatible`：当前 Server 构建未包含匹配的常驻入口，或它与模块版本不兼容。入口会保留但置灰。
- `Module unhealthy/unreachable`：模块未运行或网络不可达。
- `Module not ready`：模块依赖或配置未就绪。
- `Review required`：模块版本或权限发生变化，等待管理员重新批准。
- `Module disabled`：管理员已停用。

普通用户不应尝试修改模块地址。把界面显示的状态和发生时间提供给管理员即可。

当 Agent 模块不可用时，Agent 插件不会劫持消息；关闭 Agent 模式后，普通聊天仍然可以使用。

### 7. 安全注意事项

- 只使用管理员提供的 Server 地址。
- 不要在聊天中粘贴不必要的访问令牌、Cookie 或生产密钥。
- 审批对话框只表示当前任务请求的动作，不是永久授权。
- 下载模块产物后，由本机安全策略负责扫描和保存。
- 发现自己能够打开用户、插件或模块管理入口时，停止操作并报告管理员。

### 8. 获取帮助

向管理员提供：

- 发生时间；
- 使用的功能名称；
- 当前聊天 ID（如可见）；
- 页面显示的公开错误码；
- 是否能正常使用普通聊天。

不要发送密码、Cookie、模块 Token、模型 API Key 或 LinkDB 凭证。

---

## English

### 1. One shared platform

All users share one ChatRaw Server instance. Chats, documents, model access, plugins, and modules are not duplicated per user.

- Authentication is required before accessing product pages or APIs.
- Members can use features enabled by an administrator.
- Members cannot install, disable, or remove plugins or modules.
- Imported classic data has no creator. Members can use it, but only administrators can rename or delete it.
- New data records its creator to prevent members from modifying each other's resources; this is not a visibility boundary.

If separate companies or customers require strong data isolation, deploy separate Server instances.

### 2. Sign-in and account

Use the Server URL supplied by your administrator. After signing in, open **Settings → Account** to view your role, change your password, or sign out.

ChatRaw has no public self-registration; an administrator creates accounts. Administrators can
change an account's role, disable or re-enable it, and reset another user's password. A role change,
account disable, or administrator password reset invalidates existing sessions and requires a new
sign-in.

Changing your password invalidates the current session. Sign in again with the new password. Do not share accounts or retain browser cookies as API tokens.

### 3. Chats and shared data

The chat flow remains familiar:

1. Create or open a chat.
2. Use a model configured by the administrator.
3. Attach images, documents, web content, or knowledge-base context as needed.
4. Send the message.

After the first assistant reply is saved, the Server uses the administrator-configured
chat model to generate a concise title. Normal chats and module tasks use the same
title flow. If the model is unavailable or returns an invalid title, ChatRaw falls
back to a summary of the first message. Automatic naming never overwrites a manual
rename.

Platform users can see shared chats and documents. You can manage resources you created; only administrators can manage ownerless classic resources.

Model messages and module conversation results appear on the left, with the
model avatar before the content. User messages appear on the right, with the
user avatar after the content. Multiline Markdown and code remain left-aligned
inside each message. Reopening a chat restores persisted message bodies without
duplicating a module's final answer.

Wide Markdown tables stay inside the message surface and provide their own horizontal scroll.
Use a trackpad or Magic Mouse horizontal gesture, or hold Shift while using a mouse wheel. ChatRaw
owns horizontal gestures across the page: a horizontally scrollable region moves, while the home
surface and ordinary content consume the gesture. Continuing at an edge or over blank space therefore
does not reveal Safari history navigation. Normal vertical scrolling and pinch zoom remain unchanged.

### 4. Feature suites

A large feature has a backend module and one frontend integration:

- a **companion plugin** installed and managed by an administrator, or a source-built **Resident Integration** for a persistent entry;
- a **backend module** that performs the task in an independent service.

Members do not connect these pieces manually. Once the administrator completes installation and pairing, the feature entry point becomes available.

Enabled sidebar feature entries appear above the chat controls, separated from **New Chat** and
the chat list by a divider. When no sidebar feature is available, ChatRaw omits the empty feature
section and divider, so the sidebar starts with **New Chat**. When feature entries exceed the
available space, only the feature section scrolls; **New Chat**, the chat list, and footer actions
remain accessible.

A companion plugin may open an interactive workspace in the main content area. It can appear to
the right, above, below, or in place of the visible chat surface. Right, top, and bottom workspaces
leave chat interactive. Narrow screens use the main presentation; short screens also use it for
top and bottom workspaces. Closing a workspace preserves the current chat and messages; reloading
the page starts with the workspace closed. When a user activates that plugin's ChatRaw-provided entry
with a click or keyboard, focus moves to the Host close button and returns to the entry on close.
Opens from module tasks, timers, controls inside plugin content, or other background flows preserve
the current focus.

For Agent, the plugin uses the ChatRaw Module SDK. It never connects directly to Agent or receives Agent, LinkDB, or other private module credentials.
Agent execution appears inside one assistant message: explicit plans, tool calls,
redacted results, and one final Markdown answer. Successful timelines collapse by
default and can be expanded again.

#### Agent rule scopes

Each user can manage personal rules. Administrators may also publish a
system-default rule that applies to every user's future new Agent tasks.
Members can see its name, activation state, version, and hash, but cannot open
its Source, compiler output, validation details, or candidate history.

Creating a Source version or compiling a candidate never activates it.
Each task freezes the effective scope, Compiled version, and hash at creation,
so later activation changes do not alter in-flight or historical tasks. The
next send in the same chat is a new task and reads the latest active rules.
Personal rules take precedence over conflicting system defaults, while platform
security controls remain non-overridable.

The fallback Agent supports aggregate summaries and one explicitly requested
detail page. It does not walk pages for all details or exports in chat. A
single-page result remains explicitly partial, and neither a personal nor a
system rule can raise the fixed safety limits.

An inactive personal rule may be deleted; an active rule must first be
deactivated. It disappears from ordinary lists and its name may be reused, but
in-flight and historical tasks that froze the version remain readable. The
same explicit deactivate-then-delete rule applies to administrator-managed
system defaults; members cannot delete system rules.

### 5. Task states

| State | Meaning |
|---|---|
| Queued | Accepted and waiting for module execution |
| Running | Module work is in progress |
| Waiting approval | A sensitive step needs your decision |
| Cancel requested | ChatRaw requested cancellation |
| Succeeded | Completed successfully |
| Failed | Failed with a safe public explanation |
| Cancelled | Cancellation completed |

Streaming, cancellation, approval, and artifacts are optional action capabilities. ChatRaw only exposes capabilities declared by the manifest and approved by an administrator.

After a page reload, ChatRaw resumes tasks by task ID. The browser does not retain module addresses, tokens, task input, or task output.
The bottom-right task entry only appears for running tasks or results that have not
yet been viewed, and disappears after a terminal result is viewed. Tasks presented
inside a conversation or Resident workspace are not duplicated in this global entry.

The execution process contains explicit module-provided plans and tool activity,
not hidden model reasoning. Tool inputs and results are redacted, bounded previews.

### 6. When a feature is unavailable

Common reasons include:

- companion plugin missing, disabled, or incompatible;
- Resident Integration missing or incompatible;
- module unhealthy or unreachable;
- module dependency or configuration not ready;
- changed permissions awaiting administrator review;
- module disabled by an administrator.

Report the visible status and time to an administrator. Do not attempt to discover or edit the private module address.

If Agent is unavailable, its plugin does not take over message sending. Disable Agent mode and continue with normal chat.

### 7. Security

- Use only the Server URL supplied by your administrator.
- Do not paste unnecessary access tokens, cookies, or production keys into chats.
- An approval dialog authorizes one task decision, not permanent access.
- Local security policy applies to downloaded artifacts.
- If a member account can access user, plugin, or module management controls, stop and report it.

### 8. Support information

Provide the time, feature name, public error code, chat ID when available, and whether normal chat still works. Never send passwords, cookies, module credentials, model API keys, or LinkDB credentials.
