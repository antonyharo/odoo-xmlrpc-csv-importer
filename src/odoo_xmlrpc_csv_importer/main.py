from pathlib import Path
from typing import Annotated

import typer

from odoo_xmlrpc_csv_importer.application.import_contacts import import_contacts
from odoo_xmlrpc_csv_importer.infrastructure.config import get_settings
from odoo_xmlrpc_csv_importer.infrastructure.csv_manager import CsvManager
# from odoo_xmlrpc_csv_importer.infrastructure.logger import configure_logger, logger
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
    try:
        settings = get_settings()

        odoo_client = OdooClient(
            url=settings.url,
            db=settings.db,
            username=settings.username,
            password=settings.password.get_secret_value(),
        )

        reference_cache = ReferenceCache(COUNTRY_CACHE, STATE_CACHE)

        csv_manager = CsvManager(file_name, settings.dlq_file)

        if not odoo_client.uid:
            raise PermissionError(
                "Falha na autenticação do Odoo. Verifique as suas credenciais."
            )

        import_contacts(
            file_name=file_name,
            max_workers=max_workers,
            batch_size=batch_size,
            odoo_client=odoo_client,
            csv_manager=csv_manager,
            reference_cache=reference_cache,
        )
    except Exception as e:
        typer.secho(f"\nErro Fatal: {e}", fg=typer.colors.RED, bold=True, err=True)


if __name__ == "__main__":
    app()
