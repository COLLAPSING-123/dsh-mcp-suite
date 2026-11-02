# mcp-suite · 本机零依赖 MCP 服务器

三个 MCP server，覆盖 **文档读取（Word/PPT/Excel/PDF/Markdown）**、**PowerShell + WSL 执行**、**Git 只读查询**。

已写入 DSH 配置：`C:\Users\<user>\.dsh-beta\profiles\desktop\cordis.patch.yml`

> **使用手册**：[`docs/README.md`](./docs/README.md) —— 每个工具的作用、参数、示例、注意事项。
> 想直接用，看那一份就行；本文件讲的是「为什么这么实现」。

---

## 为什么是自研的

本机**没有 Node.js**（`npx`/`uvx` 全无），pip 从清华源拉包 120 秒不返回，
而 `windows_local_ai_agent\.venv` 里的 mcp 是 **2.x**（`mcp.server.fastmcp` 已改名 `MCPServer`，直接 import 报
`ModuleNotFoundError`）。

所以这里**不依赖任何第三方包**：协议层手写（`mcpcore.py`），文档解析用 stdlib
（docx/pptx/xlsx 本质是 ZIP+XML），跑系统 Python 3.13。

---

## 目录

```
projects/mcp-suite/
├── servers/
│   ├── server.py      # 入口：--profile docs|shell|git
│   ├── mcpcore.py     # MCP stdio 协议（JSON-RPC 2.0，手写）
│   ├── docio.py       # docx/pptx/xlsx/pdf/md 解析
│   ├── shellio.py     # powershell / wsl 执行
│   └── gitio.py       # git 只读查询
├── docs/              # 使用手册
│   ├── README.md          # 总索引 + 参数速查 + 安全边界
│   ├── docs-mcp.md        # 4 个文档工具
│   ├── shell-mcp.md       # 4 个命令工具
│   ├── git-mcp.md         # 6 个 git 工具
│   ├── cua-mcp.md         # 11 个桌面控制工具
│   └── troubleshooting.md # 排障
├── tests/
│   ├── bug_hunt.py        # 50 用例回归测试
│   └── verify_docs.py     # 校验文档与代码一致
├── logs/shell.log     # 每条 shell 命令的审计日志
├── install/
│   └── patch-snippet.yml   # 配置片段（备份用）
├── README.md
└── PROGRESS.md
```

---

## 怎么用

### 1. 重启 DSH

配置改的是启动文件，**必须重启 DSH Desktop** 才生效（关掉再开，不是刷新页面）。

### 2. 验证工具是否出现

重启后直接问：

> 用 document_info 看一下 `C:\Users\<user>\Documents\report.docx`

能返回大小/修改时间就说明 MCP 通了。

### 3. 命令行自查（不用重启）

```powershell
$py = "C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe"
$srv = "C:\Users\<user>\Documents\deepseek-harness\default-workspace\projects\mcp-suite\servers\server.py"

# 三个 profile 的自检
& $py $srv --profile docs  --selftest
& $py $srv --profile shell --selftest
& $py $srv --profile git   --selftest

# 看工具清单
& $py $srv --profile docs --list-tools
```

预期输出 `SELFTEST PASSED`。

---

## 工具清单

### docs（4 个，全部只读）

| 工具 | 作用 |
|---|---|
| `read_document` | 读 `.docx/.pptx/.xlsx/.pdf/.md/.txt/.csv/.json`，返回 markdown 风格文本 |
| `read_markdown` | 读 md 原文，或只给标题树（`outline_only`） |
| `document_info` | 只看类型/大小/修改时间，不读正文 |
| `supported_formats` | 列出支持的扩展名 |

### shell（4 个，前两个会写）

| 工具 | 作用 |
|---|---|
| `run_powershell` | 跑 PowerShell 5.1，返回 exit_code / stdout / stderr |
| `run_wsl` | 在 WSL 里跑 bash |
| `wsl_distros` | 列出 WSL 发行版 |
| `powershell_info` | PS 版本 / OS 版本 / 执行策略 |

### git（6 个，全部只读）

`git_status` / `git_log` / `git_diff` / `git_show` / `git_branches` / `git_run`（仅放行白名单子命令）

---

## 设计上的几个关键点

1. **`notifications/initialized` 绝不回包** —— 通知没有 `id`，回了客户端会解析错乱。
2. **工具失败返回 `isError: true`**，而不是 JSON-RPC 的 `error` 字段 —— 后者会被宿主当成协议故障。
3. **Windows 强制 UTF-8**：`sys.stdout.reconfigure(encoding="utf-8")`，否则中文按 cp936 输出直接乱码。
4. **配置里 command 用绝对路径**：GUI 启动的宿主 PATH 很窄，写 `python` 会 ENOENT。
5. **显式设 `cwd`**：stdio server 默认继承宿主工作目录，相对路径会读错地方。
6. **`env` 是替换不是追加**：需要 PATH 得显式传（这里没用到 env，所以无影响）。

---

## 已知限制

| 限制 | 说明 |
|---|---|
| `.doc/.ppt/.xls` 读不了 | 老二进制格式，需先另存为 x 版；工具会明确报错提示 |
| **扫描件 PDF 读不了** | 没有文本层。实测本机 `scanned.pdf` 就是这种，工具会诚实报错而非返回乱码 |
| **CID 字体 PDF 可能乱码** | 中文 PDF 若用 CID 编码，取出的不是 Unicode；无第三方库无法解决 |
| WSL 可能被沙箱挡 | 之前实测 `wsl -l -v` 返回 `WSL_E_ACCESS_DENIED`；MCP 进程若同样受限，`run_wsl` 会失败 |
| 无写入能力 | 本轮只做**只读**。生成/修改 docx/pptx 需要 python-docx 等库，本机装不上 |

---

## 回滚

配置块有明确注释标记，整块删除即可：

```yaml
# --- local MCP suite: docs / shell / git (added 2026-10-30; delete this block to roll back) ---
- insert:
    - id: mcp-docs
    ...
    - id: mcp-git
```

或直接还原备份：

```powershell
Copy-Item "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml.bak-20261030-1420" `
          "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml" -Force
```

还原后重启 DSH。

---

## 安全说明

`run_powershell` / `run_wsl` 是**真实的命令执行能力**，权限等同于你自己的用户账户。

内置防护：
- 破坏性模式（`format` / `diskpart` / `rm -rf /` / `shutdown` / `bcdedit` 等）默认**拒绝**，需显式 `force=true`；
- 每条命令写入 `logs/shell.log`，事后可审计。

**但这不等于沙箱。** 它拦不住 `Remove-Item D:\重要文件` 这类"合法但致命"的命令。
如果你不放心，把 `mcp-shell` 块注释掉即可，docs 和 git 不受影响。
