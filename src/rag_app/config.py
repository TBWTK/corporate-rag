from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Контекст"
    app_environment: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://rag:rag@db:5432/rag"
    data_dir: Path = Path("/data/uploads")
    demo_documents_dir: Path = Path("examples/acme-corp")
    max_upload_mb: int = Field(default=25, ge=1, le=100)

    llm_provider: str = "gigachat"
    llm_api_key: str | None = None
    gigachat_api_key: str | None = None
    gigachat_client_id: str | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_api_base_url: str = "https://api.giga.chat/v1"
    gigachat_verify_ssl: bool = True
    gigachat_ca_bundle_file: Path | None = Path("certs/russian_trusted_root_ca_pem.crt")
    gigachat_serialize_requests: bool = True

    generation_model: str = "GigaChat-2-Pro"
    embedding_model: str = "Embeddings-2"
    embedding_dimension: int = Field(default=1024, ge=8, le=4096)
    embedding_batch_size: int = Field(default=8, ge=1, le=32)
    chunk_max_chars: int = Field(default=1100, ge=128, le=12000)
    chunk_overlap_chars: int = Field(default=160, ge=0, le=2000)
    retrieval_top_k: int = Field(default=6, ge=1, le=20)
    retrieval_candidates: int = Field(default=18, ge=4, le=100)
    relation_max_documents: int = Field(default=3, ge=0, le=10)
    relation_chunks_per_document: int = Field(default=2, ge=1, le=6)
    generation_max_tokens: int = Field(default=1200, ge=128, le=4096)
    vision_ingestion_enabled: bool = True
    vision_max_output_tokens: int = Field(default=2400, ge=256, le=8192)
    visual_page_dpi: int = Field(default=144, ge=72, le=300)
    visual_render_timeout_seconds: float = Field(default=120.0, ge=10, le=600)
    visual_max_pages: int = Field(default=100, ge=1, le=500)
    visual_context_max_chunks: int = Field(default=40, ge=6, le=100)

    worker_poll_seconds: float = Field(default=1.5, ge=0.1, le=30)
    processing_timeout_minutes: int = Field(default=15, ge=1, le=240)

    @model_validator(mode="after")
    def validate_model_budgets(self) -> Settings:
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            raise ValueError("chunk_overlap_chars должен быть меньше chunk_max_chars")
        if self.embedding_model in {"Embeddings", "Embeddings-2"} and self.chunk_max_chars > 1400:
            raise ValueError(
                "chunk_max_chars должен быть <= 1400 для 512-токенного окна Embeddings-2"
            )
        if (
            self.llm_provider.casefold() != "fake"
            and self.embedding_model in {"Embeddings", "Embeddings-2"}
            and self.embedding_dimension != 1024
        ):
            raise ValueError("embedding_dimension должен быть 1024 для Embeddings/Embeddings-2")
        return self

    @property
    def effective_gigachat_key(self) -> str | None:
        return self.gigachat_api_key or self.llm_api_key

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
