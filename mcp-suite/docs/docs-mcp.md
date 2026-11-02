# `docs` —— 文件内容读取

**服务名**：`docs`　**工具数**：4　**全部只读**

用来把 Word / PowerPoint / Excel / PDF / Markdown 变成我能读的纯文本。

底层不依赖 python-docx 等库（本机装不上），而是直接解析 OOXML（docx/pptx/xlsx 本质是 ZIP+XML）。

---

## `read_document`

**作用**：提取任意受支持文件的正文，返回带标题层级的纯文本。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | 是 | 文件路径，绝对路径最稳 |
| `max_chars` | int | 否 | 截断长度，默认 200000，最小 1000 |

**支持格式**：`.docx` `.pptx` `.xlsx` `.xlsm` `.pdf` `.md` `.markdown` `.txt` `.csv` `.json` `.log`

**示例**

> 把 `C:\Users\<user>\Documents\report.docx` 读出来

**输出长什么样**

Word 的标题会变成 `# 一、实验目的`，表格变成 `| 学号 | 姓名 |`；PPT 按 `## Slide 1` 分页，备注用 `> 备注：` 标出。

**注意**

- 只读，不能生成或修改文件
- `.doc` `.ppt` `.xls` 是旧二进制格式，**读不了**，需先在 Office 里另存为 x 版
- **扫描件 PDF 没有文本层**，会明确报错，不会返回乱码
- 中文 PDF 若用 CID 编码字体，提取结果可能是乱码（无第三方库无法解决）

---

## `read_markdown`

**作用**：读 Markdown 原文，或只返回标题树。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | 是 | 文件路径 |
| `outline_only` | boolean | 否 | 只返回标题层级，默认 false |
| `max_chars` | int | 否 | 截断长度，默认 200000 |

**示例**

> 看看 `projects\mcp-suite\README.md` 的目录结构

→ 用 `outline_only=true`，返回：

```
- mcp-suite · 本机零依赖 MCP 服务器
  - 为什么是自研的
  - 目录
  - 怎么用
```

**注意**

- 代码块里的 `#` 不会被当成标题（已处理围栏）
- 文件编码自动探测：UTF-8 BOM → UTF-8 → GB18030

---

## `document_info`

**作用**：只看文件类型、大小、修改时间，**不读正文**。文件很大时用这个先探路。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `path` | string | 是 | 文件路径 |

**示例**

> 这个 docx 多大、什么时候改的

**输出**

```json
{
  "path": "C:\\Users\\<user>\\Documents\\report.docx",
  "extension": ".docx",
  "kind": "word",
  "size_bytes": 18054,
  "modified": "2026-10-08T10:30:21",
  "supported": true
}
```

**注意**：`supported: false` 表示格式不支持，别再调 `read_document`。

---

## `supported_formats`

**作用**：列出当前能读的扩展名。不确定某个文件能不能读时先问它。

**参数**：无

**示例**

> 你能读哪些格式

**注意**：返回里会区分「可读」和「旧格式需另存」。

---

## 典型用法组合

| 场景 | 怎么问 |
|---|---|
| 读作业要求 | 「把桌面那个 docx 要求列成清单」 |
| 看课件讲了什么 | 「这个 pptx 每页讲什么」 |
| 查名单 | 「这个 xlsx 有多少行，前 10 行给我」 |
| 找文档结构 | 「这个 md 的目录结构」 |
| 确认文件是什么 | 「这个文件是什么格式、多大」 |
| 读代码/日志 | 「把这份 .log 里 ERROR 行挑出来」 |

---

## 限制汇总

| 限制 | 说明 |
|---|---|
| 只读 | 无写入能力 |
| 旧格式 | `.doc` `.ppt` `.xls` 需另存 |
| 扫描 PDF | 无文本层，读不了 |
| CID 字体 PDF | 可能乱码 |
| 单文件上限 | 80 MB |
| 输出上限 | 默认 200000 字符，可用 `max_chars` 调 |
