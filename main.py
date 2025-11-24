import argparse
import base64
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

load_dotenv()

MAX_WORKERS = 50

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(handler)


def wg2nodekey(wg_key):
    try:
        return "nodekey:" + base64.b64decode(wg_key + "==")[-32:].hex()
    except Exception:
        return None


def nodekey2wg(node_key):
    try:
        clean = node_key.strip().removeprefix("nodekey:")
        if len(clean) != 64:
            return None
        return base64.b64encode(bytes.fromhex(clean)).decode()
    except Exception:
        return None


def parse_filters(raw_str):
    if not raw_str:
        return None
    return {c.strip().lower() for c in raw_str.split(",") if c.strip()}


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
                    logger.error(f"Error {get_name(futures[f])}: {e}")


class MullvadClient:
    def __init__(self, account):
        if not account:
            sys.exit("MULLVAD_ACCOUNT env missing")
        self.account = account
        self.api_url = "https://api.mullvad.net"

    def relays(self):
        try:
            with urllib.request.urlopen(
                f"{self.api_url}/public/relays/wireguard/v1/"
            ) as r:
                return json.load(r)
        except Exception as e:
            sys.exit(f"Mullvad API error: {e}")

    def auth(self, pubkey):
        data = urllib.parse.urlencode(
            {"account": self.account, "pubkey": pubkey}
        ).encode()
        try:
            req = urllib.request.Request(f"{self.api_url}/wg", data=data, method="POST")
            with urllib.request.urlopen(req) as r:
                parts = r.read().decode().strip().split(",")
                if len(parts) < 2:
                    raise ValueError("Bad response")
                return parts[0].split("/")[0], parts[1].split("/")[0]
        except Exception as e:
            sys.exit(f"Mullvad auth error: {e}")


class HeadscaleClient:
    def __init__(self, url, key):
        if not key:
            sys.exit("HEADSCALE_API_KEY env missing")
        self.url = url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def req(self, path, method="GET", body=None):
        try:
            data = json.dumps(body).encode() if body else None
            req = urllib.request.Request(
                f"{self.url}{path}", data=data, method=method, headers=self.headers
            )
            with urllib.request.urlopen(req) as r:
                if r.status == 204 or method == "DELETE":
                    return None
                return json.load(r)
        except urllib.error.HTTPError as e:
            if method == "DELETE" and e.code == 404:
                return None
            logger.error(f"HTTP {e.code} {method} {path}: {e.read().decode()}")
            raise
        except Exception as e:
            logger.error(f"Headscale API request failed: {e}")
            raise

    def state(self):
        d = self.req("/api/v1/node")
        return (
            d
            if d
            else {"nodes": [], "wireguardOnlyPeers": [], "wireguardConnections": []}
        )

    def reg(self, d):
        self.req("/api/v1/wireguard-only-peer/register", "POST", d)

    def conn(self, d):
        self.req("/api/v1/wireguard/connection", "POST", d)

    def del_node(self, nid):
        self.req(f"/api/v1/node/{nid}", "DELETE")

    def del_conn(self, nid, pid):
        self.req(f"/api/v1/wireguard/connection/{nid}/{pid}", "DELETE")


class App:
    def __init__(self, args):
        self.args = args
        self.hs = HeadscaleClient(
            os.environ.get("HEADSCALE_URL"), os.environ.get("HEADSCALE_API_KEY")
        )
        self.mv = MullvadClient(os.environ.get("MULLVAD_ACCOUNT"))

    def run(self):
        if self.args.command == "clean":
            self.clean()
        elif self.args.command == "create-relays":
            self.create_relays()
        elif self.args.command == "create-connections":
            self.create_connections()

    def clean(self):
        state = self.hs.state()
        peers = state.get("wireguardOnlyPeers", [])
        filters = parse_filters(self.args.filter)

        if filters:
            peers = [p for p in peers if p.get("name", "").split("-")[0] in filters]

        if not peers:
            if filters:
                logger.info("No peers match filters")
            else:
                logger.info("No peers found")
            return

        peer_ids = {str(p["id"]) for p in peers}
        conns = [
            c
            for c in state.get("wireguardConnections", [])
            if str(c["wgPeerId"]) in peer_ids
        ]

        if conns:
            run_tasks(
                f"Deleting {len(conns)} connections",
                lambda c: self.hs.del_conn(str(c["nodeId"]), str(c["wgPeerId"])),
                conns,
                lambda c: f"{c['nodeId']}->{c['wgPeerId']}",
            )

        if peers:
            run_tasks(
                f"Deleting {len(peers)} peers",
                lambda p: self.hs.del_node(str(p["id"])),
                peers,
                lambda p: p.get("name"),
            )

    def create_relays(self):
        data = self.mv.relays()
        existing = {p["name"] for p in self.hs.state().get("wireguardOnlyPeers", [])}
        filters = parse_filters(self.args.filter)
        tasks = []

        for country in data.get("countries", []):
            code = country.get("code", "").lower()
            if filters and code not in filters:
                continue

            for city in country.get("cities", []):
                for r in city.get("relays", []):
                    hostname = r.get("hostname")
                    if hostname in existing:
                        continue

                    nk = wg2nodekey(r.get("public_key", ""))
                    if not nk:
                        continue

                    eps = [f"{r['ipv4_addr_in']}:51820"]
                    if r.get("ipv6_addr_in"):
                        eps.append(f"[{r['ipv6_addr_in']}]:51820")

                    extra = {
                        "suggestExitNode": True,
                        "location": {
                            "country": country.get("name"),
                            "countryCode": country.get("code"),
                            "city": f"{city.get('name')} ({hostname})",
                            "cityCode": city.get("code"),
                            "latitude": city.get("latitude"),
                            "longitude": city.get("longitude"),
                        },
                    }

                    tasks.append(
                        {
                            "name": hostname,
                            "userId": self.args.id,
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
            f"Registering {len(tasks)} relays", self.hs.reg, tasks, lambda t: t["name"]
        )

    def create_connections(self):
        state = self.hs.state()
        node_id = self.args.node_id

        target = next(
            (n for n in state.get("nodes", []) if str(n["id"]) == node_id), None
        )
        if not target:
            sys.exit(f"Node {node_id} not found")

        node_name = target.get("givenName", target.get("name"))
        logger.info(f"Creating connections for node '{node_name}' ...")

        nodekey = nodekey2wg(target.get("nodeKey"))
        v4, v6 = self.mv.auth(nodekey)

        existing = {
            str(c["wgPeerId"])
            for c in state.get("wireguardConnections", [])
            if str(c["nodeId"]) == node_id
        }
        tasks = []

        for p in state.get("wireguardOnlyPeers", []):
            if str(p["id"]) in existing:
                continue
            tasks.append(
                (
                    {
                        "nodeId": node_id,
                        "wgPeerId": str(p["id"]),
                        "ipv4MasqAddr": v4,
                        "ipv6MasqAddr": v6,
                    },
                    p.get("name"),
                )
            )

        if not tasks:
            logger.info("All Wireguard connections are up-to-date")
            return

        run_tasks(
            f"Connecting {len(tasks)} peers",
            lambda t: self.hs.conn(t[0]),
            tasks,
            lambda t: t[1],
        )


def main():
    parser = argparse.ArgumentParser(
        description="Automatically create Wireguard exit nodes in your Headscale tailnet"
    )
    parser.add_argument("-i", "--id", required=True, help="ID of Headscale user")

    sub = parser.add_subparsers(dest="command", required=True)

    c_clean = sub.add_parser("clean", help="Delete peers & connections")
    c_clean.add_argument(
        "-f", "--filter", help="Filter by country code, comma-separated list"
    )

    c_relays = sub.add_parser("create-relays", help="Register Mullvad relays")
    c_relays.add_argument(
        "-f", "--filter", help="Filter by country code, comma-separated list"
    )

    c_conn = sub.add_parser(
        "create-connections", help="Create connections to Mullvad relays for a node"
    )
    c_conn.add_argument("node_id", help="ID of Headscale node")

    try:
        App(parser.parse_args()).run()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
