# DSH 桌面控制 + 本机 MCP 套件 · 部署手册

> 目标读者：**另一台机器上的 AI 助手**（或按步骤操作的人）。
> 读完照做即可得到一个「能截屏、能点鼠标、能打字」的 `cua` 服务，外加
> `docs / shell / git` 三个只读或受控的本机 MCP 服务。
> 每一步都给了**验证方法**和**失败时看哪里**，别跳步。

---

## 0. 包里有什么

```
dsh-mcp-suite-<date>.zip
├── DEPLOY.md                       ← 本文件
├── install/
│   └── patch-snippet.yml           ← 直接可用的 DSH 配置模板（含 4 个 server）
├── windows_local_ai_agent/         ← 桌面控制项目（cua）
│   ├── agent/mcp_server.py         ← 11 个桌面工具（零第三方 SDK）
│   ├── agent/mcpcore.py            ← 手写 MCP stdio 协议层，无依赖
│   ├── agent/main.py               ← 另一套：自带 LLM 循环的旧版 agent（可选）
│   ├── scripts/mcp_probe.py        ← 不依赖 DSH 的协议自检脚本
│   ├── requirements.txt
│   └── .env.example                ← 只有旧版 agent/main.py 需要
└── mcp-suite/                      ← docs / shell / git 三个服务
    ├── servers/{server,mcpcore,docio,shellio,gitio}.py
    ├── docs/                       ← 每个工具的参数手册
    └── tests/{bug_hunt,verify_docs}.py
```

**不含**：`.venv`（体积）、`.env`（密钥）、`logs/`（运行时产物）。这些都要在新机器上重建。

---

## 1. 前置检查（先跑这三条，别急着解包）

```powershell
py -0p                     # 需要 3.11+，记下 3.13 的完整路径，后文叫 <BASE_PY>
Test-Path "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml"   # DSH 必须装好
whoami                     # 记下用户名，后文叫 <你>
```

任何一条不满足就先解决，后面的步骤全部依赖它们。

---

## 2. 解包到哪

建议：

| 内容 | 目标位置 |
|---|---|
| `windows_local_ai_agent/` | `C:\Users\<你>\Desktop\windows_local_ai_agent` |
| `mcp-suite/` | `C:\Users\<你>\Documents\deepseek-harness\default-workspace\projects\mcp-suite` |
| venv（下一步创建） | `C:\Users\<你>\.mcp\cua-venv` ← **必须在工作区外** |

---

## 3. ⚠️ 最关键的一条：venv 必须建在工作区外

Windows 的 UIPI 规定：**低完整性进程不能向中/高完整性窗口注入输入**。
DSH 会把「**位于会话工作区目录内的任何 exe**」降为 Low 完整性，而把工作区外的 exe 保持 Medium。

实测结论（同一份 Python，只换位置）：

| exe 位置 | 完整性 | `SetCursorPos` |
|---|---|---|
| `C:\...\Python313\python.exe` | Medium | 成功 |
| 复制到工作区内再跑 | **Low** | 返回 0（静默失败） |
| 工作区内的 `.venv\Scripts\python.exe` | **Low** | 返回 0 |

**症状**：截图一切正常（读屏走 GDI，不受限），但鼠标不动、键盘没反应——不报错、不崩溃。
如果你只测截图，会误判成"能用"。

所以：**cua 的 python 解释器放在工作区外**。

---

## 4. 建 venv 并安装（cua）

```powershell
$base = "C:\Users\<你>\.mcp\cua-venv"
& '<BASE_PY>' -m venv $base
& "$base\Scripts\python.exe" -m pip install --no-cache-dir pyautogui pillow pyperclip
```

只需要这三个包。**不需要 `mcp` SDK**（协议层已内置在 `agent/mcpcore.py`）。

> 如果公司/校园网拉包慢，先 `& "$base\Scripts\python.exe" -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`

---

## 5. 自检（不启动 DSH 就能验）

```powershell
cd C:\Users\<你>\Desktop\windows_local_ai_agent
& 'C:\Users\<你>\.mcp\cua-venv\Scripts\python.exe' -m agent.mcp_server --selftest
& 'C:\Users\<你>\.mcp\cua-venv\Scripts\python.exe' -m agent.mcp_server --list-tools
```

期望输出：

```
integrity: Medium
screen: Size(width=..., height=...)
screenshot: (..., ...)
cursor: Point(x=..., y=...) -> Point(x=40, y=60) OK      ← 必须是 OK
click / focus_window / hotkey / list_windows / move / press / screen_size / screenshot / scroll / type_text / wait  (共 11 个)
```

**只要看到 `integrity: Low` 或 `cursor: ... BLOCKED`，立刻停**，回到第 3 节检查 exe 位置。
`--selftest` 会真的把鼠标挪到 (40,60)，这是设计如此。

再用不依赖 DSH 的协议探针验一遍：

```powershell
& 'C:\Users\<你>\.mcp\cua-venv\Scripts\python.exe' scripts\mcp_probe.py
```

期望 `protocol: 2025-11-25`（或更新）、11 个工具、`screenshot: isError=False -> ['image(...)', 'text(...)']`。

---

## 6. mcp-suite 的自检（docs / shell / git）

它直接跑系统 Python，不需要额外装包：

```powershell
$srv = 'C:\Users\<你>\Documents\deepseek-harness\default-workspace\projects\mcp-suite\servers\server.py'
& '<BASE_PY>' $srv --profile docs  --selftest
& '<BASE_PY>' $srv --profile shell --selftest
& '<BASE_PY>' $srv --profile git   --selftest
```

三个都要 `SELFTEST PASSED`。
回归测试（可选，50 用例）：`& '<BASE_PY>' mcp-suite\tests\bug_hunt.py`

---

## 7. 写入 DSH 配置

1. 备份：
   ```powershell
   $cfg = "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml"
   Copy-Item $cfg "$cfg.bak-$(Get-Date -Format yyyyMMdd-HHmm)"
   ```
2. 把 `install/patch-snippet.yml` 的**整块**追加到该文件末尾。
3. 替换 4 个占位符：
   - `<CUA_VENV>` → `C:\Users\<你>\.mcp\cua-venv`
   - `<PROJECT_DIR>` → `C:\Users\<你>\Desktop\windows_local_ai_agent`
   - `<SUITE_DIR>` → `...\projects\mcp-suite`
   - `<BASE_PY>` → 第 1 步记下的 3.13 `python.exe` 完整路径

**为什么一定要 `- insert:`**：这个文件是补丁层，带 `id` 的条目只能覆盖**已存在**的条目。
新插件不包 `insert` 的话，DSH 启动日志会打一行
`[W] patch: entry "mcp-cua" not found` 然后静默跳过——工具永远不出现，且没有别的报错。

4. 重启 **DSH Desktop**（托盘退出再打开，不是刷新页面）。

---

## 8. 验证工具真的挂上了

重启后，在对话里说「截个图看看」，或直接看工具列表里有没有 `mcp__cua__screenshot` 等 11 个。

命令行侧的证据（更可靠）：

```powershell
# 1) 服务进程在不在，且用的是工作区外的 exe
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*agent.mcp_server*' } |
  Select-Object ProcessId, ExecutablePath

# 2) 启动日志里的完整性级别
Get-Content .\logs\mcp-cua.log -Tail 3 -Encoding UTF8
#    期望：cua mcp server starting; integrity=Medium; confirm=chat
```

**真机动作验证**（避免"看着像成功"）：

```powershell
# 让 cua 把鼠标移到真实 (900,500)，然后用系统读数交叉验证
# 在 DSH 里调用 mcp__cua__move(900,500)，再执行：
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Cursor]::Position
# DPI 150% 的机器会显示 (600,333)，即 900/1.5 与 500/1.5 —— 这说明它真的动了
```

---

## 9. 故障对照表

| 现象 | 最可能原因 | 处理 |
|---|---|---|
| 工具根本不出现 | 配置没包 `insert:`，或重启的是页面不是程序 | 看 DSH 日志 `patch: entry ... not found`；按第 7 节改 |
| `integrity: Low` / 点不动 | python.exe 在工作区内 | 换到工作区外 venv（第 3 节） |
| `screenshot` 正常但 `click` 无效 | 同上；或目标窗口更高完整性（以管理员身份运行的窗口） | 用普通权限运行目标程序 |
| `ModuleNotFoundError: agent` | `cwd` 没设成项目目录 | 配置里补 `cwd` |
| `ModuleNotFoundError: pyautogui` | 装到了别的解释器 | 用 venv 里的 python 装，别用 `pip` 裸命令 |
| 中文变问号/乱码 | 控制台代码页不是 UTF-8 | 服务端已 `harden_stdio()`；命令行侧用 `chcp 65001` |
| 弹窗确认框卡满 180 秒 | `CUA_CONFIRM=dialog` 且窗口被遮挡 | 改 `chat` |
| shell 工具报 `WSL_E_ACCESS_DENIED` | WSL 子系统本身拒绝访问 | 与 MCP 无关，先修 WSL |
| 端口/路径含空格出错 | 引号丢了 | YAML 里路径一律单引号 |

---

## 10. 安全边界（务必读）

- `cua` 能**真的**移动鼠标、点击、键入。`CUA_CONFIRM=chat` 模式下的确认**依赖模型自觉**——
  它只是把"动手前说明"写进了工具描述，不是系统级强制。想硬约束就把 `CUA_CONFIRM` 改回 `dialog`，
  但低完整性下弹窗可能抢不到前台，会卡超时。
- `shell` 服务等价于**你自己的账户权限**。内置破坏性模式拦截（format/diskpart/shutdown/bcdedit 等）
  和全量审计日志（`mcp-suite\logs\shell.log`），但**不等于沙箱**：`Remove-Item D:\重要数据` 拦不住。
- 截图内容会经 DSH 发给模型服务商。锁屏/远程会话下截图可能失败。
- 不需要 `shell` 就把它从配置里删掉，docs/git 不受影响。

---

## 11. 回滚

```powershell
$cfg = "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml"
Copy-Item "$cfg.bak-<时间戳>" $cfg -Force   # 或直接删掉 insert 块
```
然后重启 DSH。删除 `C:\Users\<你>\.mcp\cua-venv` 即可彻底清除。

---

## 12. 交付物清单（本机已验证的状态，供对照）

| 项 | 本机实测值 |
|---|---|
| 协议版本 | 2025-11-25 / 2026-07-28 均可协商 |
| cua 工具数 | 9 |
| 完整性 | Medium（工作区外 venv） |
| 依赖 | pyautogui / pillow / pyperclip（无 mcp SDK） |
| 分辨率换算 | 真实 2560×1600 → 截图 1600×1000，比例 1.6，服务端自动回缩 |
| 端到端 | 截屏 → 定位 → 点击/输入 真机通过 |
