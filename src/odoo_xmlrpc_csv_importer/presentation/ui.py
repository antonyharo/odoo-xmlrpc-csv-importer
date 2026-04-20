from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from odoo_xmlrpc_csv_importer.infrastructure.import_stats import ImportStats


class _StatsColumn(ProgressColumn):
    """Coluna fixa com workers ativos e taxa aproximada de criação."""

    def __init__(self, stats: ImportStats, started_at: float) -> None:
        self.stats = stats
        self.started_at = started_at
        super().__init__()

    def render(self, task) -> Text:
        s = self.stats.snapshot()
        elapsed = max(time.monotonic() - self.started_at, 1e-6)
        rate = s["contacts_created"] / elapsed
        workers = s["active_workers"]
        mx = s["max_workers"]
        return Text.from_markup(
            f"[dim]workers[/] [cyan]{workers}[/]/[cyan]{mx}[/]"
            f"[dim]created/s[/] [green]{rate:,.1f}[/]"
        )


class _ErrorsColumn(ProgressColumn):
    def __init__(self, stats: ImportStats) -> None:
        self.stats = stats
        super().__init__()

    def render(self, task) -> Text:
        s = self.stats.snapshot()
        validation_errors = s["validation_errors"]
        batch_errors = s["batch_errors"]
        style_val = "red" if validation_errors else "dim"
        style_bat = "red" if batch_errors else "dim"
        return Text.from_markup(
            f"[dim]validation_errors[/] [{style_val}]{validation_errors}[/]  "
            f"[dim]batch_errors[/] [{style_bat}]{batch_errors}[/]"
        )


def build_import_progress(stats: ImportStats, started_at: float) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        _StatsColumn(stats, started_at),
        _ErrorsColumn(stats),
        expand=True,
    )


def print_summary_table(
    console: Console,
    stats: ImportStats,
    *,
    wall_seconds: float,
    file_name: Path,
    batch_size: int,
    max_workers: int,
) -> None:
    s = stats.snapshot()
    processed_hint = (
        s["contacts_created"]
        + s["contacts_skipped_odoo"]
        + s["contacts_in_failed_batches"]
    )
    rate = s["contacts_created"] / wall_seconds if wall_seconds > 0 else 0.0

    table = Table(show_header=False, box=None)
    table.add_column(style="dim", width=28)
    table.add_column()

    table.add_row("File", str(file_name))
    table.add_row("Threads", str(max_workers))
    table.add_row("Processed Batches", f"{s['batches_completed']:,}")
    table.add_row("Batch Size", str(batch_size))
    table.add_row("Created Contacts", f"[green]{s['contacts_created']:,}[/]")
    table.add_row("Rows Already in Odoo", f"{s['contacts_skipped_odoo']:,}")
    table.add_row("Validation Errors", f"[red]{s['validation_errors']:,}[/]")
    table.add_row("Batch Errors", f"[red]{s['batch_errors']:,}[/]")
    if s["contacts_in_failed_batches"]:
        table.add_row(
            "Failed Contacts in Failed Batches",
            f"[red]{s['contacts_in_failed_batches']:,}[/]",
        )
    if processed_hint:
        table.add_row(
            "[dim]Data Volume[/]",
            f"{processed_hint:,} Valid Rows",
        )
    table.add_row("Throughtput", f"{rate:,.1f} contacts/s")
    table.add_row("Total Time", f"{wall_seconds:.1f} s")

    console.print()
    console.print(Panel(table, border_style="green", padding=(1, 2)))
