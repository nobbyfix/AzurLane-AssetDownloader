import asyncio
import sys
from pathlib import Path

from azlassets import config, downloader, protobuf, repair, updater, versioncontrol
from azlassets.classes import Client, UnknownVersionTypeError, VersionResult, VersionType


def try_parse_version_string(vstring: str, skip_error: bool = False) -> VersionResult | None:
	try:
		return versioncontrol.parse_version_string(vstring)
	except UnknownVersionTypeError as e:
		if skip_error:
			print(f"WARN: Unknown version type '{e.version_name}' cannot be processed, but this error has been skipped.")
			print("WARN: Update application as soon as possible to support this missing version type.")
		else:
			raise


async def execute(args):
	# load config data from files
	userconfig = config.load_user_config()
	clientconfig = config.load_client_config(args.client)

	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, args.client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
	versioncontroller = versioncontrol.VersionController(CLIENT_ASSET_DIR)

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
	version_string = version_response.pb.version
	versionlist = [try_parse_version_string(v, args.skip_unknown_version_error) for v in version_string if v.startswith("$")]

	# find AZL version result
	azl_current = None
	for vresult in versionlist:
		if vresult.version_type == VersionType.AZL:
			azl_current = vresult
			break

	async with downloader.AzurlaneAsyncDownloader(clientconfig.cdnurl, useragent=userconfig.useragent) as downloader_session:
		for vresult in versionlist:
			if args.repair:
				update_assets = await repair.repair_hashfile(vresult, downloader_session, userconfig, versioncontroller)
			else:
				update_assets = await updater.update(
					vresult, downloader_session, userconfig, versioncontroller, args.force_refresh, args.ignore_hashfile
				)

			if update_assets:
				versioncontroller.save_difflog(vresult, update_assets)
				if vresult.version_type != VersionType.AZL:
					versioncontroller.set_as_linked(vresult, azl_current)


def execute_from_args(args):
	args.client = Client[args.client]
	asyncio.run(execute(args))
