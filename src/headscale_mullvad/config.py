from os import environ

from dotenv import load_dotenv

load_dotenv()

MAX_WORKERS = 50
MULLVAD_NODE_PREFIX = "mv-"

HEADSCALE_URL = environ.get("HEADSCALE_URL")
HEADSCALE_API_KEY = environ.get("HEADSCALE_API_KEY")
MULLVAD_ACCOUNT = environ.get("MULLVAD_ACCOUNT")
