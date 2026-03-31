# AIOCR 插件修改说明

基于 [UmiOCR-AI-OCR-Plugin](https://github.com/EatWorld/UmiOCR-AI-OCR-Plugin) 修改，添加了 **Markdown 输出** 功能。

## 修改概览

| 文件 | 修改内容 |
|------|----------|
| `ai_ocr_config.py` | 添加 `markdown_output` 配置项 |
| `ai_ocr.py` | 修改 4 个方法以支持 markdown 输出 |

---

## 1. ai_ocr_config.py

### 在 `localOptions` 中添加配置项

在 `output_format` 配置项之后添加：

```python
"markdown_output": {
    "title": tr("Markdown 输出"),
    "default": False,
    "toolTip": tr("启用后，所有 AI 接口都返回 markdown 格式，保留原文排版结构。"),
},
```

---

## 2. ai_ocr.py

### 2.1 修改 `runBase64` 方法（约第 1938 行）

在方法开头添加 markdown 检测逻辑，当启用时跳过 Paddle 纠错流程：

```python
def runBase64(self, imageBase64):
    """处理base64图片"""
    try:
        if hasattr(self, 'local_config'):
            strategy = self.local_config.get('dual_strategy', 'ai_high_precision_with_coordinates')
            markdown_output = self.local_config.get('markdown_output', False)  # 新增
            
            # 新增：如果启用了 markdown 输出，直接使用 AI 识别
            if markdown_output:
                processed_base64 = self._preprocess_image(imageBase64)
                return self._run_ocr(processed_base64, self.local_config)
            
            # 原有逻辑继续...
```

### 2.2 修改 `_build_prompt` 方法（约第 2046 行）

添加 markdown 输出格式的提示词：

```python
def _build_prompt(self, config):
    """构建提示词"""
    language = config.get("language", "auto")
    output_format = config.get("output_format", "text_only")
    markdown_output = config.get("markdown_output", False)  # 新增
    
    # 语言映射...
    lang_instruction = lang_map.get(language, "自动检测语言")
    
    if output_format == "with_coordinates":
        prompt = f"""识别图片文字并返回坐标..."""
    elif markdown_output:  # 新增分支
        prompt = f"""请将图片中的所有内容（文本、表格、公式）完整地识别出来，语言：{lang_instruction}，并以 Markdown 格式返回。

请严格遵守以下规则：
1.  **表格：** 如果图片中包含表格，请必须使用 Markdown 表格语法将其格式化。
2.  **公式：** 如果图片中包含数学公式，请必须使用 LaTeX 格式将其包裹 (行内公式使用 $...$，块级公式使用 $$...$$)。
3.  **结构：** 保持合理的段落、标题和列表结构。
4.  **纯净：** 直接返回 Markdown 结果，不要包含任何解释性文字（如 "这是结果：" 或 "好的："），也不要使用 "```markdown" 代码块标记包裹整个结果。"""
    else:
        prompt = f"""识别图片中的文字..."""
```

### 2.3 修改 `_convert_to_umi_format` 方法（约第 2216 行）

传递 config 参数给 `_parse_text_only`：

```python
def _convert_to_umi_format(self, content, config):
    """转换为Umi格式"""
    output_format = config.get("output_format", "text_only")
    
    if output_format == "with_coordinates":
        return self._parse_text_with_coordinates(content)
    else:
        return self._parse_text_only(content, config)  # 添加 config 参数
```

### 2.4 修改 `_parse_text_only` 方法（约第 2476 行）

添加 config 参数，支持 markdown 整体返回：

```python
def _parse_text_only(self, content, config=None):  # 添加 config 参数
    """解析纯文本"""
    # 原有内容处理逻辑...
    
    # 新增：检查是否启用 markdown 输出
    markdown_output = False
    if config:
        markdown_output = config.get("markdown_output", False)
    if not markdown_output:
        # 兼容旧逻辑：paddle_vl 系列默认返回 markdown
        provider_name = self.global_config.get("a_provider", self.global_config.get("provider", ""))
        if provider_name in ["paddle_vl", "paddle_vl_15", "pp_structure_v3"]:
            markdown_output = True
    
    # 新增：如果启用 markdown 输出，整体返回
    if markdown_output:
        img_width, img_height = self.original_size if getattr(self, "original_size", None) else (800, 600)
        single_box = [[0, 0], [img_width, 0], [img_width, img_height], [0, img_height]]
        return {"code": 100, "data": [{"text": content, "box": single_box, "score": 1.0}]}
    
    # 原有逻辑：按行分割文本...
```

---

## 功能说明

1. **Markdown 输出开关**：在界面勾选后，所有 AI 接口将返回 markdown 格式结果
2. **跳过 Paddle 纠错**：启用 markdown 时自动跳过 Paddle 纠错流程，避免破坏格式
3. **整体返回**：markdown 内容作为整体返回，保留所有缩进和换行
4. **兼容性**：paddle_vl 系列接口默认仍返回 markdown 格式
