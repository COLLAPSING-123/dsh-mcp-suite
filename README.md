# DSH MCP Suite · Windows 桌面控制 + 本机工具链

给 **DeepSeek Harness（DSH）** 用的本机 MCP 服务集合：一个能真正操控 Windows 桌面的
`cua` 服务，外加 `docs / shell / git` 三个只读或受控的本机服务。

> 部署步骤看 **[DEPLOY.md](DEPLOY.md)**，里面写清了每个坑和验证方法。

---

## 目录

| 目录 | 内容 |
|---|---|
| [`windows_local_ai_agent/`](windows_local_ai_agent/) | `cua` 服务：11 个桌面工具（截屏含单窗口/移动/点击/输入/按键/滚动/等待/列窗口/切前台） |
| [`mcp-suite/`](mcp-suite/) | `docs`（读 docx/pptx/xlsx/pdf）、`shell`（PowerShell/WSL 执行）、`git`（只读查询） |
| [`install/patch-snippet.yml`](install/patch-snippet.yml) | DSH 配置模板，替换占位符即可用 |

## 特点

- **零第三方 MCP SDK**：协议层 [`agent/mcpcore.py`](windows_local_ai_agent/agent/mcpcore.py) 手写，
  `cua` 只依赖 `pyautogui / pillow / pyperclip`；`mcp-suite` 完全用标准库。
- **窗口级操作**：`list_windows` / `focus_window` / `screenshot(window=…)`，单窗口截图走 PrintWindow，能拍 GPU 加速窗口（GDI 对这类窗口全黑）。
- **输入不污染剪贴板**：默认用 Unicode 键盘事件逐字输入；`method=paste` 才走剪贴板，且会保存→校验→恢复。
- **坐标自动换算**：截图缩放到最长边 1600，模型报图片坐标，服务端换算回真实分辨率。
- **可自检**：`--selftest` 会检查完整性级别、截图、光标控制；`--list-tools` 列出工具。
- **审计**：桌面动作写 `logs/mcp-cua.log`，shell 命令写 `mcp-suite/logs/shell.log`。

## 一个必须知道的限制

Windows 的 UIPI 规定低完整性进程不能向高完整性窗口注入输入。
**DSH 会把位于会话工作区目录内的任何 exe 降为 Low 完整性**，所以 `cua` 的解释器
必须放在工作区外（`C:\Users\<你>\.mcp\cua-venv`）。

症状很隐蔽：截图正常、但不报错地点击无效。详见 [DEPLOY.md 第 3 节](DEPLOY.md#3-️最关键的一条venv-必须建在工作区外)。

## 安全

- `cua` 会真实操作鼠标键盘；`CUA_CONFIRM=chat` 模式下的确认依赖模型自觉，不是系统级强制。
- `shell` 服务权限等价于当前用户账户，内置破坏性命令拦截 + 审计日志，但**不是沙箱**。
- 仓库不含任何密钥、`.env`、虚拟环境。

## 许可

未声明许可证。使用前请与仓库所有者确认。
