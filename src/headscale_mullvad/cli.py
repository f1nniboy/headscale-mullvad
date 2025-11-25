import json
import logging
import sys

import typer

from headscale_mullvad.config import MULLVAD_NODE_PREFIX

from .api import HeadscaleClient, MullvadClient
from .utils import (
    nodekey2wg,
    parse_filters,
    print_table,
    run_tasks,
    wg2nodekey,
)

logger = logging.getLogger(__name__)


class State:
    def __init__(self):
        self._hs = None
        self._mv = None

    @property
    def hs(self) -> HeadscaleClient:
        if self._hs is None:
            self._hs = HeadscaleClient()
        return self._hs

    @property
    def mv(self) -> MullvadClient:
        if self._mv is None:
            self._mv = MullvadClient()
        return self._mv


app = typer.Typer()
relay_app = typer.Typer()
app.add_typer(relay_app, name="relay")
node_app = typer.Typer()
app.add_typer(node_app, name="node")


@app.callback()
def main(ctx: typer.Context):
    ctx.obj = State()


@relay_app.command("list")
def relay_list(ctx: typer.Context):
    """
    List all Mullvad relays in Headscale.
    """
    hs = ctx.obj.hs
    relays = hs.list_relays()
    rows = []
    for relay in relays:
        try:
            extra_config = json.loads(relay.get("extraConfig", "{}"))
            location = extra_config.get("location", {})
        except json.JSONDecodeError:
            location = {}

        rows.append(
            (
                relay.get("id"),
                relay.get("name"),
                location.get("Country"),
                location.get("City"),
            )
        )
    print_table(
        "Mullvad relays",
        ["ID", "Name", "Country", "City"],
        rows,
    )


@relay_app.command("add")
def relay_add(
    ctx: typer.Context,
    id: int | None = typer.Option(
        None, "--id", "-i", help="Headscale user to create relays with"
    ),
    name: str | None = typer.Option(
        None, "--name", "-n", help="Headscale user to create relays with"
    ),
    countries=typer.Option(
        None, "--countries", "-c", help="Comma-separated list of country codes to add"
    ),
):
    """
    Add Mullvad relays to Headscale.
    """
    if id is None and name is None:
        logger.error("Either [bold]--id[/bold] or [bold]--name[/bold] must be provided")
        sys.exit(1)
    if id is not None and name is not None:
        logger.error("Cannot provide both [bold]--id[/bold] and [bold]--name[/bold]")
        sys.exit(1)

    hs = ctx.obj.hs
    mv = ctx.obj.mv

    user_id_to_use = id
    if name:
        user = hs.get_user_by_name(name)
        if not user:
            logger.error(f"User [bold]{name}[/bold] not found")
            sys.exit(1)
        user_id_to_use = user["id"]

    if not countries:
        if not typer.confirm(
            "This will fetch all Mullvad relays and may take a while. Do you want to continue?",
            default=False,
            abort=True,
        ):
            sys.exit(0)

    logger.info("Fetching Mullvad relays")
    mullvad_relays_from_mv = mv.relays()
    existing_headscale_relays = {p["name"] for p in hs.list_relays()}

    filters = parse_filters(countries)
    tasks = []

    for country_data in mullvad_relays_from_mv.get("countries", []):
        code = country_data.get("code", "").lower()
        if filters and code not in filters:
            continue

        for city_data in country_data.get("cities", []):
            for r in city_data.get("relays", []):
                hostname = MULLVAD_NODE_PREFIX + r.get("hostname")
                if hostname in existing_headscale_relays:
                    continue

                public_key = r.get("public_key", "")
                nk = wg2nodekey(public_key) if public_key else None
                if not nk:
                    continue

                eps = [f"{r['ipv4_addr_in']}:51820", f"[{r['ipv6_addr_in']}]:51820"]

                extra = {
                    "suggestExitNode": True,
                    "location": {
                        "Country": country_data.get("name"),
                        "CountryCode": country_data.get("code"),
                        "City": f"{city_data.get('name')} ({r.get('hostname')})",
                        "CityCode": city_data.get("code"),
                        "Latitude": city_data.get("latitude"),
                        "Longitude": city_data.get("longitude"),
                    },
                }

                tasks.append(
                    {
                        "name": hostname,
                        "userId": user_id_to_use,
                        "publicKey": nk,
                        "allowedIps": ["0.0.0.0/0", "::/0"],
                        "endpoints": eps,
                        "extraConfig": json.dumps(extra),
                    }
                )

    if not tasks:
        logger.info("No new relays to register")
        return

    run_tasks(
        f"Registering [bold]{len(tasks)}[/bold] relays",
        hs.register_relay,
        tasks,
        lambda t: t["name"],
    )


@relay_app.command("delete")
def relay_delete(
    ctx: typer.Context,
    countries=typer.Option(
        None,
        "--countries",
        "-c",
        help="Comma-separated list of country codes to delete",
    ),
):
    """
    Delete Mullvad relays from Headscale.
    """
    hs = ctx.obj.hs
    relays = hs.list_relays()
    filters = parse_filters(countries)
    to_delete = []

    for relay in relays:
        country_code = None
        try:
            extra_config = json.loads(relay.get("extraConfig", "{}"))
            location = extra_config.get("location", {})
            country_code = location.get("countryCode", "").lower()
        except (json.JSONDecodeError, AttributeError):
            country_code = None

        if filters and country_code and country_code not in filters:
            continue

        to_delete.append(relay)

    if not to_delete:
        logger.info("No relays to delete")
        return

    # First, delete connections to these relays
    all_connections = hs.get_connections()
    relay_ids_to_delete = {str(r["id"]) for r in to_delete}
    conns_to_delete = [
        c for c in all_connections if str(c["wgPeerId"]) in relay_ids_to_delete
    ]

    if conns_to_delete:
        run_tasks(
            f"Deleting [bold]{len(conns_to_delete)}[/bold] connections",
            lambda c: hs.delete_connection(str(c["nodeId"]), str(c["wgPeerId"])),
            conns_to_delete,
            lambda c: f"conn-{c['nodeId']}-{c['wgPeerId']}",
        )

    run_tasks(
        f"Deleting [bold]{len(to_delete)}[/bold] relays",
        lambda r: hs.delete_relay(str(r["id"])),
        to_delete,
        lambda r: r["name"],
    )


@node_app.command("list")
def node_list(ctx: typer.Context):
    """
    List all nodes and their VPN access status.
    """
    hs = ctx.obj.hs
    nodes = hs.list_nodes()
    mullvad_relays = {str(r["id"]) for r in hs.list_relays()}
    connections = hs.get_connections()

    rows = []
    for node in nodes:
        node_id = str(node["id"])
        node_connections = {
            str(c["wgPeerId"]) for c in connections if str(c["nodeId"]) == node_id
        }

        has_all_connections = mullvad_relays.issubset(node_connections)

        status = "[green]✔[/green]" if has_all_connections else "[red]✘[/red]"
        rows.append(
            (
                node["id"],
                node.get("givenName", node.get("name")),
                node["user"]["name"],
                status,
            )
        )

    print_table(
        "Nodes",
        ["ID", "Name", "User", "Access"],
        rows,
    )


def get_node_or_fail(hs: HeadscaleClient, id: int | None, name: str | None):
    if id is None and name is None:
        logger.error("Either [bold]--id[/bold] or [bold]--name[/bold] must be provided")
        sys.exit(1)
    if id is not None and name is not None:
        logger.error("Cannot provide both [bold]--id[/bold] and [bold]--name[/bold]")
        sys.exit(1)

    node = None
    if name:
        node = hs.get_node_by_name(name)
        if not node:
            logger.error(f"Node [bold]{name}[/bold] not found")
            sys.exit(1)
    else:
        node = hs.get_node_by_id(id)
        if not node:
            logger.error(f"Node with ID [bold]{id}[/bold] not found")
            sys.exit(1)
    return node


@node_app.command("add")
def node_add(
    ctx: typer.Context,
    id: int | None = typer.Option(None, "--id", "-i", help="The ID of the node to add"),
    name: str | None = typer.Option(
        None, "--name", "-n", help="The name of the node to add"
    ),
):
    """
    Add a node to Mullvad and create relay connections.
    """
    hs = ctx.obj.hs
    mv = ctx.obj.mv

    node = get_node_or_fail(hs, id, name)

    node_id = str(node["id"])

    logger.info(f"Adding node [bold]{node.get('givenName')}[/bold] to Mullvad")

    node_key_wg = nodekey2wg(node.get("nodeKey"))
    if not node_key_wg:
        logger.error("Couldn't convert nodekey to WireGuard key")
        sys.exit(1)

    try:
        ipv4, ipv6 = mv.auth(node_key_wg)
    except Exception as e:
        logger.error(f"Failed to add node to Mullvad: [bold]{e}[/bold]")
        sys.exit(1)

    logger.info("Creating relay connections")

    mullvad_relays = hs.list_relays()

    connections = hs.get_connections()
    node_connections = {
        str(c["wgPeerId"]) for c in connections if str(c["nodeId"]) == node_id
    }

    tasks = []
    for relay in mullvad_relays:
        if str(relay["id"]) not in node_connections:
            tasks.append(
                {
                    "nodeId": node_id,
                    "wgPeerId": str(relay["id"]),
                    "ipv4MasqAddr": ipv4,
                    "ipv6MasqAddr": ipv6,
                }
            )

    if not tasks:
        logger.info("All connections are already up-to-date")
        return

    run_tasks(
        f"Creating [bold]{len(tasks)}[/bold] connections",
        hs.create_connection,
        tasks,
        lambda t: f"conn-{t['wgPeerId']}",
    )


@node_app.command("delete")
def node_delete(
    ctx: typer.Context,
    id: int | None = typer.Option(
        None, "--id", "-i", help="The ID of the node to delete connections for"
    ),
    name: str | None = typer.Option(
        None, "--name", "-n", help="The name of the node to delete connections for"
    ),
):
    """
    Delete relay connections for a specific node.
    """
    hs = ctx.obj.hs

    node = get_node_or_fail(hs, id, name)
    node_id = str(node["id"])

    logger.info(f"Deleting connections for node [bold]{node.get('givenName')}[/bold]")

    connections = hs.get_connections()
    mullvad_relay_ids = {str(r["id"]) for r in hs.list_relays()}

    to_delete = []
    for conn in connections:
        if (
            str(conn["nodeId"]) == node_id
            and str(conn["wgPeerId"]) in mullvad_relay_ids
        ):
            to_delete.append(conn)

    if not to_delete:
        logger.info("No connections to delete")
        return

    run_tasks(
        f"Deleting [bold]{len(to_delete)}[/bold] connections",
        lambda c: hs.delete_connection(str(c["nodeId"]), str(c["wgPeerId"])),
        to_delete,
        lambda c: str(c["wgPeerId"]),
    )

    logger.warning("You must manually remove this device from your Mullvad account")
    logger.warning(
        "  [bold]-[/bold] Go to [bold][link=https://mullvad.net/account/devices]mullvad.net/account/devices[/link][/bold]"
    )
    logger.warning(
        f"  [bold]-[/bold] Remove device with public key [bold]{nodekey2wg(node.get('nodeKey'))}[/bold]"
    )


if __name__ == "__main__":
    app()
