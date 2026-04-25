"""FastAPI app for the Legacy COBOL Migration Workbench."""

from __future__ import annotations

import os

from openenv.core.env_server.http_server import create_app

try:
    from ..models import LegacyCobolState, ToolActionWrapper, ToolObservationWrapper
    from .legacy_cobol_env_environment import LegacyCobolEnvironment
except ImportError:
    from models import LegacyCobolState, ToolActionWrapper, ToolObservationWrapper
    from server.legacy_cobol_env_environment import LegacyCobolEnvironment


max_concurrent = int(os.getenv("MAX_CONCURRENT_ENVS", "4"))

app = create_app(
    LegacyCobolEnvironment,
    ToolActionWrapper,
    ToolObservationWrapper,
    env_name="legacy_cobol_env",
    max_concurrent_envs=max_concurrent,
)


def _install_project_schema_route() -> None:
    app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/schema"]

    @app.get("/schema", tags=["Schema"])
    async def get_project_schemas() -> dict[str, object]:
        return {
            "action": ToolActionWrapper.model_json_schema(),
            "observation": ToolObservationWrapper.model_json_schema(),
            "state": LegacyCobolState.model_json_schema(),
        }


_install_project_schema_route()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
