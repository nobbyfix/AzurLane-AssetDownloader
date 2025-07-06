import sys
import json
import yaml
from shutil import copy
from pathlib import Path
from importlib.resources import files

from .classes import Client, UserConfig, ClientConfig


# package-incuded filepaths
CONFIG_DATA_PATH = files("azlassets").joinpath("config")
YAML_TEMPLATE_PATH = CONFIG_DATA_PATH.joinpath("user_config_template.yml")
CLIENT_CONFIG_PATH = CONFIG_DATA_PATH.joinpath("client_config.json")

# cwd-relative filepaths
YAML_CONFIG_PATH = Path("config") / "user_config.yml"


def load_user_config() -> UserConfig:
	if not YAML_CONFIG_PATH.exists():
		print("Userconfig does not exist. A new one will be created.")
		print("Note that the useragent is empty and it is advised to set one.")
		YAML_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
		copy(YAML_TEMPLATE_PATH, YAML_CONFIG_PATH)
		return load_user_config()

	with open(YAML_CONFIG_PATH, 'r', encoding='utf8') as file:
		yamlconfig = yaml.safe_load(file)

	try:
		userconfig = UserConfig(
			useragent=yamlconfig['useragent'],
			download_isblacklist=yamlconfig['download-folder-listtype'] == 'blacklist',
			download_filter=yamlconfig['download-folder-list'],
			extract_isblacklist=yamlconfig['extract-folder-listtype'] == 'blacklist',
			extract_filter=yamlconfig['extract-folder-list'],
			asset_directory=yamlconfig['asset-directory'],
			extract_directory=yamlconfig['extract-directory'],
		)
	except KeyError:
		print("There is an error inside the userconfig file. Delete it or change the wrong values.")
		sys.exit(1)

	return userconfig


def load_client_config(client: Client) -> ClientConfig:
	with open(CLIENT_CONFIG_PATH, 'r', encoding='utf8') as f:
		configdata = json.load(f)

	if not client.name in configdata:
		raise NotImplementedError(f'Client {client.name} has not been configured yet.')

	config = configdata[client.name]
	try:
		clientconfig = ClientConfig(config['gateip'], config['gateport'], config['cdnurl'])
	except KeyError:
		print("The clientconfig has been wrongly configured.")
		sys.exit(1)

	return clientconfig
