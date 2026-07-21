"""App factories wiring config, repository, collector, and the API together."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import create_router
from .collectors.mock import MockConfigCollector
from .collectors.ssh import ConfigCollector, SshConfigCollector
from .config import load_settings
from .models import Device, Platform
from .repository import Repository
from .rule_loader import load_rules
from .scheduler import ComplianceScheduler
from .service import ComplianceService

_MOCK_DEVICES = [
    Device(
        id=str(uuid.uuid4()),
        name="mock-iosxe-1",
        management_address="192.0.2.11",
        platform=Platform.CISCO_IOS,
        site="Mock",
    ),
    Device(
        id=str(uuid.uuid4()),
        name="mock-nxos-1",
        management_address="192.0.2.12",
        platform=Platform.CISCO_NXOS,
        site="Mock",
    ),
]


def _frontend_dist_dir() -> Path:
    """Where the built frontend lives — bundled path when frozen by
    PyInstaller for the standalone desktop app, or `frontend/dist` next to
    the source tree when built with `npm run build` for a normal server
    deployment. Doesn't exist at all in day-to-day dev (Vite serves the
    frontend separately on :5173 in that case)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend_dist"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def _mount_frontend(app: FastAPI) -> None:
    dist_dir = _frontend_dist_dir()
    if not dist_dir.exists():
        return
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        return FileResponse(dist_dir / "index.html")


def _build_app(
    collector: ConfigCollector, repository: Repository, expose_docs: bool = True
) -> FastAPI:
    settings = load_settings()
    rules = load_rules(settings.rules_dir)
    service = ComplianceService(collector, rules, repository)
    scheduler = ComplianceScheduler(service, repository)

    app = FastAPI(
        title="Compliance Checker",
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_router(service, scheduler))
    app.state.scheduler = scheduler
    _mount_frontend(app)  # no-op unless a built frontend is present (see docstring above)

    @app.on_event("shutdown")
    def _shutdown_scheduler() -> None:
        scheduler.shutdown()

    return app


def create_application() -> FastAPI:
    """Production factory: connects to real devices over SSH.

    Starts with an empty device inventory and no credential profiles — use
    the Import page (discovery scan + bulk import) to populate both. The
    interactive API docs (/docs, /redoc, /openapi.json) are disabled here —
    this factory handles real device credentials, so there's no reason to
    expose a browsable API surface alongside it.
    """
    settings = load_settings()
    if not settings.credential_key:
        raise RuntimeError("CC_CREDENTIAL_KEY must be set to run against real devices")
    repository = Repository(settings.db_path, settings.credential_key)
    return _build_app(SshConfigCollector(), repository, expose_docs=False)


def create_mock_application() -> FastAPI:
    """Dev factory: serves canned sample configs, no SSH or lab required."""
    settings = load_settings()
    repository = Repository(settings.db_path, settings.credential_key)
    if not repository.list_devices():
        repository.add_devices(_MOCK_DEVICES)
    return _build_app(MockConfigCollector(), repository)
