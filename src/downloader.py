#!/usr/bin/env python
import sys
import asyncio
import argparse
from pathlib import Path

from azlassets import __version__, config, protobuf, versioncontrol, updater, repair, downloader
from azlassets.classes import Client, VersionType


async def execute(args):
	# load config data from files
	userconfig = config.load_user_config()
	clientconfig = config.load_client_config(args.client)

	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, args.client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
	versioncontroller = versioncontrol.VersionController(CLIENT_ASSET_DIR)

	if args.check_integrity:
		update_assets = await repair.repair(clientconfig.cdnurl, userconfig, versioncontroller)

	if args.force_refresh and not args.repair:
		print("All asset types will be checked for different hashes.")

	version_response = protobuf.get_version_response(clientconfig.gateip, clientconfig.gateport)
	if not version_response:
		print("Server did not return a response to version request.")
		sys.exit(1)

	# parse version response
	version_string = version_response.pb.version
	versionlist = [versioncontrol.parse_version_string(v) for v in version_string if v.startswith("$")]

	# find AZL version result
	azl_current = None
	for vresult in versionlist:
		if vresult.version_type == VersionType.AZL:
			azl_current = vresult
			break

	async with downloader.AzurlaneAsyncDownloader(clientconfig.cdnurl, useragent=userconfig.useragent) as downloader_session:
		for vresult in versionlist:
			if args.repair:
				update_assets = await repair.repair_hashfile(
					vresult,
					downloader_session,
					userconfig,
					versioncontroller
				)
			else:
				update_assets = await updater.update(
					vresult,
					downloader_session,
					userconfig,
					versioncontroller,
					args.force_refresh,
					args.ignore_hashfile
				)

			if update_assets:
				versioncontroller.save_difflog(vresult, update_assets)
				if vresult.version_type != VersionType.AZL:
					versioncontroller.set_as_linked(vresult, azl_current)


def main():
	print(f"Running Azurlane file downloader v{__version__}.")

	# setup argument parser
	parser = argparse.ArgumentParser()
	parser.add_argument("client", type=str, choices=Client.__members__,
		help="client to update")
	parser.add_argument("--force-refresh", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="Compares asset hashes even when the version file is up to date.")
	parser.add_argument("--repair", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="Downloads missing files if the update process failed partially.")
	parser.add_argument("--check-integrity", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="Checks if all files are correct using the local hash file.")
	parser.add_argument("--ignore-hashfile", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="Ignores the local hashfile and downloads ALL files again. This is only intended for testing purposes.")
	args = parser.parse_args()

	args.client = Client[args.client]
	asyncio.run(execute(args))

if __name__ == "__main__":
	main()
