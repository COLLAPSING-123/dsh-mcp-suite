# `git` —— 查看 Git 仓库

**服务名**：`git`　**工具数**：6　**只读**

设计上就是只读的：没有任何工具能 commit、push、建分支、改文件。
连 `git_run` 也只放行白名单子命令。

---

## `git_status`

**作用**：当前分支 + 未跟踪/已修改文件。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `repo` | string | 是 | 仓库根目录 |

**示例**

> my-project 现在有什么没提交的

**输出**

```
## main...origin/main
?? docs/report.pdf
?? build/
```

`??` = 未跟踪，` M` = 已修改，`A ` = 已暂存。

---

## `git_log`

**作用**：提交历史。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `repo` | string | 是 | 仓库根目录 |
| `max_count` | int | 否 | 1–200，默认 20 |
| `path` | string | 否 | 只看这个路径的历史 |

**示例**

> my-project 最近 5 次提交

**输出**

```
9d8659d 2025-08-30 alice fix login bug
a9db26c 2025-08-17 alice add API docs
c27bc0b 2025-08-10 alice update CI config
```

格式：`短hash 日期 作者 提交说明`

**注意**：`max_count` 传非数字会退回默认 20，不报错。

---

## `git_diff`

**作用**：工作区或暂存区的差异。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `repo` | string | 是 | 仓库根目录 |
| `staged` | boolean | 否 | 看暂存区（`git diff --staged`） |
| `path` | string | 否 | 只看这个路径 |
| `context` | int | 否 | 上下文行数，0–20，默认 3 |

**示例**

> 我现在改了哪些地方

**注意**：没有差异时返回 `(no differences in the working tree)`，
不是 `(no output)`——后者容易被误判成失败。

---

## `git_show`

**作用**：某个提交的完整内容 + 补丁。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `repo` | string | 是 | 仓库根目录 |
| `rev` | string | 否 | 修订号，默认 `HEAD` |

**示例**

> my-project 最新那次提交改了啥

**输出**：commit 信息 + 文件变更统计 + 完整 diff。二进制文件显示
`Binary files /dev/null and ... differ`，不会尝试当文本解析。

**注意**：`rev` 不存在会报 `git show ... failed (exit 128)`，不是崩溃。

---

## `git_branches`

**作用**：所有本地和远程分支及跟踪关系。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `repo` | string | 是 | 仓库根目录 |

**示例**

> 这个仓库有哪些分支

**输出**

```
* main                9d8659d [origin/main] fix login bug
  remotes/origin/HEAD -> origin/main
  remotes/origin/main 9d8659d fix login bug
```

---

## `git_run`

**作用**：跑白名单内的只读 git 子命令，覆盖上面 5 个工具没包的情况。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `repo` | string | 是 | 仓库根目录 |
| `subcommand` | string | 是 | 见下方白名单 |
| `args` | string[] | 否 | 额外参数，原样传递 |

**白名单**：`status` `log` `diff` `show` `branch` `remote` `tag` `rev-parse` `describe` `shortlog` `blame` `ls-files` `stash`

**额外拦截**（即使子命令在白名单里）：

- `push`、`reset --hard`、`clean -f`、`checkout --`、`rebase`、`filter-branch`、`gc --prune`
- `branch -D` / `-d` / `--delete`
- `tag -d` / `--delete`
- `update-ref -d`、`reflog expire`、`prune`

**示例**

> 这个文件每一行是谁写的

→ `subcommand="blame"`, `args=["README.md"]`

> 这个仓库的远程地址

→ `subcommand="remote"`, `args=["-v"]`

**注意**：`subcommand` 不在白名单直接拒绝，报错会列出所有允许的。

---

## 典型用法组合

| 场景 | 怎么问 |
|---|---|
| 看提交历史 | 「my-project 最近提交」 |
| 看某次提交细节 | 「fix login bug那次改了哪些文件」 |
| 找某文件的改动历史 | 「README.md 的修改记录」 |
| 看有没有未提交 | 「我现在有什么没提交」 |
| 看分支 | 「有哪些分支」 |
| 查某行作者 | 「这个文件第 20 行是谁写的」 |
| 查远程 | 「远程仓库地址是什么」 |

---

## 边界：它不能做什么

| 不能做 | 替代方案 |
|---|---|
| commit | 你自己在终端执行，或用 `shell.run_powershell` |
| push | 同上 |
| 建/删分支 | 同上（`branch -D` 被明确拦截） |
| 改工作区文件 | 同上 |

**为什么这么设计**：Git 的破坏性操作后果不可逆（`reset --hard` 会丢工作区改动），
而查看历史的需求远多于修改需求。要改的时候，用 `shell` 让你明确知道自己在做什么。

---

## 常见报错

| 报错 | 原因 | 解决 |
|---|---|---|
| `not a directory: Z:\nope` | 路径不存在 | 检查路径 |
| `not a git repository (no .git)` | 不是仓库根目录 | 指到含 `.git` 的目录 |
| `subcommand 'push' not allowed` | 不在白名单 | 用 `shell` 执行 |
| `git show ... failed (exit 128)` | 修订号不存在 | 用 `git_log` 查真实 hash |
