from application import odoo_etl
from typing import Annotated

import time
import typer


def main(
    file_name: Annotated[str, typer.Argument(help=".CSV file to import.")],
    batch_size: Annotated[
        int, typer.Option(help="Total of contacts to create in each batch")
    ] = 1000,
    max_workers: Annotated[
        int,
        typer.Option(help="Total of threads to perform in contacts creation."),
    ] = 4,
):
    start_time = time.time()
    odoo_etl(file_name, max_workers, batch_size)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Tempo de execução: {elapsed_time:.2f} segundos")


if __name__ == "__main__":
    typer.run(main)
