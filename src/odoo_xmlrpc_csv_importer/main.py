from typing import Annotated

import typer

from odoo_xmlrpc_csv_importer.application.odoo_etl import odoo_etl
from odoo_xmlrpc_csv_importer.infrastructure.config import get_settings

app = typer.Typer()

settings = get_settings()


@app.command()
def main(
    file_name: Annotated[str, typer.Argument(help=".CSV file to import.")],
    batch_size: Annotated[
        int, typer.Option(help="Total of contacts to create in each batch")
    ] = 1000,
    max_workers: Annotated[
        int,
        typer.Option(help="Total of threads to perform in contacts creation."),
    ] = 4,
) -> None:
    odoo_etl(settings, file_name, max_workers, batch_size)


if __name__ == "__main__":
    app()
