# Vision API SOP

## ⚠️ 前置规则（必须遵守）

1. **先枚举窗口**：调用 vision 前必须先用 `pygetwindow` 枚举窗口标题，确认目标窗口存在且已激活到前台。窗口不存在就不要截图。
2. **🚫 禁止全屏截图**：必须先利用ljqCtrl截取窗口区域。能截局部（如标题栏）就不截整窗口，能截窗口就绝不全屏。全屏截图在任何场景下都不允许。
3. **能不用 vision 就不用**：如果窗口标题/本地 OCR（`ocr_utils.py`）能获取所需信息，就不要调用 vision API，省 token 且更可靠。Vision 是最后手段。

## 当前后端

**ModelScope 免费 API** — Qwen/Qwen3-VL-235B-A22B-Instruct
- 配置文件: `memory/vision_api.py`，密钥在 `../mykey.py` 的 `MODELSCOPE_API_KEY`
- 零依赖: 仅用 stdlib `urllib` + `PIL`，无需 `requests`
- 限流: 免费版有速率限制，密集调用会返回 429

## 快速用法

```python
from vision_api import ask_vision

# 支持三种输入方式
result = ask_vision(pil_image, prompt="描述图片", timeout=60)
result = ask_vision("screenshot.png", prompt="图中有什么？")
result = ask_vision(Path("photo.jpg"), prompt="分析")

# 返回: 成功 → 模型回复(str)，失败 → 'Error: ...' 开头字符串
# 大图自动缩放(max_pixels=1_440_000)，RGBA/LA/P 自动转 RGB
```

## 初次配置或换后端

1. 检查 `memory/vision_api.py` 是否存在
2. 若无：复制 `memory/vision_api.template.py`，修改头部配置区
3. 保底方案：去 `https://modelscope.cn/my/myaccesstoken` 申请免费 token
