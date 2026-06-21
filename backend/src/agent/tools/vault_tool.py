import os
import asyncio
from src.agent.tools.registry import tool_registry

VAULT_DIR = "/app/vault"

def _write_file_sync(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

@tool_registry.register("save_to_vault", "Saves a markdown report, summary, code reference, or plan to the vault for the user to access. Arguments: filename (str), content (str).")
async def save_to_vault(filename: str, content: str) -> str:
    """
    Saves a markdown file inside the user's workspace vault.
    Defensively sanitizes the filename to prevent path traversal outside /app/vault.
    """
    clean_filename = os.path.basename(filename)
    if not clean_filename.endswith(".md"):
        clean_filename += ".md"

    os.makedirs(VAULT_DIR, exist_ok=True)
    file_path = os.path.join(VAULT_DIR, clean_filename)

    try:
        await asyncio.to_thread(_write_file_sync, file_path, content)
        print(f"Successfully saved {clean_filename} to vault.")
        return f"Successfully saved document as '{clean_filename}' in the vault."
    except Exception as e:
        return f"Failed to save document to the vault: {str(e)}"
