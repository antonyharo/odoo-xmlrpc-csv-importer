from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ImportStats:
    """Thread safe counters to follow up import stats."""

    max_workers: int
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    active_workers: int = 0
    validation_errors: int = 0
    batches_completed: int = 0
    batch_errors: int = 0
    contacts_created: int = 0
    contacts_skipped_odoo: int = 0
    contacts_in_failed_batches: int = 0

    def worker_enter(self) -> None:
        with self._lock:
            self.active_workers += 1

    def worker_exit(self) -> None:
        with self._lock:
            self.active_workers = max(0, self.active_workers - 1)

    def record_validation_error(self) -> None:
        with self._lock:
            self.validation_errors += 1

    def record_batch_success(self, *, created: int, skipped_odoo: int) -> None:
        with self._lock:
            self.batches_completed += 1
            self.contacts_created += created
            self.contacts_skipped_odoo += skipped_odoo

    def record_batch_failure(self, batch_rows: int) -> None:
        with self._lock:
            self.batches_completed += 1
            self.batch_errors += 1
            self.contacts_in_failed_batches += batch_rows

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "active_workers": self.active_workers,
                "max_workers": self.max_workers,
                "validation_errors": self.validation_errors,
                "batches_completed": self.batches_completed,
                "batch_errors": self.batch_errors,
                "contacts_created": self.contacts_created,
                "contacts_skipped_odoo": self.contacts_skipped_odoo,
                "contacts_in_failed_batches": self.contacts_in_failed_batches,
            }
