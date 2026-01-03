from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def upload_image(image: UploadFile = File(...)):
    content = await image.read()
    print("Đã nhận ảnh:", len(content), "bytes")
    return {"success": True}
