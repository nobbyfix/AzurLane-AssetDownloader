import json
import sys
import yaml
from importlib.resources import as_file, files
from pathlib import Path
from shutil import copy

from .classes import Client, ClientConfig, UserConfig

# package-incuded filepaths
CONFIG_DATA_PATH = files("azlassets").joinpath("config")
YAML_TEMPLATE_PATH = CONFIG_DATA_PATH.joinpath("user_config_template.yml")
CLIENT_CONFIG_PATH = CONFIG_DATA_PATH.joinpath("client_config.json")

# cwd-relative filepaths
YAML_CONFIG_PATH = Path("config") / "user_config.yml"


def create_user_config() -> bool:
	"""
	Create the user config file from the built-in template if it doesn't exist.

	Copies the package-bundled template from ``user_config_template.yml`` to
	``config/user_config.yml`` relative to the current working directory.

	Returns:
		bool: True if the file was created, False if it already existed
	"""
	if not YAML_CONFIG_PATH.exists():
		print("Userconfig does not exist. A new one will be created.")
		print("The useragent is using the default value and it is advised to set a custom one.")
		YAML_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
		with as_file(YAML_TEMPLATE_PATH) as template_path:
			copy(template_path, YAML_CONFIG_PATH)
		return True
	return False


def load_user_config() -> UserConfig:
	"""
	Load user configuration from ``config/user_config.yml``.

	Calls :func:`create_user_config` first, so the file is created from the
	built-in template if it doesn't exist yet.

	Returns:
		UserConfig: The loaded user configuration
	"""
	# make sure the config file exists
	create_user_config()

	with YAML_CONFIG_PATH.open("r", encoding="utf8") as file:
		yamlconfig = yaml.safe_load(file)

	try:
		userconfig = UserConfig(
			useragent=yamlconfig["useragent"],
			download_isblacklist=yamlconfig["download-folder-listtype"] == "blacklist",
			download_filter=yamlconfig["download-folder-list"],
			extract_isblacklist=yamlconfig["extract-folder-listtype"] == "blacklist",
			extract_filter=yamlconfig["extract-folder-list"],
			asset_directory=yamlconfig["asset-directory"],
			extract_directory=yamlconfig["extract-directory"],
		)
	except KeyError:
		print("There is an error inside the userconfig file. Delete it or change the wrong values.")
		sys.exit(1)

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
	except KeyError:
		print("The clientconfig has been wrongly configured.")
		sys.exit(1)

	return clientconfig
