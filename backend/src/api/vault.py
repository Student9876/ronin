import os
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/vault", tags=["Vault"])

VAULT_DIR = "/app/vault"

class VaultFile(BaseModel):
    name: str
    size: int
    mtime: float

def _list_vault_files() -> List[VaultFile]:
    if not os.path.exists(VAULT_DIR):
        return []
    
    files = []
    for f in os.listdir(VAULT_DIR):
        path = os.path.join(VAULT_DIR, f)
        if os.path.isfile(path) and f.endswith(".md"):
            stat = os.stat(path)
            files.append(VaultFile(
                name=f,
                size=stat.st_size,
                mtime=stat.st_mtime
            ))
    # Sort by mtime descending (newest first)
    files.sort(key=lambda x: x.mtime, reverse=True)
    return files

def _read_vault_file(filename: str) -> str:
    path = os.path.join(VAULT_DIR, filename)
    if not os.path.exists(path) or not os.path.isfile(path):
        raise FileNotFoundError()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/", response_model=List[VaultFile])
async def list_files():
    """Lists all markdown files inside the vault."""
    try:
        files = await asyncio.to_thread(_list_vault_files)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list vault files: {str(e)}")

@router.get("/{filename}")
async def get_file(filename: str):
    """Retrieves the content of a specific markdown file."""
    clean_filename = os.path.basename(filename)
    try:
        content = await asyncio.to_thread(_read_vault_file, clean_filename)
        return {"name": clean_filename, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in vault")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read vault file: {str(e)}")
