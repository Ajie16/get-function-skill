---
name: code-optimizer
description: |
  批量提取代码库中指定打印函数（如 osal_printk、printk、printf）的字符串字面量参数，
  生成精简替换后安全写回源码。仅需 Python 3 标准库，零第三方依赖。
  触发场景：优化日志字符串、精简打印输出、批量重构字符串字面量、
  提取并替换打印函数参数、代码库级字符串优化、缩短 printk/osal_printk 字符串、
  减少固件镜像中的日志体积、优化调试输出。
---

# 代码优化器（Code Optimizer）

## 1. 何时调用此 Skill

当用户提出以下任何请求时，必须调用此 Skill：

- "优化/精简/缩短 `osal_printk`/`printk`/`printf` 的字符串"
- "批量重构/替换代码库中的字符串字面量"
- "提取打印函数的字符串参数并优化"
- "减少固件/镜像中的日志字符串体积"
- "优化调试输出/日志信息"
- 任何涉及批量修改源码中打印函数字符串的请求

## 2. 前置条件

- 目标代码库必须是 **Git 仓库**（`extracted.json` 依赖 `gitRepo` 路径解析）
- 已安装 **Python 3**（仅标准库，无第三方依赖）


## 3. 执行步骤（严格按顺序）

### 步骤 1：准备配置文件

**必须询问用户**（如果未明确指定）：
1. 目标打印函数名（如 `osal_printk`、`printk`、`printf`）
2. 源码根目录或路径列表
3. 需要排除的目录/文件模式（如 `test/`、`vendor/`）

**创建 `config.json`**：
```json
{
  "targetFunctions": ["osal_printk"],
  "filePatterns": ["*.c", "*.h"],
  "excludePatterns": ["**/test/**", "**/vendor/**"],
  "paths": ["/absolute/path/to/source"]
}
```

> 格式详情参见 [references/data-formats.md](references/data-formats.md)。

### 步骤 2：提取字符串字面量

```bash
python scripts/codebase.py analyze \
  --config config.json --output extracted.json
```

**预期输出**：
```
Analysis complete. Extracted 64 string literals. Saved to extracted.json
```

**如果输出为 0**：检查 `targetFunctions` 是否拼写正确，或 `filePatterns` 是否覆盖了目标文件。

### 步骤 3：获取待替换项

```bash
python scripts/codebase.py get \
  --input extracted.json --batch 30
```

**输出说明**：
- 默认返回 JSON 格式的 `items` 数组，每个项只包含 `id` 和 `stringLiteral`
- 当返回 `"remaining": 0` 时，表示全部处理完毕，跳到步骤 5
- **大型代码库**（>1000 项）：添加 `--group-by-file` 以减少输出体积；如需完整字段可指定 `--format full`

### 步骤 4：生成替换内容

根据抓取到的 `stringLiteral` 和上下文，生成精简后的替换字符串。

**替换输出格式**：生成 `batch-replacements.json`：
```json
{
  "version": "1.0",
  "replacements": [
    {"id": "call-001", "replacement": "\"精简后的字符串\\n\""},
    {"id": "call-002", "replacement": "\"%d %d %d\\n\""}
  ]
}
```

**替换规则**：
- 保留格式说明符：`%d`、`%s`、`%x`、`%02x` 等必须原样保留
- 保留转义序列：`\n`、`\r\n`、`\t` 等必须保留
- 保留引号：替换结果必须是完整的带引号字符串字面量，如 `"optimized\n"`
- 保持语义：确保替换后的字符串仍能传达相同的关键信息

### 步骤 5：导入替换结果

```bash
python scripts/replacements.py import \
  --file batch-replacements.json
```

**验证**：检查输出 `Imported N new, updated M existing replacements`

### 步骤 6：（可选）浏览器审查

```bash
python scripts/review.py \
  --input extracted.json --output review.html
```

**操作流程**：
1. 打开生成的 `review.html`（`file:///path/to/review.html`）
2. 逐项审查生成的替换是否合理
3. 在线编辑不满意的替换
4. 点击 **Download** 导出更新后的 `replacements.json`

### 步骤 7：应用替换到源码

```bash
python scripts/replacements.py apply --input extracted.json
```

**预期输出**：
```
Applied replacements to pm/pm_porting.c
Applied replacements to at/at_cmd_porting/at_porting.c
...
Applied 64/64 replacements.
```

**如果应用失败**：
- 检查 `git diff` 确认源码是否已被其他修改改变（偏移量不匹配）
- 重新运行 `analyze` 刷新偏移量

### 步骤 8：完成检查

```bash
python scripts/codebase.py status --input extracted.json
```

**预期输出**：
```
Stats: total=64, pending=0, completed=64
```

当 `pending=0` 时表示全部完成。向用户报告：
- 总替换数
- 涉及文件数
- 示例对比（原始 vs 替换后）
- 建议 `git diff` 审查最终变更

## 4. 命令速查表

| 目的 | 命令 |
|------|------|
| 提取字符串 | `python scripts/codebase.py analyze --config config.json --output extracted.json` |
| 获取批次 | `python scripts/codebase.py get --input extracted.json --batch 30`（默认只返回 id + stringLiteral）|
| 导入替换 | `python scripts/replacements.py import --file batch-replacements.json` |
| 审查页面 | `python scripts/review.py --input extracted.json --output review.html` |
| 应用替换 | `python scripts/replacements.py apply --input extracted.json` |
| 状态检查 | `python scripts/codebase.py status --input extracted.json` |
| 严格检查 | `python scripts/codebase.py status --input extracted.json --strict` |

## 5. 常见问题与处理

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `analyze` 返回 0 条 | `targetFunctions` 拼写错误或文件模式不匹配 | 检查函数名和 `filePatterns` |
| `apply` 报 `file not found` | `filePath` 是相对路径但运行目录不对 | 在 `extracted.json` 所在目录运行 apply，或确保 `gitRepo` 正确 |
| `apply` 报 `original string mismatch` | 源码已被修改，偏移量失效 | 重新运行 `analyze` |
| `import` 后 `replacements.json` 为空 | 导入文件格式错误或 ID 不匹配 | 检查 `batch-replacements.json` 格式 |

## 6. 安全注意事项

- `apply` 命令会直接修改源码文件，但会**验证原字符串偏移位置**并**原子写入**（先写 `.tmp` 再 `os.replace`）
- 运行前确保工作区已提交或已备份
- `replacements.json` 在 apply 后**保留不清空**，供审计和复查

## 7. 完整示例

**场景**：优化 `/home/user/project/src` 目录下的所有 `osal_printk` 调用。

```bash
# 1. 准备配置
cat > config.json << 'EOF'
{"targetFunctions": ["osal_printk"], "filePatterns": ["*.c", "*.h"], "excludePatterns": [], "paths": ["/home/user/project/src"]}
EOF

# 2. 提取
python scripts/codebase.py analyze \
  --config config.json --output extracted.json

# 3. 获取批次 → 生成 batch-replacements.json
python scripts/codebase.py get --input extracted.json --batch 30
# [生成 batch-replacements.json]

# 4. 导入并应用
python scripts/replacements.py import --file batch-replacements.json
python scripts/replacements.py apply --input extracted.json

# 5. 检查完成
python scripts/codebase.py status --input extracted.json
```

## 8. 检查清单

- [ ] 已确认目标打印函数名和源码路径
- [ ] `config.json` 已创建且格式正确
- [ ] `analyze` 成功提取到字符串（数量 > 0）
- [ ] 所有待处理项已分批获取并完成替换生成
- [ ] 替换结果已导入 `replacements.json`
- [ ] （可选）已通过 `review.py` 审查并导出更新
- [ ] `replacements.py apply` 成功执行，无 `mismatch` 警告
- [ ] `status` 显示 `pending=0`，即 100% 完成
- [ ] 已执行 `git diff` 确认变更正确
- [ ] 已向用户报告结果（总数、文件数、示例对比）

## 9. 参考文档

| 文件 | 内容 |
|------|------|
| [references/data-formats.md](references/data-formats.md) | JSON 数据格式详细说明 |
| [references/advanced-usage.md](references/advanced-usage.md) | 大型代码库调优、完整 CLI 参考 |
