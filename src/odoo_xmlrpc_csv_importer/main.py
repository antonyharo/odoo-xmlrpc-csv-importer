from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from odoo_xmlrpc_csv_importer.application.import_contacts import import_contacts
from odoo_xmlrpc_csv_importer.infrastructure.config import get_settings
from odoo_xmlrpc_csv_importer.infrastructure.csv_manager import CsvManager
from odoo_xmlrpc_csv_importer.infrastructure.import_stats import ImportStats
from odoo_xmlrpc_csv_importer.infrastructure.odoo_client import OdooClient
from odoo_xmlrpc_csv_importer.services.reference_cache import ReferenceCache

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
    ] = 4,
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

        reference_cache = ReferenceCache(COUNTRY_CACHE, STATE_CACHE)

        import_stats = ImportStats(max_workers=max_workers)

        csv_manager = CsvManager(
            file_name, settings.dlq_file, import_stats=import_stats
        )

        console.print(
            Panel.fit(
                Text.assemble(
                    ("etl ", "bold cyan"),
                    ("· importação de contatos Odoo (XML-RPC)", "bold white"),
                ),
                subtitle=f"{file_name.name}  ·  {max_workers} threads  ·  lote {batch_size}",
                border_style="cyan",
            )
        )

        import_contacts(
            file_name=file_name,
            max_workers=max_workers,
            batch_size=batch_size,
            odoo_client=odoo_client,
            csv_manager=csv_manager,
            reference_cache=reference_cache,
            import_stats=import_stats,
            console=console,
        )
    except Exception as e:
        console.print(f"\n[bold red]Erro fatal:[/] {e}")


if __name__ == "__main__":
    app()
