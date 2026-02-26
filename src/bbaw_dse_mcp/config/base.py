"""Configuration for bbaw-dse-mcp servers."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find project root (where .env is located)
# This module is in src/bbaw_dse_mcp/config/base.py
# Project root is 3 levels up
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    """Global settings, loaded from environment variables or .env"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_prefix="EDITIONS_",
        case_sensitive=False,
    )

    # Schleiermacher-digital
    sd_url: str = Field(
        default="http://localhost:8080",
        description="Base URL for Schleiermacher-digital (local or remote)",
    )
    sd_db_path: str = Field(
        default="/db/apps/schleiermacher",
        description="eXist-db app path (for admin/structure queries)",
    )
    sd_data_path: str = Field(
        default="/db/projects/schleiermacher/data",
        description="eXist-db data collection (TEI/XML documents)",
    )
    sd_cache_path: str = Field(
        default="/db/projects/schleiermacher/cache",
        description="eXist-db cache collection (JSON caches)",
    )
    sd_username: str | None = Field(default="admin")
    sd_password: str | None = Field(default="")
    sd_local: bool = Field(
        default=True,
        description="True for local development, False for remote",
    )

    # Acta Borussica
    ab_url: str = Field(
        default="https://actaborussica.bbaw.de",
        description="Base URL for Acta Borussica",
    )
    ab_db_path: str = Field(
        default="/db/apps/actaborussica",
        description="eXist-db app path (for admin/structure queries)",
    )
    ab_data_path: str = Field(
        default="/db/projects/actaborussica/data",
        description="eXist-db data collection (TEI/XML documents)",
    )
    ab_username: str | None = Field(default=None)
    ab_password: str | None = Field(default=None)

    # correspSearch
    cs_api_url: str = Field(
        default="https://correspsearch.net/api/v2.0",
        description="correspSearch API URL (v2.0)",
    )

    # GeoNames
    geonames_username: str | None = Field(
        default=None,
        description="GeoNames API username for place geocoding (get one at geonames.org)",
    )

    # Anthropic (for deep_research Agent)
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API Key for the ReAct Research Agent"
    )
    research_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model for the Research Agent (cheaper model)",
    )
    research_max_steps: int = Field(
        default=10, description="Maximum steps for Research Agent"
    )

    # Server
    server_name: str = Field(
        default="Digital Editions", description="Name of the MCP Server"
    )


# Singleton instance
settings = Settings()

# TEI Namespace constants
TEI_NAMESPACE = "http://www.tei-c.org/ns/1.0"
TEI_NS = {"tei": TEI_NAMESPACE}
