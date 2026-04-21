import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from odoo_xmlrpc_csv_importer.application.use_cases.import_contacts_use_case import (
    ImportContactsUseCase,
)
from odoo_xmlrpc_csv_importer.infrastructure.config import get_settings
from odoo_xmlrpc_csv_importer.infrastructure.csv_reader import CsvReader
from odoo_xmlrpc_csv_importer.infrastructure.dlq_writer import DlqWriter
from odoo_xmlrpc_csv_importer.infrastructure.import_stats import ImportStats
from odoo_xmlrpc_csv_importer.infrastructure.odoo_client import OdooClient
from odoo_xmlrpc_csv_importer.infrastructure.reference_cache import ReferenceCache
from odoo_xmlrpc_csv_importer.presentation.ui import (
    build_import_progress,
    print_summary_table,
)

app = typer.Typer()

COUNTRY_CACHE = {}
STATE_CACHE = {}


@app.command()
def main(
    file_name: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help=".CSV file to import.",
        ),
    ],
    batch_size: Annotated[
        int, typer.Option(help="Total of contacts to create in each batch")
    ] = 1000,
    max_workers: Annotated[
        int,
        typer.Option(help="Total of threads to perform in contacts creation."),
    ] = 3,
) -> None:
    console = Console(stderr=True)
    try:
        settings = get_settings()

        odoo_client = OdooClient(
            url=settings.url,
            db=settings.db,
            username=settings.username,
            password=settings.password.get_secret_value(),
        )
        odoo_client.authenticate()
        states_and_countries_ids = odoo_client.get_states_and_countries_ids()

        reference_cache = ReferenceCache()
        reference_cache.warm_up(states_and_countries_ids)

        import_stats = ImportStats(max_workers=max_workers)

        csv_reader = CsvReader(file_name)
        dlq_writer = DlqWriter(settings.dlq_file)

        console.print(
            Panel.fit(
                Text.assemble(
                    ("etl ", "bold cyan"),
                    ("- Odoo Contact Importer", "bold white"),
                ),
                subtitle=f"{file_name.name}  ·  {max_workers} threads  ·  batch size {batch_size}",
                border_style="cyan",
            )
        )

        import_contacts_use_case = ImportContactsUseCase(
            odoo_client=odoo_client,
            csv_reader=csv_reader,
            dlq_writer=dlq_writer,
            reference_cache=reference_cache,
            import_stats=import_stats,
        )

        started_at = time.monotonic()
        progress = build_import_progress(import_stats, started_at)

        wall_start = time.perf_counter()

        with progress:
            task_id = progress.add_task("[cyan]Importing Batches...", total=None)

            import_contacts_use_case.execute(
                file_path=str(file_name), max_workers=max_workers, batch_size=batch_size
            )

            progress.update(task_id, description="[green]Success![/]")

        wall_seconds = time.perf_counter() - wall_start
        print_summary_table(
            console,
            import_stats,
            wall_seconds=wall_seconds,
            file_name=file_name,
            batch_size=batch_size,
            max_workers=max_workers,
        )

    except Exception as e:
        console.print(f"\n[bold red]Fatal Error:[/] {e}")


if __name__ == "__main__":
    app()
