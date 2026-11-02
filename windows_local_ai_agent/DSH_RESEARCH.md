# DSH_RESEARCH — computer use 接入与 mcp-suite 复用（2026-11-02）

## 一、根因（实测，推翻 10-18 的结论）

cua 服务端点不动鼠标，**不是窗口层级问题，也不是 UIPI/MCP 的问题**，而是 **exe 所在路径**决定的：

| 实验 | 完整性级别 | SetCursorPos |
|---|---|---|
| `C:\...\Python313\python.exe`（系统 Python） | Medium | 返回 1，成功 |
| 同一个 exe **复制进工作区**再跑 | **Low** | 返回 0，失败 |
| 工作区 `.venv\Scripts\python.exe` | **Low** | 返回 0，失败 |
| 系统 Python 跑**工作区里的 .py 脚本** | Medium | 脚本路径不影响 |

**规则**：DSH 会话把「工作区目录内的可执行文件」降到 Low 完整性；脚本、cwd 都不影响，**只看 exe 在哪**。Low IL 下 Windows 静默丢弃 `SetCursorPos` / `SendInput`（返回 0 且无错误码），但 `screenshot` 走 GDI 只读，所以照常可用。

## 二、修法

把 `mcp-cua` 的 command 换成工作区外的系统 Python，用 `PYTHONPATH` 借 venv 的依赖：

```yaml
command: 'C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe'
args: [ '-m', 'agent.mcp_server' ]
cwd: 'C:\Users\<user>\Desktop\windows_local_ai_agent'
env:
  CUA_CONFIRM: chat
  PYTHONPATH: 'C:\Users\<user>\Desktop\windows_local_ai_agent\.venv\Lib\site-packages'
```

验证：`--selftest` 输出 `integrity: Medium` / `cursor: (1200,900) -> (40,60) OK`；随后真机写入 Notepad 新标签成功（138 字符）。

## 三、mcp-suite 里可直接复用的东西

| 部件 | 价值 | 采用情况 |
|---|---|---|
| `shell` MCP 的 Medium IL 执行通道 | 它是本次定位根因的**对照实验工具** | 用作诊断通道 |
| `mcpcore.py`（手写 JSON-RPC，零依赖） | 可替掉 `mcp 2.x`（40+ 包 / 64 MB） | 待定（P2） |
| `shellio.py` 的「先写审计日志再执行 + 破坏性正则默认拒绝」 | 工程习惯 | 待定（P3） |
| `--selftest` / `--list-tools` 自检 | 改完不用重启就能验 | **已采用** |
| `sys.stdout.reconfigure(encoding="utf-8")` | 防中文乱码 | 已由 logging(encoding) 覆盖 |

## 四、参考

- 微软 UIPI 说明（低完整性无法向高完整性注入输入）：https://learn.microsoft.com/zh-cn/troubleshoot/power-platform/power-automate/desktop-flows/ui-automation/uipi-issues
- 本机 mcp-suite 项目：`projects/mcp-suite/README.md`

## 五、P2：去掉 mcp 2.x 依赖（2026-11-02 完成）

把 `projects/mcp-suite/servers/mcpcore.py` vendor 成 [`agent/mcpcore.py`](agent/mcpcore.py)（251 行，零依赖），
`agent/mcp_server.py` 改写为基于它注册工具。**抄了什么**：JSON-RPC 分发、initialize/tools/list/tools/call、
通知不回包、`isError` 约定、`harden_stdio()`。**改了什么**：`_as_content` 支持直接透传 image/text 内容块
（截图需要图文混排），`KNOWN_VERSIONS` 增加 `2026-07-28`，`ToolError` 对外导出。

结果：服务端不再 `import mcp`，依赖只剩 pyautogui / Pillow / pyperclip。

实测（2026-11-02 10:48）：

```
protocol: 2026-07-28
server: {'name': 'cua', 'version': '2.0.0'}
tools: 9 个
screenshot: isError=False -> ['image(1901856 b64)', 'text(74)']
move: isError=False
cursor: move(600,300) -> 系统读数 (400,200) = 真实 (600,300) ✔
```

## 六、P3：独立 venv（2026-11-02 完成）

- 位置：`C:\Users\<user>\.mcp\cua-venv`（工作区外，Medium IL）
- 内容：只装 `pyautogui` / `pillow` / `pyperclip`，**不再需要 mcp SDK**
- 配置：`command` 改成该 venv 的 `python.exe`，删除 `PYTHONPATH` 借用
- 实测：`--selftest` → `integrity: Medium`，`--list-tools` → 9 个；`move(900,500)` → 系统读数 `(600,333)` = 真实坐标

配置备份：`cordis.patch.yml.bak-20261102-cua-medium`（改 command 前）、
`cordis.patch.yml.bak-20261102-cua-venv`（换 venv 前）。

## 七、遗留

- 项目 `.venv` 现在只服务旧的 `agent.main`（LLM 版），cua 服务端不再依赖它。
- 若以后把 exe 放回工作区，会重新变成 Low IL —— 已加启动日志 `integrity=` 兜底。
