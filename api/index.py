import json
import base64
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from io import BytesIO
from PIL import Image

app = FastAPI()

@app.post("/api/crop")
async def crop_image(
    image: UploadFile = File(...), 
    boxes: str = Form(...)
):
    try:
        content = await image.read()
        img = Image.open(BytesIO(content))
        
        clean_text = boxes.replace("```json", "").replace("```", "").strip()
        box_list = json.loads(clean_text)
        
        results = []
        for item in box_list:
            box = item.get("box")
            cropped_img = img.crop((box[0], box[1], box[2], box[3]))
            
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