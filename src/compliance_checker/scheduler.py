"""Background recurring compliance runs."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .models import ScheduleSettings
from .repository import Repository
from .service import ComplianceService

_JOB_ID = "compliance-scheduled-run"


class ComplianceScheduler:
    def __init__(self, service: ComplianceService, repository: Repository) -> None:
        self._service = service
        self._repository = repository
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._apply(repository.get_schedule_settings())

    def _apply(self, settings: ScheduleSettings) -> None:
        if self._scheduler.get_job(_JOB_ID):
            self._scheduler.remove_job(_JOB_ID)
        if settings.enabled:
            self._scheduler.add_job(
                self._service.run,
                "interval",
                hours=settings.interval_hours,
                id=_JOB_ID,
            )

    def get_settings(self) -> ScheduleSettings:
        return self._repository.get_schedule_settings()

    def update_settings(self, settings: ScheduleSettings) -> ScheduleSettings:
        self._repository.set_schedule_settings(settings)
        self._apply(settings)
        return settings

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
