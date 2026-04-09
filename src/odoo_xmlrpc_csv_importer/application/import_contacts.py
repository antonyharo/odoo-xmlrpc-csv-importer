import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console

from odoo_xmlrpc_csv_importer.application.ui import (
    build_import_progress,
    print_summary_table,
)
from odoo_xmlrpc_csv_importer.core.chunker import chunker
from odoo_xmlrpc_csv_importer.infrastructure.import_stats import ImportStats
from odoo_xmlrpc_csv_importer.infrastructure.logger import logger


def search_existing_emails(batch: list, models, odoo_client) -> set:
    emails_to_search: set = {c["email"] for c in batch}

    records_db: list = odoo_client.search_records(models, emails_to_search)
    return {r["email"].lower() for r in records_db if r.get("email")}


def process_batch(
    batch: list,
    odoo_client,
    csv_manager,
    reference_cache,
    import_stats: ImportStats | None,
) -> None:
    """Process batch of contacts and orquestrates deduplication, cache and load in Odoo"""
    if import_stats is not None:
        import_stats.worker_enter()
    try:
        start_time = time.time()

        contacts_to_create: list[dict] = []

        # Each thread creates its own models proxy
        models = xmlrpc.client.ServerProxy(f"{odoo_client.url}/xmlrpc/2/object")

        existing_emails: set = search_existing_emails(batch, models, odoo_client)

        # Sanitize data to get reference ids and filter records that already exists in db
        for contact in batch:
            if contact["email"] in existing_emails:
                continue

            contact["country_id"], contact["state_id"] = (
                reference_cache.get_contact_reference_ids(
                    state_name=contact["state_id"],
                    country_name=contact["country_id"],
                    odoo_client=odoo_client,
                    models=models,
                )
            )

            contacts_to_create.append(contact)

        if contacts_to_create:
            odoo_client.create_contacts(models, contacts_to_create)

        skipped_odoo = len(batch) - len(contacts_to_create)
        if import_stats is not None:
            import_stats.record_batch_success(
                created=len(contacts_to_create),
                skipped_odoo=skipped_odoo,
            )

        logger.debug(
            "lote_processado",
            criados=len(contacts_to_create),
            ignorados_odoo=skipped_odoo,
            segundos=round(time.time() - start_time, 2),
        )

    except Exception as e:
        logger.error(f"Erro no lote: {e}")
        csv_manager.log_to_dlq(batch, str(e))
        if import_stats is not None:
            import_stats.record_batch_failure(len(batch))

    finally:
        if import_stats is not None:
            import_stats.worker_exit()


def import_contacts(
    *,
    file_name: Path,
    max_workers: int,
    batch_size: int,
    odoo_client,
    csv_manager,
    reference_cache,
    import_stats: ImportStats,
    console: Console,
) -> None:
    wall_start = time.perf_counter()

    logger.info("lendo_arquivo", path=str(file_name))

    contacts_stream = csv_manager.stream_csv_contacts()

    started_at = time.monotonic()
    progress = build_import_progress(import_stats, started_at)

    with progress:
        batch_task = progress.add_task("[cyan]Lotes[/] — enfileirando…", total=None)
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch in chunker(contacts_stream, batch_size):
                futures.append(
                    executor.submit(
                        process_batch,
                        batch,
                        odoo_client,
                        csv_manager,
                        reference_cache,
                        import_stats,
                    )
                )
                progress.update(
                    batch_task,
                    description=f"[cyan]Lotes[/] — {len(futures):,} na fila",
                )

            total = len(futures)
            if total == 0:
                progress.update(
                    batch_task,
                    total=1,
                    completed=1,
                    description="[yellow]Nenhum lote (CSV vazio ou só inválidos)[/]",
                )
            else:
                progress.update(
                    batch_task,
                    total=total,
                    completed=0,
                    description="[cyan]Lotes processados[/]",
                )
                for fut in as_completed(futures):
                    fut.result()
                    progress.advance(batch_task)

    wall_seconds = time.perf_counter() - wall_start
    logger.info("importacao_finalizada", segundos=round(wall_seconds, 2))
    print_summary_table(
        console,
        import_stats,
        wall_seconds=wall_seconds,
        file_name=file_name,
        batch_size=batch_size,
        max_workers=max_workers,
    )
