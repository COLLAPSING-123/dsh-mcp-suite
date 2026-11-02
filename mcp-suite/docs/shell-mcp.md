# `shell` —— 执行 PowerShell 与 WSL 命令

**服务名**：`shell`　**工具数**：4　**⚠️ 其中 2 个可写，能改你的系统**

这是四个 MCP 里**能力最强、风险最高**的一个。它不是"建议"，是真在你的机器上跑命令。

---

## 安全机制（先读）

1. **破坏性模式拦截**：命中以下模式的命令默认**拒绝执行**
   - `format X:`、`diskpart`、`bcdedit`、`vssadmin delete`、`cipher /w`
   - `Remove-Item ... -Recurse ... C:\`
   - `rm -rf /`、`mkfs`、`dd of=/dev/`
   - `shutdown`、`Restart-Computer`、`Stop-Computer`
2. **绕过方式**：显式传 `force=true`。**用了就没有这层保护。**
3. **全量审计**：每条命令写入 `projects\mcp-suite\logs\shell.log`

**拦不住什么**：`Remove-Item D:\重要文件`、`git clean -fdx` 这类"合法但致命"的命令。
它只防手滑，不防意图。

---

## `run_powershell`

**作用**：执行 PowerShell 5.1 命令，返回退出码 + stdout + stderr。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `command` | string | 是 | PowerShell 命令文本 |
| `cwd` | string | 否 | 工作目录，不存在会报错 |
| `timeout_sec` | int | 否 | 超时秒数，1–600，默认 60 |
| `force` | boolean | 否 | 绕过破坏性拦截 |

**示例**

> 看看 D 盘还剩多少空间

> 列出我所有的 git 仓库

> 查一下 python 进程占了多少内存

**输出格式**

```
exit_code: 0

stdout:
<标准输出>

stderr:
<标准错误，为空时不显示>
```

**注意**

- 内部已强制 UTF-8，中文输出不会乱码
- 超时会中断并报错，不会挂死
- `cwd` 不传时用 MCP 进程的工作目录（`projects\mcp-suite`）
- 退出码非 0 **不会**报错，只是 `exit_code` 是别的数字——判断成功要看它

---

## `run_wsl`

**作用**：在 WSL 里执行 bash 命令。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `command` | string | 是 | bash 命令文本 |
| `distro` | string | 否 | 发行版名，不传用默认 |
| `timeout_sec` | int | 否 | 超时秒数，1–600 |
| `force` | boolean | 否 | 绕过破坏性拦截 |

**示例**

> 在 Ubuntu 里看看内核版本

> 用 WSL 跑一下这个 python 脚本

**注意**

- 你本机是 `Ubuntu-20.04`（Python 3.8.10）
- `wsl.exe` 的诊断信息是 UTF-16LE，已做编码探测
- **WSL 自身失败**（发行版不存在、服务被禁）会报错，不会伪装成 `exit_code: 4294967295`
- 如果 WSL 整体不可用，错误信息里会带 `WSL_E_*`

---

## `wsl_distros`

**作用**：列出 WSL 发行版及运行状态。

**参数**：无

**示例**

> 我有几个 WSL 发行版

**输出**

```
NAME              STATE           VERSION
* Ubuntu-20.04      Running         2
  docker-desktop    Stopped         2
```

**注意**：`*` 表示默认发行版。WSL 不可用时会报错而不是返回空表。

---

## `powershell_info`

**作用**：查 PowerShell 版本、OS 版本、执行策略。

**参数**：无

**示例**

> 我这台机器的 PowerShell 什么版本

**输出**

```
exit_code: 0

stdout:
5.1.26100.9444
Microsoft Windows NT 10.0.26200.0
Undefined
```

**注意**：第三行是 `CurrentUser` 作用域的执行策略，`Undefined` 是正常的（表示没单独设过）。

---

## 典型用法组合

| 场景 | 怎么问 |
|---|---|
| 查磁盘空间 | 「C 盘和 D 盘各剩多少」 |
| 找大文件 | 「D 盘超过 1G 的文件列出来」 |
| 查进程 | 「哪个进程占内存最多」 |
| 查服务 | 「MySQL 服务在跑吗」 |
| 批量改名 | 「把 D:\tmp 下的 .txt 都加个前缀」 |
| Linux 侧操作 | 「在 WSL 里看看 /mnt/c 挂载」 |
| 跑脚本 | 「用 python 跑一下这个文件」 |

---

## 一个必须知道的坑

**`pwsh` 工具（我平时用的那个）和这个 MCP 不是一回事。**

| | `pwsh` 工具 | `shell` MCP |
|---|---|---|
| 完整性级别 | **Low**（沙箱降权） | **Medium**（正常） |
| WSL | ❌ 被拒 | ✅ 正常 |
| 写工作区外文件 | ❌ 被拒 | ✅ 允许 |
| 注册表写入 | ❌ 被拒 | ✅ 允许 |

所以：**如果某命令在 `pwsh` 里失败，不代表机器做不到**，让我改走 `shell` MCP 再试一次。

---

## 关掉它

不需要命令执行时，编辑 `cordis.patch.yml`：

```yaml
    - id: mcp-shell
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: shell
        # ... 把这一整块注释掉或删掉
```

重启 DSH 后生效，`docs` 和 `git` 不受影响。

---

## 审计日志怎么看

```powershell
Get-Content projects\mcp-suite\logs\shell.log -Tail 30
```

每条记录格式：

```
[2026-10-30T14:23:26] ps Get-Date -Format 'yyyy-MM-dd'
    -> exit=0
```

`ps` = PowerShell，`wsl` = WSL，`->` 后面是退出码或超时标记。
