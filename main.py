from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from typing import List, Dict
from fastapi.templating import Jinja2Templates
from random import randint
from io import BytesIO
import asyncio
import zipfile
import math

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Хранилище для загруженных файлов в оперативной памяти
storage: Dict[str, Dict[str, BytesIO]] = {}
# Время жизни файла в минутах
FILE_LIFETIME_MINUTES = 30

async def delete_files_after_timeout(uid: str):
    await asyncio.sleep(FILE_LIFETIME_MINUTES * 60)
    if uid in storage:
        del storage[uid]

def pretty_file_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


@app.post("/upload/")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    uid = str(randint(1000, 9999))
    storage[uid] = {}

    for file in files:
        file_content = BytesIO(await file.read())
        storage[uid][file.filename] = file_content

    background_tasks.add_task(delete_files_after_timeout, uid)
    
    return RedirectResponse(f"/{uid}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/{uid}")
async def get_files(uid: str, request: Request):
    if uid not in storage:
        raise HTTPException(status_code=404, detail="Files not found or expired")
    
    files = [{"name": name, "size": pretty_file_size(len(content.getvalue()))} for name, content in storage[uid].items()]
    return templates.TemplateResponse("files.html", {"request": request, "files": files, "uid": uid})

@app.get("/{uid}/download/{filename}")
async def download_file(uid: str, filename: str):
    if uid not in storage or filename not in storage[uid]:
        raise HTTPException(status_code=404, detail="File not found or expired")

    file_content = storage[uid][filename]
    file_content.seek(0)
    return StreamingResponse(file_content, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={filename.encode('utf-8')}"})

@app.get("/{uid}/download_all")
async def download_all_files(uid: str):
    if uid not in storage:
        raise HTTPException(status_code=404, detail="Files not found or expired")

    zip_content = BytesIO()
    with zipfile.ZipFile(zip_content, 'w') as zipf:
        for filename, file_content in storage[uid].items():
            file_content.seek(0)
            zipf.writestr(filename, file_content.read())
    zip_content.seek(0)
    return StreamingResponse(zip_content, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=all_files.zip"})

@app.get("/")
async def main():
    content = """
        <body>
        <form action="/upload/" enctype="multipart/form-data" method="post">
        <input name="files" type="file" multiple id="fileInput">
        <input type="submit" style="display: none" id="submit">
        </form>
        </body>
        <script>
            document.getElementById('fileInput').addEventListener('change', function(event) {
            if (event.target.files.length > 0) {
                document.getElementById('submit').click()
            }
            })
        </script>
    """
    return HTMLResponse(content=content)


import uvicorn 
uvicorn.run(app, port=42701)