#!/usr/bin/env python3
import argparse
from pathlib import Path

from lib import config, protobuf, versioncontrol, updater, repair
from lib.classes import Client


def execute(args):
	# load config data from files
	userconfig = config.load_user_config()
	clientconfig = config.load_client_config(args.client)

	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, args.client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)

	if args.check_integrity:
		repair.repair(clientconfig.cdnurl, userconfig, CLIENT_ASSET_DIR)

	if args.force_refresh and not args.repair:
		print("All asset types will be checked for different hashes.")

	version_response = protobuf.get_version_response(clientconfig.gateip, clientconfig.gateport)
	versionlist = [versioncontrol.parse_version_string(v) for v in version_response.pb.version if v.startswith("$")]
	for vresult in versionlist:
		if args.repair:
			update_assets = repair.repair_hashfile(vresult, clientconfig.cdnurl, userconfig, CLIENT_ASSET_DIR)
		else:
			update_assets = updater.update(vresult, clientconfig.cdnurl, userconfig, CLIENT_ASSET_DIR, args.force_refresh)

		if update_assets:
			versioncontrol.save_difflog2(vresult, update_assets, CLIENT_ASSET_DIR)


def main():
	# setup argument parser
	parser = argparse.ArgumentParser()
	parser.add_argument("client", type=str, choices=Client.__members__,
		help="client to update")
	parser.add_argument("--force-refresh", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="compares asset hashes even when the version file is up to date")
	parser.add_argument("--repair", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="downloads missing files if the update process failed partially")
	parser.add_argument("--check-integrity", type=bool, default=False, action=argparse.BooleanOptionalAction,
		help="checks if all files are correct using the local hash file")
	args = parser.parse_args()

	args.client = Client[args.client]
	execute(args)

if __name__ == "__main__":
	main()
