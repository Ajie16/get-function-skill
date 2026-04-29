# Code Optimizer

批量提取代码库中打印函数（如 `osal_printk`、`printk`、`printf`）的字符串字面量参数，生成精简替换后安全写回源码。

## 特性

- **零依赖**：仅需 Python 3 标准库
- **安全应用**：验证偏移位置后原子写入（`.tmp` + `os.replace`）
- **批量处理**：支持大型代码库分批处理
- **浏览器审查**：生成静态 HTML 页面，支持在线编辑和导出

## 快速开始

```bash
# 1. 准备配置（config.json 内含源码路径）
cat > config.json << 'EOF'
{
  "targetFunctions": ["osal_printk"],
  "filePatterns": ["*.c", "*.h"],
  "excludePatterns": [],
  "paths": ["/path/to/source"]
}
EOF

# 2. 提取
python scripts/codebase.py analyze --config config.json --output extracted.json

# 3. 获取批次（默认纯文本输出）
python scripts/codebase.py get --input extracted.json --batch 30

# 4. 生成 batch-replacements.json 后导入并应用
python scripts/replacements.py import --file batch-replacements.json
python scripts/replacements.py apply --input extracted.json

# 5. 检查完成
python scripts/codebase.py status --input extracted.json
```

## 目录结构

```
.
├── SKILL.md                 # AI 使用指南
├── README.md                # 本文件
├── scripts/
│   ├── codebase.py          # 提取、获取、状态
│   ├── replacements.py      # 导入、应用替换
│   └── review.py            # 生成审查 HTML
└── references/
    ├── data-formats.md      # JSON 数据格式说明
    └── advanced-usage.md    # 高级用法和 CLI 参考
```

## 命令速查

| 命令 | 说明 |
|------|------|
| `python scripts/codebase.py analyze --config cfg.json --output out.json` | 提取字符串 |
| `python scripts/codebase.py get --input out.json --batch 30` | 获取待处理项（默认纯文本） |
| `python scripts/codebase.py get --input out.json --batch 30 --json` | 获取待处理项（JSON 格式） |
| `python scripts/codebase.py get --input out.json --batch 30 --json --format full` | 获取完整字段（需配合 `--json`） |
| `python scripts/replacements.py import --file batch.json` | 导入替换（支持紧凑数组和对象格式） |
| `python scripts/replacements.py apply --input out.json` | 应用到源码 |
| `python scripts/review.py --input out.json --output review.html` | 生成审查页面 |
| `python scripts/codebase.py status --input out.json` | 查看进度 |

## 替换格式

`batch-replacements.json` 支持两种格式，推荐紧凑数组：

```json
{
  "version": "1.0",
  "replacements": [
    ["call-001", "\"精简后的字符串\\n\""],
    ["call-002", "\"%d %d %d\\n\""]
  ]
}
```

或传统对象格式：

```json
{
  "version": "1.0",
  "replacements": [
    {"id": "call-001", "replacement": "\"精简后的字符串\\n\""}
  ]
}
```

## License

MIT
