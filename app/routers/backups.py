from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from app import backup

router = APIRouter(prefix="/api/backups", tags=["backups"])


def _existing(name: str):
    path = backup.find_backup(name)
    if path is None:
        raise HTTPException(status_code=404, detail="バックアップが見つかりません")
    return path


@router.get("")
def list_backups():
    return backup.list_backups()


@router.post("", status_code=201)
def create_backup():
    return backup.create_backup()


@router.post("/{name}/restore")
def restore_backup(name: str):
    before = backup.restore_backup(_existing(name))
    return {"restored": name, "before_restore": before}


@router.get("/{name}/download")
def download_backup(name: str):
    return FileResponse(_existing(name), media_type="application/octet-stream", filename=name)


@router.delete("/{name}", status_code=204)
def delete_backup(name: str, confirm: str = ""):
    """誤って消さないよう、確認として消すバックアップの名前（?confirm=名前）が必要。"""
    path = _existing(name)
    if confirm != name:
        raise HTTPException(status_code=400, detail="削除するには確認が必要です")
    path.unlink()
    return Response(status_code=204)
