# Agent Guide for Code Optimizer

本文档面向 AI Coding Agent，帮助其快速理解本项目结构、技术栈、开发规范与安全注意事项。

## Project Overview

本项目是一个**代码优化器（Code Optimizer）**，用于批量提取 C 代码库中指定打印函数（如 `osal_printk`、`printk`、`printf`）的字符串字面量参数，经 AI 优化后再安全地写回源码。核心目标是**缩减固件/镜像中的日志字符串体积**。

关键特性：
- **零依赖**：仅使用 Python 3 标准库，无第三方包
- **安全写回**：应用替换前验证偏移位置，使用原子写入（`.tmp` + `os.replace`）
- **分批处理**：支持大型代码库（1000+ 项）分批获取与处理
- **浏览器审查**：生成自包含静态 HTML 页面，支持在线编辑、跳过、导出 `replacements.json`

## Technology Stack

- **语言**：Python 3（已在 3.12 验证，理论上兼容 3.8+）
- **依赖**：零第三方依赖，仅用标准库（`argparse`, `json`, `os`, `re`, `fnmatch`, `pathlib`, `datetime`, `sys`, `html`, `typing`）
- **目标源码语言**：C / C++（通过正则匹配 `"..."` 字符串字面量）
- **构建系统**：无。直接运行脚本即可，无需 `pyproject.toml`、`setup.py` 或 `Makefile`

## Directory Structure

```
.
├── AGENTS.md                 # 本文件（面向 AI Agent 的项目指南）
├── README.md                 # 面向人类用户的快速开始与命令速查
├── SKILL.md                  # Kimi Skill 定义，包含触发条件与执行步骤
├── replacements.json         # 当前已导入的替换记录（工作文件）
├── scripts/
│   ├── codebase.py           # 核心：提取、获取批次、标记完成、状态、应用替换
│   ├── replacements.py       # 替换管理：导入、增删查、应用回源码
│   └── review.py             # 审查工具：生成静态 HTML 供人工审查
├── references/
│   ├── data-formats.md       # config.json / extracted.json / replacements.json 字段说明
│   └── advanced-usage.md     # 大型代码库调优、完整 CLI 参考
└── test/
    ├── config.json           # 测试用配置示例
    ├── extracted.json        # 测试用提取结果（大规模真实数据，约 1257 项）
    ├── batch-replacements.json  # 测试用批量替换输入
    ├── replacements.json     # 测试用替换记录
    ├── review.html           # 测试用生成的审查页面
    └── ...                   # 其他中间/测试数据文件
```

## Key Modules and Responsibilities

### `scripts/codebase.py`

核心引擎，提供以下子命令：

| 子命令 | 作用 |
|--------|------|
| `analyze` | 读取 `config.json`，扫描源码路径，提取目标函数字符串字面量，输出 `extracted.json` |
| `get` | 从 `extracted.json` 中读取待处理项，按批次返回。默认纯文本输出；加 `--json` 返回完整 JSON。支持 `--group-by-file` 按文件分组 |
| `mark-done` | 手动将指定 ID 或 batch-id 的项标记为 `completed` |
| `status` | 显示进度统计。`--strict` 会在有未完成项时返回非零退出码 |
| `apply` | （内含于 codebase.py，但通常由 replacements.py 调用）直接将替换写回源码并更新 extracted.json |

主要正则：
- `STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"')` —— 匹配 C 风格双引号字符串字面量
- `func_pattern = re.compile(rf"\b{re.escape(func_name)}\s*\(")` —— 匹配目标函数调用

### `scripts/replacements.py`

替换管理器，提供 CRUD 与应用：

| 子命令 | 作用 |
|--------|------|
| `import` | 从 AI 生成的 JSON 导入替换。支持**紧凑数组格式** `["call-001", "\"str\""]` 和传统对象格式 |
| `add` / `remove` / `clear` / `list` | 单条增删、清空、列表 |
| `apply` | 将 `replacements.json` 中的替换应用到源码。按偏移量**降序**处理，防止位置漂移；验证原文匹配；原子写入；更新 `extracted.json` 状态 |

默认工作文件为当前目录下的 `replacements.json`。

### `scripts/review.py`

生成**完全自包含**的静态 HTML 审查页面（无服务器依赖）。功能包括：
- 原始字符串与 AI 替换的并排对比
- 行内编辑替换内容
- 勾选/跳过单项或批量操作
- 搜索过滤（按文件、ID、字符串内容）
- 导出 `replacements.json`（下载或复制到剪贴板）
- 使用 `localStorage` 自动保存编辑状态，刷新不丢失

## Data Flow and Workflow

标准工作流如下（Agent 操作时必须严格按此顺序）：

1. **配置**：创建 `config.json`，指定 `targetFunctions`、`filePatterns`、`excludePatterns`、`paths`
2. **提取**：`python scripts/codebase.py analyze --config config.json --output extracted.json`
3. **获取批次**：`python scripts/codebase.py get --input extracted.json --batch 30`
4. **生成替换**：AI 根据批次内容生成 `batch-replacements.json`
5. **（可选）审查**：`python scripts/review.py --input extracted.json --output review.html`，浏览器中编辑后导出
6. **导入**：`python scripts/replacements.py import --file batch-replacements.json`
7. **应用**：`python scripts/replacements.py apply --input extracted.json`
8. **检查**：`python scripts/codebase.py status --input extracted.json`，确认 `pending=0`

## Build and Test Commands

本项目**无构建步骤**，直接运行脚本即可。

### 运行脚本

```bash
# 提取
python scripts/codebase.py analyze --config test/config.json --output test/extracted.json

# 获取批次（纯文本）
python scripts/codebase.py get --input test/extracted.json --batch 30

# 获取批次（JSON，完整字段）
python scripts/codebase.py get --input test/extracted.json --batch 30 --json --format full

# 导入并应用
python scripts/replacements.py import --file test/batch-replacements.json
python scripts/replacements.py apply --input test/extracted.json

# 状态检查
python scripts/codebase.py status --input test/extracted.json

# 生成审查页面
python scripts/review.py --input test/extracted.json --output test/review.html
```

### 测试

- **无自动化单元测试框架**（无 `pytest`、`unittest` 等）。
- `test/` 目录仅包含**测试数据/固定装置（fixtures）**，用于手动验证脚本行为。
- 修改代码后，建议使用 `test/` 中的数据做端到端验证：
  1. 用 `test/config.json` 运行 `analyze`
  2. 用 `test/extracted.json` 运行 `get`
  3. 用 `test/batch-replacements.json` 运行 `import` + `apply`
  4. 检查 `status` 输出是否符合预期

## Code Style Guidelines

- **类型注解**：函数参数和返回值使用 `typing` 注解（如 `List[Dict[str, Any]]`）
- **文档字符串**：模块和函数顶部使用双引号 docstring 说明用途
- **常量**：模块级正则和常量使用 `UPPER_SNAKE_CASE`
- **函数命名**：使用 `snake_case`
- **命令函数**：以 `cmd_` 前缀命名子命令处理函数（如 `cmd_analyze`）
- **JSON 读写**：统一使用 `utf-8` 编码；写文件时先写 `.tmp` 再用 `os.replace` 原子替换
- **错误处理**：对文件不存在、编码错误、偏移不匹配等情况打印 `Warning` 到 `stderr`，尽量不中断整体流程
- **字符串格式化**：代码中未使用 f-string 的复杂场景较少，以标准字符串操作为主

## Security Considerations

1. **源码修改前验证**：`apply` 命令在替换前会验证 `content[start:end] == original`，若偏移量因源码变更而失效则跳过该项并告警。
2. **原子写入**：所有文件写操作均为原子写入（先写 `.tmp` 文件，再 `os.replace`），避免写一半崩溃导致源码损坏。
3. **路径解析**：`apply` 时先尝试相对路径解析；若失败，会回退到 `gitRepo` 根目录拼接路径。
4. **Git 仓库依赖**：`extracted.json` 中的 `filePath` 是相对于运行 `analyze` 时的 CWD 的；`gitRepo` 字段用于 `apply` 时的路径回退。因此目标代码库必须是 Git 仓库（或显式指定 `gitRepo`）。
5. **replacements.json 保留**：`apply` 成功后**不会自动清空** `replacements.json`，保留以供审计和复查。如需清理，手动执行 `python scripts/replacements.py clear`。
6. **二进制/大文件过滤**：`analyze` 会自动跳过二进制文件（检测 `\x00`）和超过 1 MiB 的文件。

## Development Conventions

- **语言**：项目文档（README、SKILL.md、references/）主要使用**中文**；代码注释和 docstring 使用**英文**。
- **版本标记**：所有 JSON 输出文件均包含 `"version": "1.0"`。
- **ID 生成**：`analyze` 为每个提取项分配 `call-NNN` 格式 ID，从 `001` 开始顺序编号。
- **时间戳**：使用 `datetime.now().isoformat()` 生成 ISO 8601 格式时间戳。
- **批次标识**：`get` 命令为每次获取的项分配 `batch-{timestamp}` 作为 `batchId`。
- **状态机**：每个提取项的 `status` 只能是 `pending` 或 `completed`。

## Common Pitfalls for Agents

- **不要假设有包管理器**：没有 `requirements.txt` 或 `pip install` 步骤，不要尝试安装依赖。
- **不要修改 test/ 中的大文件除非必要**：`test/extracted.json` 等文件体积较大（>1 MB），仅用于验证，一般不应纳入版本控制修改。
- **路径问题**：`apply` 必须在 `extracted.json` 所在目录运行，或确保其中的 `filePath` 能被正确解析。若源码已被其他修改改变，必须重新运行 `analyze` 刷新偏移量。
- **替换字符串必须带引号**：`replacement` 字段必须是完整的带引号字符串字面量，如 `"optimized\n"`，而非裸文本。
- **保留格式说明符**：AI 生成替换时必须保留 `%d`、`%s`、`%x`、`%02x` 等格式说明符以及 `\n`、`\r\n`、`\t` 等转义序列。
