# 故障排查

---

## 工具不见了 / 调不到

**症状**：我调用 `docs` / `shell` / `git` 时报工具不存在。

**按顺序查**：

### 1. 配置里还在吗

```powershell
Select-String -Path "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml" `
              -Pattern '^\s+- id: mcp-'
```

应该看到 4 行：`mcp-cua`、`mcp-docs`、`mcp-shell`、`mcp-git`。

### 2. 配置能解析吗

```powershell
& "D:\Anaconda\python.exe" -c "import yaml;d=yaml.safe_load(open(r'C:\Users\<user>\.dsh-beta\profiles\desktop\cordis.patch.yml',encoding='utf-8'));print('ok',len(d))"
```

输出 `ok 10` 才正常。报 `ScannerError` 说明 YAML 被改坏了——用备份还原：

```powershell
Copy-Item "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml.bak-20261030-1438" `
          "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml" -Force
```

### 3. 服务本身能起来吗

```powershell
$py  = "C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe"
$srv = "C:\Users\<user>\Documents\deepseek-harness\default-workspace\projects\mcp-suite\servers\server.py"

& $py $srv --profile docs  --selftest
& $py $srv --profile shell --selftest
& $py $srv --profile git   --selftest
```

三个都要 `SELFTEST PASSED`。

### 4. 重启

改完 `cordis.patch.yml` **必须重启 DSH Desktop**（关掉再开，刷新页面无效）。

---

## `wsl` 报 `WSL_E_ACCESSDENIED`

**不是 WSL 坏了**，是进程完整性级别不够。

`pwsh` 工具跑在 **Low IL**，`shell` MCP 跑在 **Medium IL**。WSL 的 LxssManager
要求 Medium 及以上。

**验证**：

```powershell
whoami /groups | Select-String 'Mandatory Label'
```

- `Low Mandatory Level` → WSL 会被拒
- `Medium Mandatory Level` → 正常

**解决**：让我改走 `shell` MCP 执行，不要用 `pwsh` 工具。

---

## PDF 读不出内容

**症状**：`no extractable text layer in ...`

**原因**：PDF 是扫描件或图片型，没有文本层。这不是 bug，是格式限制。

**怎么判断**：

- 用 PDF 阅读器打开，**能不能选中文字**
- 能选中 → 有文本层，应该能读
- 选不中 → 图片型，只能 OCR

**替代方案**：用 OCR 工具（你装了 Tesseract-OCR）。

---

## 中文 PDF 读出乱码

**原因**：PDF 用了 CID 编码的自定义字体映射，文本层里存的不是 Unicode。

**现状**：无第三方库（pypdf/pdfminer）无法正确还原。本机 pip 装不了包。

**变通**：截图后 OCR，或直接从源头要原始文档。

---

## `.doc` / `.ppt` / `.xls` 读不了

**原因**：旧二进制格式（OLE 复合文档），不是 ZIP+XML。

**解决**：用 Office 打开，另存为 `.docx` / `.pptx` / `.xlsx`，再读新的。

---

## `shell` 命令被拒绝

**症状**：`refused: command matches destructive pattern /.../`

**原因**：命中了破坏性拦截（`format` / `diskpart` / `shutdown` / `bcdedit` 等）。

**解决**：确认确实要执行，传 `force=true`。**用了就没有保护。**

---

## `shell` 命令超时

**症状**：`powershell timed out after 60s`

**解决**：传更大的 `timeout_sec`（最大 600）。

```json
{ "command": "...", "timeout_sec": 300 }
```

---

## 中文输出乱码

**现象**：返回的 stdout 是一堆 `锟斤拷` 或 `����`。

**已处理**：`run_powershell` 内部强制 UTF-8，`wsl` 做了 UTF-16LE 探测。

**如果还乱码**：多半是命令本身输出的编码问题（比如某个老程序的 GBK 输出）。
可以在命令里显式转码：

```powershell
[Console]::OutputEncoding = [Text.Encoding]::UTF8
```

---

## 想临时关掉某个 MCP

编辑 `cordis.patch.yml`，把对应块注释掉：

```yaml
#    - id: mcp-shell
#      name: '@deepseek-ai/dsh-mcp-client'
#      config:
#        serverName: shell
#        ...
```

重启后生效。其他 MCP 不受影响。

**建议**：长期不用 `shell` 就关掉它，减少误操作面。

---

## 完全回滚

```powershell
# 回到「只有 cua，没有 docs/shell/git」的状态
Copy-Item "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml.bak-20261030-1420" `
          "$env:USERPROFILE\.dsh-beta\profiles\desktop\cordis.patch.yml" -Force
```

重启 DSH。

| 备份 | 状态 |
|---|---|
| `.bak-20261030-1420` | 加 MCP 之前（13443 B） |
| `.bak-20261030-1438` | 加 MCP 之后、改上限之前（14978 B） |

---

## 想看命令审计

```powershell
Get-Content projects\mcp-suite\logs\shell.log -Tail 50
```

---

## 跑回归测试

改了 `servers\` 下任何 `.py` 之后：

```powershell
& "C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe" `
   "projects\mcp-suite\tests\bug_hunt.py"
```

预期 `50 passed, 0 failed`。

**注意**：测试里的 WSL 用例在当前环境下可能被跳过或报错，
因为测试进程继承 `pwsh` 的 Low IL——这是环境限制，不是代码缺陷。

---

## 改了代码不生效

MCP server 是**每次调用新起的进程**，但 DSH 会缓存工具列表。

**改完 `.py` 必须重启 DSH**，否则跑的仍是旧代码。

验证是否加载了新版：

```powershell
& $py $srv --profile docs --list-tools
```

看输出是否包含你新加的工具名。
