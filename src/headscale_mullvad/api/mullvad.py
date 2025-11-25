import sys

import requests

from ..config import MULLVAD_ACCOUNT
from ..utils import logger


class MullvadClient:
    def __init__(self):
        if not MULLVAD_ACCOUNT:
            logger.error("MULLVAD_ACCOUNT env missing")
            sys.exit(1)

        self.account = MULLVAD_ACCOUNT
        self.api_url = "https://api.mullvad.net"

    def _handle_api_error(self, e, context_msg):
        if e.response is not None:
            try:
                raw_msg = e.response.text
                error_message = f"Mullvad API error: [bold]{raw_msg}[/bold]"

                raise Exception(error_message) from e
            except (ValueError, IndexError):
                pass
        logger.error(f"Mullvad [bold]{context_msg}[/bold] error: [bold]{e}[/bold]")
        raise Exception(f"Mullvad {context_msg} error: {e}") from e

    def relays(self):
        try:
            response = requests.get(f"{self.api_url}/public/relays/wireguard/v1/")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_api_error(e, "API")

    def auth(self, pubkey):
        data = {"account": self.account, "pubkey": pubkey}
        try:
            response = requests.post(f"{self.api_url}/wg", data=data)
            response.raise_for_status()
            parts = response.text.strip().split(",")
            return parts[0].split("/")[0], parts[1].split("/")[0]
        except requests.exceptions.RequestException as e:
            self._handle_api_error(e, "auth")
