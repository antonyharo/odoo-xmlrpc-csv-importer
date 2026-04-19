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


def _search_existing_emails(emails: list | set, models, odoo_client) -> set:
    results: list = odoo_client.search_records(models, emails)
    return {r["email"].lower() for r in results if r.get("email")}


def filter_contacts(batch: list, models, odoo_client) -> list:
    """Filter contacts based on existing emails in Odoo"""
    existing_emails: set = _search_existing_emails({c["email"] for c in batch}, models, odoo_client)
    return [contact for contact in batch if contact["email"] not in existing_emails]


def enrich_contacts(contacts, reference_cache, odoo_client, models) -> list:
    """Sanitize data to get reference ids and filter records that already exists in db"""
    enriched_contacts = []
    
    for contact in contacts:
        contact["country_id"], contact["state_id"] = (
            reference_cache.get_contact_reference_ids(
                state_name=contact["state_id"],
                country_name=contact["country_id"],
                odoo_client=odoo_client,
                models=models,
            )
        )

        enriched_contacts.append(contact)

    return enriched_contacts


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

        # Each thread creates its own models proxy
        models = xmlrpc.client.ServerProxy(f"{odoo_client.url}/xmlrpc/2/object")
        
        filtered_contacts = filter_contacts(batch, models, odoo_client)
        enriched_contacts = enrich_contacts(filtered_contacts, reference_cache, odoo_client, models)

        if enriched_contacts:
            odoo_client.create_contacts(models, enriched_contacts)

        skipped_odoo = len(batch) - len(enriched_contacts)
        
        if import_stats is not None:
            import_stats.record_batch_success(
                created=len(enriched_contacts),
                skipped_odoo=skipped_odoo,
            )

        logger.debug(
            "batch_processed",
            created=len(enriched_contacts),
            ingored=skipped_odoo,
            seconds=round(time.time() - start_time, 2),
        )

    except Exception as e:
        logger.error(e)
        csv_manager.log_to_dlq(batch, str(e))
        import_stats.record_batch_failure(len(batch))

    finally:
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
    logger.info("success", segundos=round(wall_seconds, 2))
    print_summary_table(
        console,
        import_stats,
        wall_seconds=wall_seconds,
        file_name=file_name,
        batch_size=batch_size,
        max_workers=max_workers,
    )
