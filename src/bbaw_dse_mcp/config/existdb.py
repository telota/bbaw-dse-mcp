"""eXist-db Konfiguration."""

from pydantic import BaseModel, Field


class ExistDBConfig(BaseModel):
    """Konfiguration für eXist-db Verbindung."""

    base_url: str = Field(description="Base URL der eXist-db Installation")
    app_path: str = Field(description="App collection path (for structure queries)")
    data_path: str = Field(description="Data collection path (for TEI/XML documents)")
    username: str | None = Field(default=None, description="Username für Auth")
    password: str | None = Field(default=None, description="Password für Auth")
    timeout: float = Field(default=30.0, description="Request timeout in Sekunden")

    @classmethod
    def local(
        cls,
        app_path: str = "/db",
        data_path: str | None = None,
        port: int = 8080,
        username: str = "admin",
        password: str = "",
    ) -> "ExistDBConfig":
        """Factory für lokale eXist-db Entwicklung.

        Args:
            app_path: App collection path (z.B. /db/apps/schleiermacher)
            data_path: Data collection path (optional, defaults to app_path)
            port: Port der lokalen Instanz (default: 8080)
            username: Username (default: admin)
            password: Password (default: leer)
        """
        return cls(
            base_url=f"http://localhost:{port}",
            app_path=app_path,
            data_path=data_path or app_path,
            username=username,
            password=password,
        )

    @classmethod
    def remote(
        cls,
        base_url: str,
        app_path: str,
        data_path: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> "ExistDBConfig":
        """Factory für remote eXist-db Server.

        Args:
            base_url: Base URL of the eXist-db server
            app_path: App collection path
            data_path: Data collection path (optional, defaults to app_path)
            username: Optional username for authentication
            password: Optional password for authentication
        """
        return cls(
            base_url=base_url,
            app_path=app_path,
            data_path=data_path or app_path,
            username=username,
            password=password,
        )
