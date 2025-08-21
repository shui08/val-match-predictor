import json
import os
import time
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from httpx import HTTPError
from .henrik_client import HenrikClient

load_dotenv()

DEFAULT_REGION = os.getenv("DEFAULT_REGION", "na")
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = RAW_DIR / "index.json"

class Cache:
    def __init__(self):
        self.index = {"players": {}}
        if INDEX_PATH.exists():
            try:
                self.index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.index = {"players": {}}
        self.client = HenrikClient()

    def save_index(self):
        temp = INDEX_PATH.with_suffix(".temp")
        temp.write_text(json.dumps(self.index, indent=2), encoding="utf-8")
        temp.replace(INDEX_PATH)

    def get_or_refresh_player(self, name_tag: str, max_age_hours: int = 24, max_matches: int = 50) -> Dict[str, Any]:
        name_tag = name_tag.strip()
        
        if "#" not in name_tag:
            raise ValueError(f"Riot tag must look like 'Name#Tag', got: {name_tag}")
        
        name, tag = name_tag.split("#", 1)
        meta = self.index["players"].get(name_tag)
        now = time.time()
        stale = True
        if meta and (now - meta.get("fetched_at", 0)) < max_age_hours * 3600:
            stale = False

        if stale:
            acct = self.client.resolve_tag(name, tag)
            
            if acct.get("status") != 200 or not acct.get("data"):
                raise ValueError(f"Account '{name}#{tag}' not found in Henrik API")
            
            puuid = acct.get("data", {}).get("puuid")
            region = acct.get("data", {}).get("region", DEFAULT_REGION)

            matches = []
            start = 0
            while len(matches) < max_matches:
                batch = self.client.matches(region, name, tag, mode="competitive", size=10, start=start)
                data = batch.get("data") or []
                if not data:
                    break
                matches.extend(data)
                start += 10

            try:
                mmr = self.client.mmr(region, name, tag).get("data")
            except HTTPError:
                mmr = None


            payload = {
                "name_tag": name_tag,
                "region": region,
                "puuid": puuid,
                "mmr": mmr,
                "matches": matches,
                "fetched_at": now,
            }

            raw_path = RAW_DIR / f"{puuid or name_tag.replace('#','_')}.json"
            with raw_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
                
            self.index["players"][name_tag] = {
                "puuid": puuid,
                "region": region,
                "raw_path": str(raw_path),
                "fetched_at": now,
            }
            self.save_index()
            return payload
        else:
            raw_path = Path(meta["raw_path"])
            try:
                return json.loads(raw_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, FileNotFoundError):
                del self.index["players"][name_tag]
                self.save_index()
                return self.get_or_refresh_player(name_tag, max_age_hours=0)
