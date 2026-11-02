# 本机 MCP 使用手册

四个 MCP 服务，共 **23 个工具**，全部配在
`C:\Users\<user>\.dsh-beta\profiles\desktop\cordis.patch.yml`。

| MCP | 工具数 | 一句话作用 | 能否改东西 |
|---|---|---|---|
| [`docs`](./docs-mcp.md) | 4 | 读 Word / PPT / Excel / PDF / Markdown | 只读 |
| [`shell`](./shell-mcp.md) | 4 | 执行 PowerShell 与 WSL 命令 | **可写，危险** |
| [`git`](./git-mcp.md) | 6 | 查看 Git 仓库 | 只读（`git_run` 受白名单约束） |
| [`cua`](./cua-mcp.md) | 9 | 控制鼠标键盘、截屏 | **可写，需逐次确认** |

---

## 怎么用：不需要记工具名

直接用中文说需求就行，我会自动选工具。

> 把桌面上那个 docx 作业要求读出来

→ 调 `docs.read_document`

> my-project 仓库最近改了什么

→ 调 `git.git_log`

工具名只在两种情况下需要你知道：**想精确控制参数**，或**想让我跳过自动选择**。

---

## 按需求查

| 我想…… | 看这里 |
|---|---|
| 读 Word / PPT / Excel / PDF 的内容 | [docs-mcp.md](./docs-mcp.md) |
| 在电脑上执行命令、查系统状态 | [shell-mcp.md](./shell-mcp.md) |
| 看提交历史、比较改动、找某次提交 | [git-mcp.md](./git-mcp.md) |
| 让我点击界面、输入文字、截屏 | [cua-mcp.md](./cua-mcp.md) |
| 出错了 / 工具不见了 / 想关掉某个 | [troubleshooting.md](./troubleshooting.md) |

---

## 参数速查

带 `*` 的是必填。

### docs

| 工具 | 参数 |
|---|---|
| `read_document` | `path*`, `max_chars` |
| `read_markdown` | `path*`, `outline_only`, `max_chars` |
| `document_info` | `path*` |
| `supported_formats` | 无 |

### shell

| 工具 | 参数 |
|---|---|
| `run_powershell` | `command*`, `cwd`, `timeout_sec`, `force` |
| `run_wsl` | `command*`, `distro`, `timeout_sec`, `force` |
| `wsl_distros` | 无 |
| `powershell_info` | 无 |

### git

| 工具 | 参数 |
|---|---|
| `git_status` | `repo*` |
| `git_log` | `repo*`, `max_count`, `path` |
| `git_diff` | `repo*`, `staged`, `path`, `context` |
| `git_show` | `repo*`, `rev` |
| `git_branches` | `repo*` |
| `git_run` | `repo*`, `subcommand*`, `args` |

### cua

见 [cua-mcp.md](./cua-mcp.md)。

---

## 安全边界（先看这段）

| MCP | 风险 | 出错的后果 |
|---|---|---|
| `docs` | 无 | 顶多读到错误内容 |
| `git` | 无 | 顶多给错信息（无法改动仓库） |
| `shell` | **高** | **可能删文件、改系统设置** |
| `cua` | 中 | 可能点错位置，但每步需你同意 |

**建议**：不需要 `shell` 时，把 `cordis.patch.yml` 里的 `mcp-shell` 块注释掉再重启，
`docs` 和 `git` 不受影响。

---

## 相关位置

| 内容 | 路径 |
|---|---|
| 服务源码 | `projects\mcp-suite\servers\` |
| 配置 | `%USERPROFILE%\.dsh-beta\profiles\desktop\cordis.patch.yml` |
| 命令审计日志 | `projects\mcp-suite\logs\shell.log` |
| 回归测试 | `projects\mcp-suite\tests\bug_hunt.py` |
| 开发记录 | `projects\mcp-suite\PROGRESS.md` |
