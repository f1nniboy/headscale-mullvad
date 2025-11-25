import base64
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from .config import MAX_WORKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=True, markup=True)],
    force=True,
)
logger = logging.getLogger(__name__)


def wg2nodekey(wg_key):
    try:
        return "nodekey:" + base64.b64decode(wg_key + "==")[-32:].hex()
    except Exception:
        return None


def nodekey2wg(node_key):
    try:
        clean = node_key.strip().removeprefix("nodekey:")
        return (
            base64.b64encode(bytes.fromhex(clean)).decode()
            if len(clean) == 64
            else None
        )
    except Exception:
        return None


def parse_filters(raw_str):
    return {c.strip().lower() for c in raw_str.split(",")} if raw_str else None


def run_tasks(desc, func, items, get_name):
    if not items:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task_id = progress.add_task(desc, total=len(items))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exc:
            futures = {exc.submit(func, i): i for i in items}
            for f in as_completed(futures):
                progress.advance(task_id)
                try:
                    f.result()
                except Exception as e:
                    logger.error(
                        f"Error [bold]{get_name(futures[f])}[/bold]: [bold]{e}[/bold]"
                    )


def print_table(title, columns, rows):
    if not rows:
        return

    table = Table(title=title)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(item) for item in row])

    Console().print(table)
