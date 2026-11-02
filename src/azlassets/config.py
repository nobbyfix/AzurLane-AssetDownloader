import json
import tomllib
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from shutil import copy

from .classes import Client
from .filter import PathFilter

CONFIG_VERSION = 6

# package-incuded filepaths
CONFIG_DATA_PATH = files("azlassets").joinpath("config")
TOML_USERCONFIG_DEFAULT_PATH = CONFIG_DATA_PATH.joinpath("userconfig_default.toml")
TOML_USERCONFIG_TEMPLATE_PATH = CONFIG_DATA_PATH.joinpath("userconfig.toml")
CLIENT_CONFIG_PATH = CONFIG_DATA_PATH.joinpath("client_config.json")

# cwd-relative filepaths
TOML_USERCONFIG_DEFAULT_EXAMPLE_PATH = Path("config", "userconfig_default.toml")
TOML_USERCONFIG_PATH = Path("config", "userconfig.toml")


@dataclass
class UserConfig:
	"""
	User-supplied configuration controlling download and extraction behaviour.
	"""

	useragent: str
	asset_directory: Path
	extract_directory: Path
	download_filter: PathFilter
	import_filter: PathFilter
	extract_filter: PathFilter


@dataclass
class ClientConfig:
	"""
	Server connection parameters for a game client.
	"""

	gateip: str
	gateport: int
	cdnurl: str


def deep_update(dict1: dict, dict2: dict) -> dict:
	"""Recursively merges dict2 into dict1."""
	for key, value in dict2.items():
		if isinstance(value, dict):
			dict1[key] = deep_update(dict1[key], value)
		else:
			dict1[key] = value
	return dict1


def create_default_toml_userconfig_example():
	TOML_USERCONFIG_DEFAULT_EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
	with as_file(TOML_USERCONFIG_DEFAULT_PATH) as source_path:
		copy(source_path, TOML_USERCONFIG_DEFAULT_EXAMPLE_PATH)


def load_default_toml_userconfig_example() -> dict:
	with open(TOML_USERCONFIG_DEFAULT_EXAMPLE_PATH, "rb") as f:
		return tomllib.load(f)


def update_default_toml_userconfig_example():
	try:
		data = load_default_toml_userconfig_example()
	except FileNotFoundError:
		create_default_toml_userconfig_example()
		return

	if data["meta"]["version"] != CONFIG_VERSION:
		create_default_toml_userconfig_example()


def load_default_toml_userconfig() -> dict:
	with TOML_USERCONFIG_DEFAULT_PATH.open("rb") as f:
		return tomllib.load(f)


def create_toml_userconfig():
	TOML_USERCONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
	with as_file(TOML_USERCONFIG_TEMPLATE_PATH) as source_path:
		copy(source_path, TOML_USERCONFIG_PATH)


def load_toml_userconfig() -> dict:
	with TOML_USERCONFIG_PATH.open("rb") as f:
		return tomllib.load(f)


def ensure_toml_userconfig_exists():
	if not TOML_USERCONFIG_PATH.exists():
		create_toml_userconfig()


def get_userconfig_from_tomldata(toml_data: dict) -> UserConfig:
	download_filter = PathFilter(
		raw_patterns_whitelist=toml_data["download"]["filters"]["whitelist"],
		raw_patterns_blacklist=toml_data["download"]["filters"]["blacklist"],
	)

	if toml_data["import"]["filters"]["use-download-filters"]:
		import_filter = download_filter
	else:
		import_filter = PathFilter(
			raw_patterns_whitelist=toml_data["import"]["filters"]["whitelist"],
			raw_patterns_blacklist=toml_data["import"]["filters"]["blacklist"],
		)

	if toml_data["extract"]["filters"]["use-download-filters"]:
		extract_filter = download_filter
	else:
		extract_filter = PathFilter(
			raw_patterns_whitelist=toml_data["extract"]["filters"]["whitelist"],
			raw_patterns_blacklist=toml_data["extract"]["filters"]["blacklist"],
		)

	userconfig = UserConfig(
		useragent=toml_data["user"]["useragent"],
		asset_directory=toml_data["filepaths"]["asset-directory"],
		extract_directory=toml_data["filepaths"]["extract-directory"],
		download_filter=download_filter,
		import_filter=import_filter,
		extract_filter=extract_filter,
	)
	return userconfig


def load_userconfig() -> UserConfig:
	# load default config first and then overwrite it with the userconfig
	toml_userconfig = load_default_toml_userconfig()
	toml_userconfig = deep_update(toml_userconfig, load_toml_userconfig())

	userconfig = get_userconfig_from_tomldata(toml_userconfig)
	return userconfig


def load_client_config(client: Client) -> ClientConfig:
	"""
	Load client configuration for the given client from the built-in
	``client_config.json``.

	Args:
		client: The client to load configuration for

	Raises:
		NotImplementedError: If no entry for ``client`` exists in the config file

	Returns:
		ClientConfig: The loaded client configuration
	"""
	with CLIENT_CONFIG_PATH.open("r", encoding="utf8") as f:
		configdata = json.load(f)

	if client.name not in configdata:
		raise NotImplementedError(f"Client {client.name} has not been configured yet.")

	config = configdata[client.name]
	try:
		clientconfig = ClientConfig(config["gateip"], config["gateport"], config["cdnurl"])
	except KeyError as e:
		raise KeyError("The clientconfig has been wrongly configured.") from e

	return clientconfig
