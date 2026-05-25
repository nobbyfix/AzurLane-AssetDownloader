import asyncio
import sys
from pathlib import Path

from . import config, downloader, extractor, protobuf, repair, updater
from .classes import Client
from .versioncontrol import UnknownVersionTypeError, VersionController, VersionResult, VersionType, parse_version_string


def try_parse_version_string(vstring: str, skip_error: bool = False) -> VersionResult | None:
	"""
	Parse a version string, with optional suppression of errors.

	Args:
		vstring: The version string to parse
		skip_error: If True, an :class:`UnknownVersionTypeError` is caught, a warning is printed,
			and None is returned instead of raising

	Returns:
		VersionResult or None: The parsed result, or None if the type was unknown and ``skip_error`` is True

	Raises:
		UnknownVersionTypeError: If the version type is unrecognised and ``skip_error`` is False
	"""
	try:
		return parse_version_string(vstring)
	except UnknownVersionTypeError as e:
		if skip_error:
			print(f"WARN: Unknown version type '{e.version_name}' cannot be processed, but this error has been skipped.")
			print("WARN: Update application as soon as possible to support this missing version type.")
		else:
			raise


async def execute(args):
	"""
	Main async entry point for the download manager.
	"""
	# load config data from files
	userconfig = config.load_user_config()
	clientconfig = config.load_client_config(args.client)

	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, args.client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
	versioncontroller = VersionController(CLIENT_ASSET_DIR)

	if args.check_integrity:
		async with downloader.AzurlaneAsyncDownloader(clientconfig.cdnurl, useragent=userconfig.useragent) as downloader_session:
			update_assets = await repair.repair(downloader_session, versioncontroller)
			return

	if args.force_refresh and not args.repair:
		print("All asset types will be checked for different hashes.")

	version_response = protobuf.get_version_response(clientconfig.gateip, clientconfig.gateport)
	if not version_response:
		print("Server did not return a response to version request.")
		sys.exit(1)

	# parse version response
	version_response_string: list[str] = version_response.pb.version
	parsed_version_response = dict()
	for v in version_response_string:
		if v.startswith("$"):
			if vresult := try_parse_version_string(v.strip(), args.skip_unknown_version_error):
				parsed_version_response[vresult.version_type] = vresult

	try:
		azl_latest_version_with_difflog = versioncontroller.load_latest_difflog_version(VersionType.AZL)
	except FileNotFoundError:
		azl_latest_version_with_difflog = None

	async with downloader.AzurlaneAsyncDownloader(clientconfig.cdnurl, useragent=userconfig.useragent) as downloader_session:
		for vresult in parsed_version_response.values():
			if args.repair:
				update_assets = await repair.repair_hashfile(vresult, downloader_session, userconfig, versioncontroller)
			else:
				update_assets = await updater.update(
					vresult, downloader_session, userconfig, versioncontroller, args.force_refresh, args.ignore_hashfile
				)

			if update_assets:
				versioncontroller.update_difflog(vresult, update_assets, is_latest=True)

				if vresult.version_type == VersionType.AZL:
					azl_latest_version_with_difflog = vresult
				elif azl_latest_version_with_difflog is not None:
					versioncontroller.set_as_linked(vresult, azl_latest_version_with_difflog)

	if args.extract:
		extractor.extract_latest_client(args.client)


def execute_from_args(args):
	args.client = Client[args.client]
	asyncio.run(execute(args))
