"""REST API for the compliance workspace."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .models import (
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
    Rule,
    ScanRequest,
    ScheduleSettings,
    Site,
    SiteCreate,
)
from .scheduler import ComplianceScheduler
from .service import ComplianceService


class RunRequest(BaseModel):
    device_ids: Optional[List[str]] = None


def create_router(service: ComplianceService, scheduler: Optional[ComplianceScheduler] = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

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

    return router
