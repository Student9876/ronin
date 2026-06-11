import httpx
from typing import Dict

# Centralized browser footprint to bypass bot detection / strict limiters
STANDARD_BROWSER_HEADERS: Dict[str, str] = {
    "X-Forwarded-For": "127.0.0.1",
    "X-Real-IP": "127.0.0.1",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "no-cache"
}

def get_http_client(use_headers: bool = True, timeout: float = 15.0) -> httpx.AsyncClient:
    """
    Returns an Asynchronous HTTP Client pre-configured with standardized 
    spoofing layers. Fully reusable across Research, Coding, or System modes.
    """
    return httpx.AsyncClient(
        headers=STANDARD_BROWSER_HEADERS if use_headers else None,
        timeout=timeout,
        follow_redirects=True
    )