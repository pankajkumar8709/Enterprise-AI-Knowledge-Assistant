from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise AI Knowledge Assistant API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    secret_key: str = Field(
        min_length=32,
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY"),
        description="HS256 signing key; configure with JWT_SECRET.",
    )
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    # Spec §4 JWT_REFRESH_DAYS.
    jwt_refresh_days: int = Field(default=7, ge=1, le=365)
    database_url: str = Field(alias="DATABASE_URL")
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")
    log_level: str = "INFO"
    document_upload_dir: str = "storage/documents"
    document_extraction_dir: str = "storage/extractions"
    # Spec §4 MAX_UPLOAD_MB=25 (was 10 MB pre-Phase 5.5).
    max_document_size_bytes: int = 25 * 1024 * 1024
    # Chunking tunables (spec §4) — no hardcoded chunk parameters (audit F-039).
    chunk_target_tokens: int = 500
    chunk_max_tokens: int = 700
    chunk_min_tokens: int = 60
    chunk_overlap_tokens: int = 80
    # CORS (spec §4 CORS_ORIGINS) — audit F-026.
    cors_origins: str = "http://localhost:5173"
    # --- Phase 5.5 additions (spec §4/§8) ---
    redis_url: str = "redis://redis:6379/0"
    allow_self_signup: bool = True
    allowed_email_domains: str = ""  # empty = any domain (spec §4)
    allowed_extensions: str = "pdf,docx,pptx,txt,md,markdown"
    ocr_enabled: bool = True
    ocr_min_chars_per_page: int = 40
    ocr_dpi: int = 300
    min_doc_chars: int = 200
    # --- Embeddings / retrieval (spec §4) ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_batch: int = 32
    query_embed_prefix: str = "Represent this sentence for searching relevant passages: "
    vector_top_k: int = 20
    fts_top_k: int = 20
    rrf_k: int = 60
    min_similarity: float = 0.35
    final_chunks: int = 6
    rerank_top_n: int = 20
    rerank_enabled: bool = False  # Phase 11 flips to true
    context_max_tokens: int = 4000
    cache_ttl_seconds: int = 900
    # --- OKF (spec §4) ---
    okf_top_k: int = 8
    okf_min_score: float = 0.25
    okf_auto_approve_threshold: float = 1.01  # never auto-approve
    okf_min_confidence_keep: float = 0.40
    classifier_min_confidence: float = 0.60
    # --- LLM (spec §4; provider = Groq per human decision, deviation from §2 Anthropic) ---
    llm_external_allowed: bool = False  # must be true or LLM calls are refused (§1)
    llm_provider: str = "groq"
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("GROQ_API_KEY", "LLM_API_KEY"))
    llm_model: str = "llama-3.3-70b-versatile"
    # Human-supplied Groq routing (from .env): primary + fallback model.
    llm_primary_model: str = "openai/gpt-oss-120b"
    llm_fallback_model: str = "qwen/qwen3.8-27b"
    llm_temperature: float = 0.0
    llm_max_output_tokens: int = 1000
    llm_timeout_seconds: int = 60
    llm_max_concurrency: int = Field(default=2, ge=1)
    llm_max_retries: int = Field(default=3, ge=0)
    chat_history_turns: int = 6

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_extension_list(self) -> list[str]:
        return [ext.strip().lower().lstrip(".") for ext in self.allowed_extensions.split(",") if ext.strip()]

    @property
    def allowed_email_domain_list(self) -> list[str]:
        return [domain.strip().lower() for domain in self.allowed_email_domains.split(",") if domain.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    # Required fields (secret_key, database_url) are supplied by the environment
    # / .env at runtime; mypy cannot see pydantic-settings' env loading.
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
