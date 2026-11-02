# mcp-suite · 进度笔记

> 状态：**已完成并写入 DSH 配置，等待重启验证**
> 执行时间：2026-10-30 14:03–14:30

## 目标

配置本机定制化 MCP，覆盖：git / Word / PPT / PDF / Markdown 文件格式，以及 PowerShell 与 WSL 调用。

## 关键决策：为什么自研

| 约束 | 实测证据 |
|---|---|
| 无 Node.js / npx / uvx / uv / pipx | `Get-Command` 全部 not found |
| 系统 Python 3.13 无 `mcp` 包 | `importlib.metadata` 查无 |
| venv 里的 mcp 是 **2.x** | 实测 `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`，提示改名 `MCPServer` |
| pip 拉包失败 | `pip download pypdf` 从清华源 **120 秒未完成** |

→ **不引入任何第三方依赖**，协议层手写，跑系统 `py -3.13`。

关键洞察：**docx/pptx/xlsx 本质是 ZIP+XML（OPC）**，用 `zipfile` + `ElementTree` 即可解析，
不需要 python-docx/openpyxl —— 这正是绕开 pip 的支点。

## 交付物

```
projects/mcp-suite/
├── servers/
│   ├── server.py      14470 B   入口 + profile 注册 + selftest
│   ├── mcpcore.py      8072 B   MCP stdio 协议（手写 JSON-RPC 2.0）
│   ├── docio.py       12524 B   docx/pptx/xlsx/pdf/md 解析
│   ├── shellio.py      6398 B   powershell / wsl 执行 + 审计日志
│   └── gitio.py        4056 B   git 只读查询 + 白名单
├── logs/shell.log              命令审计
├── install/patch-snippet.yml   配置片段备份
├── README.md
└── PROGRESS.md
```

## 验证结果（全部实测）

| 验证项 | 结果 |
|---|---|
| `--selftest` docs | **PASSED**，4 个工具 |
| `--selftest` shell | **PASSED**，4 个工具（真实跑了 `'mcp-ok'` 并取回） |
| `--selftest` git | **PASSED**，6 个工具（`push` 被正确拒绝） |
| stdin/stdout 管道握手 | **通过**：initialize → tools/list → tools/call 全部返回；通知**未回包** |
| 真实 .docx 解析 | **通过**：中文正常、标题层级保留、`max_chars` 截断生效 |
| 真实 .pdf 解析 | **按预期报错**：`scanned.pdf` 无文本层，返回明确提示而非乱码 |
| YAML 结构校验 | **通过**：顶层 9→10 项，4 个 MCP 条目齐全，`mcp-cua` 未受损 |
| 按配置参数实际拉起 | **ALL OK**：三个 server 全部 init 成功、工具数 4/4/6 |

## 配置变更

写入 `C:\Users\<user>\.dsh-beta\profiles\desktop\cordis.patch.yml`：

- 备份：`cordis.patch.yml.bak-20261030-1420`（13443 B，MD5 `FD01B525...` 与源一致）
- 新增：`mcp-docs` / `mcp-shell` / `mcp-git` 三个 `@deepseek-ai/dsh-mcp-client` 条目
- 文件：13443 B → 14978 B，444 → 469 行

## 缺陷排查记录（2026-10-30 14:50 第二轮）

表驱动回归测试：`tests/bug_hunt.py`，**50 用例全过**。

| # | 缺陷 | 根因 | 修复 |
|---|---|---|---|
| 1 | `git_log` 报 `'--date=short': not an integer` | `args.insert(2, ...)` 把参数插到 `-n` 和它的值之间 | 先构造完整列表再 append |
| 2 | `read_markdown` 不接受 `max_chars` | schema 与函数签名不一致（`read_document` 支持，它不支持） | 补 schema + 参数 |
| 3 | **`git_show` 整个函数消失** | 修 `git_diff` 时 `edit` 误删了 `def git_show(...)` 那一行，函数体变成 `git_diff` 里的死代码 | 恢复函数定义 |
| 4 | `git_diff` 无差异返回 `(no output)` | 容易被误判为失败 | 明确返回 `(no differences in the working tree)` |
| 5 | **`branch -D` / `tag -d` 未被拦截** | 正则匹配 `branch\s+-D`，但实际只检查 args，subcommand 没拼进去 | 检查时拼接 `subcommand + args` |
| 6 | **`run_wsl` 假成功**：错误发行版返回 `exit_code: 4294967295` 却是成功 | 未区分「命令失败」与「WSL 自身失败」 | `-1`/`WSL_E_` 判定为工具错误 |
| 7 | WSL 错误信息乱码 | `wsl.exe` 诊断信息是 UTF-16LE，被当 UTF-8/GBK 解 | `_decode` 检测 NUL 密度后按 UTF-16LE 解 |
| 8 | `wsl_distros` 把错误当正常列表返回 | 只判 `returncode != 0 and not text` | 合并双流检测 `WSL_E_` / 「拒绝访问」 |

第 3 条是本轮最严重的问题，由我自己的 `edit` 引入，**靠回归测试才抓出来**——这也说明单跑 selftest 不够。

## 环境状态变化（非代码问题）

14:2x 时 `run_wsl` 可用（返回内核信息、`whoami`=root）；
14:5x 起 **全机 WSL 均不可用**：`wsl -l -v` 直连也返回 `WSL_E_ACCESS_DENIED`。
即不是 MCP 进程被限制，而是 WSL 子系统本身当前拒绝访问。
代码已改为如实报错（不再伪装成功）。恢复 WSL 后无需改代码。

## 待办

- [ ] **用户重启 DSH Desktop**（本轮 8 处修复一次性生效）
- [ ] 重启后确认 14 个工具可用
- [ ] WSL 恢复后复测 `run_wsl`

## 回滚

删除配置里 `# --- local MCP suite` 标记起的整块，或还原 `.bak-20261030-1420`，然后重启。

## 已知限制

1. `.doc/.ppt/.xls` 老格式不支持（需另存为 x 版）
2. 扫描件 PDF 无文本层，读不了（诚实报错，不返回垃圾）
3. CID 字体中文 PDF 可能乱码（无第三方库无法解）
4. 本轮**只做只读**，无写入/生成文档能力
5. WSL 当前全机不可用（环境问题，非代码问题）

## 安全提示

`run_powershell` / `run_wsl` 是真实命令执行，权限 = 用户账户。
内置破坏性模式拦截（format/diskpart/shutdown/bcdedit 等）+ 全量审计日志，
**但拦不住 `Remove-Item D:\重要文件` 这类合法但致命的操作**。
不放心就注释掉 `mcp-shell` 块，docs/git 不受影响。

## 使用手册（2026-10-30 15:0x）

在 `docs/` 下补齐 6 份文档，覆盖全部 14 个工具（docs 4 + shell 4 + git 6）与 cua 的 9 个：

| 文件 | 内容 |
|---|---|
| `docs/README.md` | 总索引、参数速查表、安全边界分级 |
| `docs/docs-mcp.md` | 4 个文档工具，逐个讲作用/参数/示例/限制 |
| `docs/shell-mcp.md` | 4 个命令工具 + 破坏性拦截清单 + 审计日志用法 |
| `docs/git-mcp.md` | 6 个 git 工具 + 只读边界 + 常见报错 |
| `docs/cua-mcp.md` | 9 个桌面控制工具 + 坐标换算 + 确认机制 |
| `docs/troubleshooting.md` | 工具不出现、WSL_E_ACCESSDENIED、PDF 读不出、乱码、回滚 |

新增校验脚本 `tests/verify_docs.py`：比对 `tools/list` 的真实 schema 与文档文本，
确保**每个工具名和每个参数都在文档里出现过**。当前结果：14 个工具、全部参数，未提及项「无」。

回归测试仍为 `50 passed, 0 failed`。