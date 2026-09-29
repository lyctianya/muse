"""文件域：上传 / 列表 / 下载 / 删除。

挂载前缀：/api/files（由 api/main.py 统一加）。
权限：
    files:view    查看与下载
    files:upload  上传
    files:manage  删除任意文件（无此权限只能删自己的）
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.platform import storage
from api.platform.auth import get_current_user, require_perm

router = APIRouter()

# 单文件上限 200MB
MAX_SIZE = 200 * 1024 * 1024


@router.get("/", dependencies=[Depends(require_perm("files:view"))])
def list_all(domain: str = "", limit: int = 100, offset: int = 0,
             user: dict = Depends(get_current_user)):
    items = storage.list_files(domain=domain or None,
                               limit=min(limit, 500), offset=offset)
    for it in items:
        it["created_at"] = it["created_at"].isoformat() if it.get("created_at") else None
        it["mine"] = str(it["owner_id"]) == str(user["id"])
    return {"items": items}


@router.post("/upload", dependencies=[Depends(require_perm("files:upload"))])
async def upload(file: UploadFile = File(...),
                 user: dict = Depends(get_current_user)):
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "文件超过 200MB 上限")
    meta = storage.save_file(
        content=content,
        filename=file.filename or "unnamed",
        mime=file.content_type or "application/octet-stream",
        owner_id=str(user["id"]),
        domain="files",
    )
    meta.pop("stored_path", None)
    return meta


@router.get("/{fid}", dependencies=[Depends(require_perm("files:view"))])
def download(fid: str):
    meta = storage.get_file(fid)
    if not meta:
        raise HTTPException(404, "文件不存在")
    p = storage.file_path(meta)
    if not p.exists():
        raise HTTPException(404, "文件已丢失")
    return FileResponse(str(p), media_type=meta["mime"],
                        filename=meta["filename"])


@router.delete("/{fid}")
def remove(fid: str, user: dict = Depends(get_current_user)):
    meta = storage.get_file(fid)
    if not meta:
        raise HTTPException(404, "文件不存在")
    perms = user.get("permissions", [])
    is_owner = str(meta["owner_id"]) == str(user["id"])
    if not is_owner and "files:manage" not in perms:
        raise HTTPException(403, "只能删除自己的文件")
    if not storage.delete_file(fid):
        raise HTTPException(404, "文件不存在")
    return {"ok": True}
