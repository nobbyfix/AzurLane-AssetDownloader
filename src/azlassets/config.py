import json
import tomllib
import warnings
import yaml
from collections import defaultdict
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from shutil import copy

from .classes import Client
from .filter import PathFilter

CONFIG_VERSION = 2

# package-incuded filepaths
CONFIG_DATA_PATH = files("azlassets").joinpath("config")
TOML_USERCONFIG_DEFAULT_PATH = CONFIG_DATA_PATH.joinpath("userconfig_default.toml")
TOML_USERCONFIG_TEMPLATE_PATH = CONFIG_DATA_PATH.joinpath("userconfig.toml")
CLIENT_CONFIG_PATH = CONFIG_DATA_PATH.joinpath("client_config.json")
YAML_TEMPLATE_PATH = CONFIG_DATA_PATH.joinpath("user_config_template.yml")

# cwd-relative filepaths
TOML_USERCONFIG_DEFAULT_EXAMPLE_PATH = Path("config", "userconfig_default.toml")
TOML_USERCONFIG_PATH = Path("config", "userconfig.toml")
YAML_CONFIG_PATH = Path("config", "user_config.yml")


# STRINGS
DEPRECATION_WARNING = """The old YAML-based userconfig has been found. Support for it will be dropped with version 6.0. \
Check https://github.com/nobbyfix/AzurLane-AssetDownloader/blob/master/UPGRADE.md on what \
actions to take to migrate to the new TOML-based userconfig."""

FORMAT_WARNING = """The YAML config has been formatted incorrectly and values may be missing. \
Correct these issues or delete the file to use the new TOML-based userconfig. \
The fallback default configuration will be used."""

CONVERT_INPUT = """Converting the YAML-based userconfig will overwrite 'userconfig.toml'. \
If you have already edited that file, the contents will be lost. \
Are you sure you want to proceed? (y/n): """


# WARNINGS AND WARNING CONTROL
class YAMLConfigDeprecationWarming(DeprecationWarning):
	pass


class YAMLConfigInvalidFormatWarning(UserWarning):
	pass


warnings.simplefilter("once", YAMLConfigDeprecationWarming)


# DATACLASSES
@dataclass
class YAMLUserConfig:
	"""
	Old User-supplied configuration controlling download and extraction behaviour.
	"""

	useragent: str
	download_isblacklist: bool
	download_filter: list
	extract_isblacklist: bool
	extract_filter: list
	asset_directory: Path
	extract_directory: Path


@dataclass
class UserConfig:
	"""
	User-supplied configuration controlling download and extraction behaviour.
	"""

	useragent: str
	asset_directory: Path
	extract_directory: Path
	download_filter: PathFilter
	extract_filter: PathFilter


@dataclass
class ClientConfig:
	"""
	Server connection parameters for a game client.
	"""

	gateip: str
	gateport: int
	cdnurl: str


def load_yaml_userconfig() -> YAMLUserConfig | None:
	"""
	Load user configuration from ``config/user_config.yml``.

	Returns:
		YAMLUserConfig: The loaded user configuration
	"""
	try:
		with YAML_CONFIG_PATH.open("r", encoding="utf8") as file:
			yamlconfig = yaml.safe_load(file)
	except FileNotFoundError:
		return None

	warnings.warn(DEPRECATION_WARNING, category=YAMLConfigDeprecationWarming)
	try:
		userconfig = YAMLUserConfig(
			useragent=yamlconfig["useragent"],
			download_isblacklist=yamlconfig["download-folder-listtype"] == "blacklist",
			download_filter=yamlconfig["download-folder-list"],
			extract_isblacklist=yamlconfig["extract-folder-listtype"] == "blacklist",
			extract_filter=yamlconfig["extract-folder-list"],
			asset_directory=yamlconfig["asset-directory"],
			extract_directory=yamlconfig["extract-directory"],
		)
		return userconfig
	except KeyError:
		warnings.warn(FORMAT_WARNING, category=YAMLConfigInvalidFormatWarning)
		return None


def convert_yaml_userconfig(yaml_config: YAMLUserConfig) -> UserConfig:
	download_w_pattern = yaml_config.download_filter if not yaml_config.download_isblacklist else []
	download_b_pattern = yaml_config.download_filter if yaml_config.download_isblacklist else []
	download_filter = PathFilter(raw_patterns_whitelist=download_w_pattern, raw_patterns_blacklist=download_b_pattern)

	extract_w_pattern = yaml_config.extract_filter if not yaml_config.extract_isblacklist else []
	extract_b_pattern = yaml_config.extract_filter if yaml_config.extract_isblacklist else []
	extract_filter = PathFilter(raw_patterns_whitelist=extract_w_pattern, raw_patterns_blacklist=extract_b_pattern)

	userconfig = UserConfig(
		useragent=yaml_config.useragent,
		asset_directory=yaml_config.asset_directory,
		extract_directory=yaml_config.extract_directory,
		download_filter=download_filter,
		extract_filter=extract_filter,
	)
	return userconfig


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
	extract_filter = PathFilter(
		raw_patterns_whitelist=toml_data["extract"]["filters"]["whitelist"],
		raw_patterns_blacklist=toml_data["extract"]["filters"]["blacklist"],
	)

	userconfig = UserConfig(
		useragent=toml_data["user"]["useragent"],
		asset_directory=toml_data["filepaths"]["asset-directory"],
		extract_directory=toml_data["filepaths"]["extract-directory"],
		download_filter=download_filter,
		extract_filter=extract_filter,
	)
	return userconfig


def load_userconfig() -> UserConfig:
	if yamlconfig := load_yaml_userconfig():
		return convert_yaml_userconfig(yamlconfig)

	# load default config first and then overwrite it with the userconfig
	toml_userconfig = load_default_toml_userconfig()
	toml_userconfig |= load_toml_userconfig()

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


def create_toml_userconfig_from_yaml():
	import tomli_w

	if yamlconfig := load_yaml_userconfig():
		userconfig = convert_yaml_userconfig(yamlconfig)
	else:
		print("Nothing to convert: YAML userconfig does not exist.")
		return

	yn = input(CONVERT_INPUT)
	if not yn.lower() in {"y", "yes"}:
		print("Aborted.")
		return

	default_tomldata = load_default_toml_userconfig()
	default_userconfig = get_userconfig_from_tomldata(default_tomldata)

	# only convert the data that is different from the default config

	toml_data = defaultdict(dict)
	if userconfig.useragent != "" or userconfig.useragent != default_userconfig.useragent:
		toml_data["user"]["useragent"] = userconfig.useragent

	# filepaths
	if userconfig.asset_directory != default_userconfig.asset_directory:
		toml_data["filepaths"]["asset-directory"] = userconfig.asset_directory
	if userconfig.extract_directory != default_userconfig.extract_directory:
		toml_data["filepaths"]["extract-directory"] = userconfig.extract_directory

	# download filters
	if userconfig.download_filter.whitelist != default_userconfig.download_filter.whitelist:
		toml_data["download"]["filters"]["whitelist"] = userconfig.download_filter.whitelist
	if userconfig.download_filter.blacklist != default_userconfig.download_filter.blacklist:
		toml_data["download"]["filters"]["blacklist"] = userconfig.download_filter.blacklist

	# extract filters
	if userconfig.extract_filter.whitelist != default_userconfig.extract_filter.whitelist:
		toml_data["extract"]["filters"]["whitelist"] = userconfig.extract_filter.whitelist
	if userconfig.extract_filter.blacklist != default_userconfig.extract_filter.blacklist:
		toml_data["extract"]["filters"]["blacklist"] = userconfig.extract_filter.blacklist

	toml_string = tomli_w.dumps(toml_data)

	with TOML_USERCONFIG_TEMPLATE_PATH.open("r", encoding="utf8") as template_f:
		template_string = template_f.read()

	with open(TOML_USERCONFIG_PATH, "w", encoding="utf8") as f:
		f.write(template_string)
		f.write("\n")
		f.write(toml_string)

	print("Conversion complete. Deleting old YAML userconfig file...")
	YAML_CONFIG_PATH.unlink()

	print("Done.")
