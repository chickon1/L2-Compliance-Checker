"""REST API for the compliance workspace."""

from __future__ import annotations

from typing import List, Optional

import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .auth import SESSION_COOKIE_NAME
from .models import (
    AuthCredentials,
    AuthStatus,
    ComplianceRun,
    CredentialProfile,
    CredentialProfileCreate,
    CredentialProfileUpdate,
    Device,
    DeviceChanges,
    DeviceCheckResult,
    DeviceCreate,
    DiscoveredHost,
    ImportDevicesRequest,
    ResultOverride,
    ResultOverrideCreate,
    Role,
    Rule,
    ScanRequest,
    ScheduleSettings,
    Site,
    SiteCreate,
    User,
    UserCreate,
    UserUpdate,
)
from .repository import Repository
from .scheduler import ComplianceScheduler
from .service import ComplianceService


class RunRequest(BaseModel):
    device_ids: Optional[List[str]] = None


def create_auth_dependencies(repository: Repository):
    """Returns (get_current_user, require_admin) FastAPI dependencies bound
    to this repository — same closure-over-state style create_router()
    already uses for `service`/`scheduler`, since there's no Depends()-based
    DI container elsewhere in this codebase to hook into."""

    def get_current_user(request: Request) -> User:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = repository.get_session_user(token) if token else None
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    def require_admin(user: User = Depends(get_current_user)) -> User:
        if user.role != Role.ADMIN:
            raise HTTPException(status_code=403, detail="Admin role required")
        return user

    return get_current_user, require_admin


def create_auth_router(repository: Repository) -> APIRouter:
    """Unauthenticated by design — these are exactly the routes you need to
    be able to reach *without* already having a session."""
    router = APIRouter(prefix="/api/v1/auth")

    @router.get("/status", response_model=AuthStatus)
    def status(request: Request) -> AuthStatus:
        setup_required = len(repository.list_users()) == 0
        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = repository.get_session_user(token) if token else None
        return AuthStatus(setup_required=setup_required, authenticated=user is not None, user=user)

    @router.post("/setup", response_model=User)
    def setup(credentials: AuthCredentials, response: Response) -> User:
        if repository.list_users():
            raise HTTPException(status_code=409, detail="Setup has already been completed")
        user = User(id=str(uuid.uuid4()), username=credentials.username, role=Role.ADMIN)
        repository.add_user(user, credentials.password)
        _set_session_cookie(response, repository.create_session(user.id))
        return user

    @router.post("/login", response_model=User)
    def login(credentials: AuthCredentials, response: Response) -> User:
        user = repository.verify_login(credentials.username, credentials.password)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        _set_session_cookie(response, repository.create_session(user.id))
        return user

    @router.post("/logout", status_code=204)
    def logout(request: Request, response: Response) -> None:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            repository.delete_session(token)
        response.delete_cookie(SESSION_COOKIE_NAME)

    return router


def _set_session_cookie(response: Response, token: str) -> None:
    # No `secure=True`: the packaged desktop build serves plain HTTP over
    # loopback only, where a Secure cookie would silently never be sent.
    # See packaging/README.md's hardening notes.
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )


def create_router(
    service: ComplianceService,
    repository: Repository,
    scheduler: Optional[ComplianceScheduler] = None,
) -> APIRouter:
    get_current_user, require_admin = create_auth_dependencies(repository)
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])

    @router.get("/devices", response_model=List[Device])
    def list_devices() -> List[Device]:
        return service.devices()

    @router.post("/devices/import", response_model=List[Device])
    def import_devices(request: ImportDevicesRequest) -> List[Device]:
        return service.import_devices(request.devices)

    @router.patch("/devices/{device_id}", response_model=Device)
    def update_device(device_id: str, request: DeviceCreate) -> Device:
        try:
            return service.update_device(device_id, request)
        except KeyError:
            raise HTTPException(status_code=404, detail="Device not found")

    @router.delete("/devices/{device_id}", status_code=204)
    def delete_device(device_id: str) -> None:
        try:
            service.delete_device(device_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Device not found")

    @router.get("/rules", response_model=List[Rule])
    def list_rules() -> List[Rule]:
        return service.rules()

    @router.post("/checks/run", response_model=ComplianceRun)
    def run_checks(request: RunRequest) -> ComplianceRun:
        return service.run(request.device_ids)

    @router.get("/checks/results", response_model=Optional[ComplianceRun])
    def latest_results() -> Optional[ComplianceRun]:
        return service.latest_run()

    @router.get("/checks/results/{device_id}", response_model=DeviceCheckResult)
    def device_results(device_id: str) -> DeviceCheckResult:
        run = service.latest_run()
        if run is None:
            raise HTTPException(status_code=404, detail="No runs yet")
        for result in run.device_results:
            if result.device_id == device_id:
                return result
        raise HTTPException(status_code=404, detail="No results for this device")

    @router.get("/checks/results/{device_id}/changes", response_model=Optional[DeviceChanges])
    def device_changes(device_id: str) -> Optional[DeviceChanges]:
        return service.changes_for_device(device_id)

    @router.get("/schedule", response_model=ScheduleSettings)
    def get_schedule() -> ScheduleSettings:
        if scheduler is None:
            raise HTTPException(status_code=404, detail="Scheduler not available")
        return scheduler.get_settings()

    @router.put("/schedule", response_model=ScheduleSettings)
    def update_schedule(request: ScheduleSettings) -> ScheduleSettings:
        if scheduler is None:
            raise HTTPException(status_code=404, detail="Scheduler not available")
        return scheduler.update_settings(request)

    @router.get("/credential-profiles", response_model=List[CredentialProfile])
    def list_credential_profiles() -> List[CredentialProfile]:
        return service.list_credential_profiles()

    @router.post("/credential-profiles", response_model=CredentialProfile)
    def create_credential_profile(request: CredentialProfileCreate) -> CredentialProfile:
        return service.create_credential_profile(request)

    @router.patch("/credential-profiles/{profile_id}", response_model=CredentialProfile)
    def update_credential_profile(
        profile_id: str, request: CredentialProfileUpdate
    ) -> CredentialProfile:
        try:
            return service.update_credential_profile(profile_id, request)
        except KeyError:
            raise HTTPException(status_code=404, detail="Credential profile not found")

    @router.delete("/credential-profiles/{profile_id}", status_code=204)
    def delete_credential_profile(profile_id: str) -> None:
        try:
            service.delete_credential_profile(profile_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Credential profile not found")

    @router.get("/sites", response_model=List[Site])
    def list_sites() -> List[Site]:
        return service.list_sites()

    @router.post("/sites", response_model=Site)
    def create_site(request: SiteCreate) -> Site:
        return service.create_site(request)

    @router.post("/discovery/scan", response_model=List[DiscoveredHost])
    def scan(request: ScanRequest) -> List[DiscoveredHost]:
        return service.scan(request.range, request.credential_profile_id, request.port)

    @router.post(
        "/devices/{device_id}/results/{rule_id}/override", response_model=ResultOverride
    )
    def create_override(
        device_id: str, rule_id: str, request: ResultOverrideCreate
    ) -> ResultOverride:
        return service.create_override(device_id, rule_id, request.comment)

    @router.delete("/devices/{device_id}/results/{rule_id}/override", status_code=204)
    def clear_override(device_id: str, rule_id: str) -> None:
        service.clear_override(device_id, rule_id)

    @router.get("/users", response_model=List[User], dependencies=[Depends(require_admin)])
    def list_users() -> List[User]:
        return repository.list_users()

    @router.post("/users", response_model=User, dependencies=[Depends(require_admin)])
    def create_user(request: UserCreate) -> User:
        user = User(id=str(uuid.uuid4()), username=request.username, role=request.role)
        try:
            repository.add_user(user, request.password)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists")
        return user

    @router.patch("/users/{user_id}", response_model=User, dependencies=[Depends(require_admin)])
    def update_user(user_id: str, request: UserUpdate) -> User:
        try:
            repository.update_user(user_id, request.username, request.role, request.password)
        except KeyError:
            raise HTTPException(status_code=404, detail="User not found")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists")
        return repository.get_user(user_id)

    @router.delete("/users/{user_id}", status_code=204, dependencies=[Depends(require_admin)])
    def delete_user(user_id: str) -> None:
        try:
            repository.delete_user(user_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="User not found")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    return router
