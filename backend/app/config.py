"""Application configuration, read from environment variables (.env supported)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Search order, first match wins per key: backend/.env → repo root .env → cwd .env.
# load_dotenv(override=False) never overwrites keys already set, so earlier
# files win and real environment variables always take precedence.
for _env_path in (
    Path(__file__).resolve().parent.parent / ".env",  # backend/.env
    Path(__file__).resolve().parent.parent.parent / ".env",  # repo root .env
    Path(".env"),  # cwd
):
    if _env_path.exists():
        load_dotenv(_env_path, override=False)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    max_nodes: int = int(os.getenv("MAX_GRAPH_NODES", "600"))
    max_edges: int = int(os.getenv("MAX_GRAPH_EDGES", "2500"))
    chunk_chars: int = int(os.getenv("CHUNK_CHARS", "4000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    llm_concurrency: int = int(os.getenv("LLM_CONCURRENCY", "4"))
    extraction_mode: str = os.getenv("EXTRACTION_MODE", "balanced").lower()
    llm_chunk_fraction: float = float(os.getenv("LLM_CHUNK_FRACTION", "0.35"))
    llm_min_chunks: int = int(os.getenv("LLM_MIN_CHUNKS", "12"))
    llm_max_chunks: int = int(os.getenv("LLM_MAX_CHUNKS", "250"))

    allowed_extensions: tuple[str, ...] = (
        ".pdf", ".docx", ".txt", ".md", ".pptx", ".html", ".htm",
    )

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
