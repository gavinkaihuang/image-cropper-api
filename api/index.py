import json
import base64
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from io import BytesIO
from PIL import Image

app = FastAPI()

# ==========================================
# 1. 审核控制台路由 (浏览器直接访问你的 Vercel 域名)
# ==========================================
@app.get("/")
async def review_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI 切图审核工作台</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 20px; max-width: 1000px; margin: 0 auto; background: #f5f5f7; }
            h2 { color: #333; }
            textarea { width: 100%; height: 150px; padding: 10px; border-radius: 8px; border: 1px solid #ccc; font-family: monospace; }
            button { margin-top: 10px; padding: 10px 20px; background: #0070f3; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
            button:hover { background: #0051a2; }
            .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin-top: 30px; }
            .card { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; }
            .card img { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 4px; margin-bottom: 10px; }
            .tag { display: inline-block; background: #e0e0e0; padding: 4px 8px; border-radius: 4px; font-size: 12px; color: #555; }
        </style>
    </head>
    <body>
        <h2>🔍 试卷切图审核工作台</h2>
        <p>请将 Dify 输出的 JSON 数组（包含 Base64 字符串）粘贴到下方：</p>
        <textarea id="jsonInput" placeholder='[{"cropped_array": [{"id": 1, "image": "data:image/jpeg;base64,..."}]}]'></textarea>
        <button onclick="renderImages()">渲染图片</button>
        
        <div class="gallery" id="gallery"></div>

        <script>
            function renderImages() {
                const input = document.getElementById('jsonInput').value;
                const gallery = document.getElementById('gallery');
                gallery.innerHTML = ''; // 清空画廊
                
                try {
                    const data = JSON.parse(input);
                    // 兼容 Dify 迭代节点输出的数组格式
                    data.forEach((iterationResult, index) => {
                        let croppedArray = [];
                        // 如果是字符串，再解析一次
                        if (typeof iterationResult === 'string') {
                            croppedArray = JSON.parse(iterationResult).cropped_array || [];
                        } else {
                            croppedArray = iterationResult.cropped_array || [];
                        }
                        
                        croppedArray.forEach(item => {
                            const card = document.createElement('div');
                            card.className = 'card';
                            card.innerHTML = `
                                <img src="${item.image}" alt="题目 ${item.id}">
                                <div class="tag">题目 ID: ${item.id} (迭代轮次: ${index + 1})</div>
                            `;
                            gallery.appendChild(card);
                        });
                    });
                } catch (e) {
                    alert('JSON 解析失败，请检查粘贴的内容格式是否完整！\\n错误信息: ' + e.message);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# ==========================================
# 2. 原有的切图 API 路由 (供 Dify 调用)
# ==========================================
@app.post("/api/crop")
async def crop_image(
    image: UploadFile = File(...), 
    boxes: str = Form(...)
):
    try:
        content = await image.read()
        img = Image.open(BytesIO(content))
        
        # 1. 获取原图的真实宽高
        img_w, img_h = img.size
        
        clean_text = boxes.replace("```json", "").replace("```", "").strip()
        box_list = json.loads(clean_text)
        
        results = []
        for item in box_list:
            box = item.get("box")
            
            # 2. 核心修复：将 Qwen-VL 的千分位相对坐标转换回真实像素坐标
            # 公式：(归一化坐标 / 1000) * 原图真实尺寸
            x1 = int((box[0] / 1000.0) * img_w)
            y1 = int((box[1] / 1000.0) * img_h)
            x2 = int((box[2] / 1000.0) * img_w)
            y2 = int((box[3] / 1000.0) * img_h)
            
            # 3. 防御性编程：防止坐标越界或反转导致 PIL 崩溃
            x1, x2 = max(0, min(x1, x2)), min(img_w, max(x1, x2))
            y1, y2 = max(0, min(y1, y2)), min(img_h, max(y1, y2))
            
            # 4. 使用换算后的真实坐标进行裁切
            cropped_img = img.crop((x1, y1, x2, y2))
            
            buffered = BytesIO()
            cropped_img.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            results.append({
                "id": item.get("id"),
                "image": "data:image/jpeg;base64," + img_base64
            })
            
        return JSONResponse(content={"cropped_array": results})
        
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)