"""
설정 로더 — config.yaml(조정값)과 .env(키·모델·연락처)를 한곳에서 읽는다.

도메인을 모르는 공통 모듈이다. 다른 모듈은 여기서 값만 가져다 쓴다.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent          # cube_rag/
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Env:
    gms_key: str
    gms_base_url: str
    chat_model: str
    embed_model: str
    wiki_user_agent: str

    def missing(self) -> list[str]:
        """비어 있는 필수 환경변수 이름 목록 (/api/status, 시작 시 안내용)."""
        required = {
            "GMS_KEY": self.gms_key,
            "GMS_BASE_URL": self.gms_base_url,
            "CHAT_MODEL": self.chat_model,
            "EMBED_MODEL": self.embed_model,
            "WIKI_USER_AGENT": self.wiki_user_agent,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_env() -> Env:
    return Env(
        gms_key=os.getenv("GMS_KEY", "").strip(),
        gms_base_url=os.getenv("GMS_BASE_URL", "").strip(),
        chat_model=os.getenv("CHAT_MODEL", "").strip(),
        embed_model=os.getenv("EMBED_MODEL", "").strip(),
        wiki_user_agent=os.getenv("WIKI_USER_AGENT", "").strip(),
    )


@lru_cache
def get_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def path(key: str) -> Path:
    """config.yaml paths.<key>를 프로젝트 루트 기준 절대 경로로 돌려준다."""
    return ROOT / get_config()["paths"][key]
