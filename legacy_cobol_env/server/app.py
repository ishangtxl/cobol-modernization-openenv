"""FastAPI app for the Legacy COBOL Migration Workbench."""

from __future__ import annotations

import os
from threading import RLock

from fastapi import Body, HTTPException, status
from openenv.core.env_server.http_server import (
    ResetRequest,
    ResetResponse,
    StepRequest,
    StepResponse,
    create_app,
)
from openenv.core.env_server.mcp_types import ListToolsAction
from openenv.core.env_server.serialization import serialize_observation
from pydantic import ValidationError

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

_rest_env = LegacyCobolEnvironment()
_rest_lock = RLock()


def _remove_routes(paths: set[str]) -> None:
    app.router.routes = [
        route for route in app.router.routes if getattr(route, "path", None) not in paths
    ]


def _rest_action(action_data: dict[str, object]) -> ToolActionWrapper | ListToolsAction:
    try:
        if action_data.get("type") == "list_tools":
            return ListToolsAction.model_validate(action_data)
        return ToolActionWrapper.model_validate(action_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


def _install_persistent_rest_routes() -> None:
    _remove_routes({"/reset", "/step", "/state"})

    @app.post("/reset", response_model=ResetResponse, tags=["Environment Control"])
    async def reset(
        request: ResetRequest = Body(default_factory=ResetRequest),
    ) -> ResetResponse:
        kwargs = request.model_dump(exclude_unset=True)
        with _rest_lock:
            observation = _rest_env.reset(**kwargs)
        return ResetResponse(**serialize_observation(observation))

    @app.post("/step", response_model=StepResponse, tags=["Environment Control"])
    async def step(request: StepRequest) -> StepResponse:
        action = _rest_action(request.action)
        kwargs = request.model_dump(exclude_unset=True, exclude={"action"})
        with _rest_lock:
            observation = _rest_env.step(action, **kwargs)
        return StepResponse(**serialize_observation(observation))

    @app.get("/state", response_model=LegacyCobolState, tags=["State Management"])
    async def get_state() -> LegacyCobolState:
        with _rest_lock:
            return _rest_env.state.model_copy(deep=True)


def _install_project_schema_route() -> None:
    _remove_routes({"/schema"})

    @app.get("/schema", tags=["Schema"])
    async def get_project_schemas() -> dict[str, object]:
        return {
            "action": ToolActionWrapper.model_json_schema(),
            "observation": ToolObservationWrapper.model_json_schema(),
            "state": LegacyCobolState.model_json_schema(),
        }


_install_persistent_rest_routes()
_install_project_schema_route()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
