# dashboard/components/export_report.py

import os
import io
import pandas as pd
import json
from jinja2 import Template
from markdown import markdown
from PIL import Image

try:
    import pdfkit
except ImportError:
    pdfkit = None

def export(selected_files, export_format, output_dir):
    """
    导出分析报告（PDF/Markdown），返回二进制流
    :param selected_files: 用户选择的文件名列表
    :param export_format: 'PDF' 或 'Markdown'
    :param output_dir: 文件所在目录
    :return: bytes
    """
    # 1. 汇总内容
    sections = []
    for fname in selected_files:
        fpath = os.path.join(output_dir, fname)
        ext = os.path.splitext(fname)[-1].lower()
        if ext in [".png", ".jpg", ".jpeg"]:
            # 图片
            sections.append({
                "type": "image",
                "title": fname,
                "path": fpath
            })
        elif ext == ".csv":
            # 表格
            df = pd.read_csv(fpath)
            sections.append({
                "type": "table",
                "title": fname,
                "table_html": df.head(20).to_html(index=False),  # 只展示前20行
                "shape": df.shape
            })
        elif ext == ".json":
            # JSON 摘要
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            sections.append({
                "type": "json",
                "title": fname,
                "json_str": json.dumps(data, ensure_ascii=False, indent=2)[:2000]  # 截断
            })
        else:
            continue

    # 2. 渲染 markdown
    md_template = """
# EmotionSense 分析报告

{% for sec in sections %}
## {{ sec.title }}

{% if sec.type == 'image' %}
![]({{ sec.path }})
{% elif sec.type == 'table' %}
**表格预览（共{{ sec.shape[0] }}行, {{ sec.shape[1] }}列）**  
{{ sec.table_html | safe }}
{% elif sec.type == 'json' %}
<details>
<summary>JSON内容预览</summary>

```json
{{ sec.json_str }}
```
</details>
{% endif %}

---
{% endfor %}
    """
    template = Template(md_template)
    md_content = template.render(sections=sections)

    if export_format == "Markdown":
        return md_content.encode("utf-8")

    # 3. Markdown 转 HTML
    html_content = markdown(md_content, extensions=['tables', 'fenced_code'])

    # 4. 图片路径处理（本地图片转 base64 内嵌）
    from base64 import b64encode
    import re

    def img_to_base64(path):
        with open(path, "rb") as f:
            return b64encode(f.read()).decode("utf-8")

    def replace_img(match):
        img_path = match.group(1)
        if not os.path.isabs(img_path):
            img_path = os.path.join(output_dir, img_path)
        ext = os.path.splitext(img_path)[-1].lower()
        if ext in [".png", ".jpg", ".jpeg"]:
            b64 = img_to_base64(img_path)
            return f'<img src="data:image/{ext[1:]};base64,{b64}" style="max-width:700px;">'
        return match.group(0)

    html_content = re.sub(r'!\[\]\((.*?)\)', replace_img, html_content)

    # 5. HTML 转 PDF
    if pdfkit is None:
        raise ImportError("请先安装 pdfkit 和 wkhtmltopdf 以支持 PDF 导出")
    pdf_bytes = pdfkit.from_string(html_content, False)
    return pdf_bytes