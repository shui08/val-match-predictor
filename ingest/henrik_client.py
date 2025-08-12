import os
import time
import httpx
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from collections import deque
from urllib.parse import quote

load_dotenv()

HENRIK_BASE = "https://api.henrikdev.xyz"
API_KEY = os.getenv("HENRIK_API_KEY")

HEADERS = {"Authorization": API_KEY}

class HenrikClient:
    def __init__(self, rate_per_minute: int = 30):
        self.rate_per_minute = rate_per_minute
        self.request_times = deque()
        self.client = httpx.Client(base_url=HENRIK_BASE, headers=HEADERS, timeout=30.0)

    def _respect_rate_limit(self):
        while True:
            now = time.time()
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
            if len(self.request_times) < self.rate_per_minute:
                self.request_times.append(now)
                return
            sleep_for = 60 - (now - self.request_times[0]) + 0.05
            time.sleep(sleep_for)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._respect_rate_limit()
        resp = self.client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()
    
    def resolve_tag(self, name: str, tag: str):
        return self._get(f"/valorant/v2/account/{quote(name)}/{quote(tag)}")
    
    def matches(self, region: str, name: str, tag: str, mode: str = "competitive",
            size: int = 10, start: int = 0) -> Dict[str, Any]:
        params = {"mode": mode, "size": size, "start": start}
        return self._get(f"/valorant/v3/matches/{region}/{quote(name)}/{quote(tag)}", params=params)
    
    def mmr(self, region: str, name: str, tag: str, platform: str = "pc") -> Dict[str, Any]:
        return self._get(f"/valorant/v3/mmr/{region}/{platform}/{quote(name)}/{quote(tag)}")
    
    def close(self):
        self.client.close()
    
    