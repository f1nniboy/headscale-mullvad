import requests

from ..config import HEADSCALE_API_KEY, HEADSCALE_URL, MULLVAD_NODE_PREFIX
from ..utils import logger


class HeadscaleClient:
    def __init__(self):
        if not HEADSCALE_URL or not HEADSCALE_API_KEY:
            raise ValueError("HEADSCALE_URL and HEADSCALE_API_KEY must be set")

        self.url = HEADSCALE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {HEADSCALE_API_KEY}",
            "Content-Type": "application/json",
        }

    def req(self, path, method="GET", body=None):
        try:
            response = requests.request(
                method, f"{self.url}{path}", json=body, headers=self.headers
            )
            response.raise_for_status()
            if response.status_code == 204 or method == "DELETE":
                return None
            return response.json()
        except requests.exceptions.HTTPError as e:
            if not (method == "DELETE" and e.response.status_code == 404):
                logger.error(
                    f"HTTP [bold]{e.response.status_code}[/bold] [bold]{method}[/bold] [bold]{path}[/bold]: [bold]{e.response.text}[/bold]"
                )
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Headscale API request failed: [bold]{e}[/bold]")
            raise
        return None

    def state(self):
        return self.req("/api/v1/node") or {
            "nodes": [],
            "wireguardOnlyPeers": [],
            "wireguardConnections": [],
        }

    def list_relays(self):
        all_relays = self.state().get("wireguardOnlyPeers", [])
        return [r for r in all_relays if r.get("name", "").startswith(MULLVAD_NODE_PREFIX)]

    def register_relay(self, relay_data):
        self.req("/api/v1/wireguard-only-peer/register", "POST", relay_data)

    def delete_relay(self, relay_id):
        self.req(f"/api/v1/node/{relay_id}", "DELETE")

    def list_nodes(self):
        return self.state().get("nodes", [])

    def get_node_by_id(self, node_id):
        return next(
            (n for n in self.list_nodes() if str(n.get("id")) == str(node_id)), None
        )

    def get_node_by_name(self, name):
        return next(
            (
                n
                for n in self.list_nodes()
                if n.get("givenName") == name or n.get("name") == name
            ),
            None,
        )

    def get_connections(self):
        return self.state().get("wireguardConnections", [])

    def create_connection(self, conn_data):
        self.req("/api/v1/wireguard/connection", "POST", conn_data)

    def delete_connection(self, node_id, peer_id):
        self.req(f"/api/v1/wireguard/connection/{node_id}/{peer_id}", "DELETE")

    def list_users(self):
        d = self.req("/api/v1/user")
        return d.get("users", []) if d else []

    def get_user_by_name(self, username):
        users = self.list_users()
        for user in users:
            if user.get("name") == username:
                return user
        return None
