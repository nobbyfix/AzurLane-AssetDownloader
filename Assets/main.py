from pathlib import Path
from argparse import ArgumentParser

from lib import config, protobuf, versioncontrol, updater
from lib.classes import Client


def main(client: Client):
	# load config data from files
	userconfig = config.load_user_config()
	clientconfig = config.load_client_config(client)

	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)

	version_response = protobuf.get_version_response(clientconfig.gateip, clientconfig.gateport)
	versionlist = [versioncontrol.parse_version_string(v) for v in version_response.pb.version if v.startswith("$")]
	for vresult in versionlist:
		if update_assets := updater.update(vresult, clientconfig.cdnurl, userconfig, CLIENT_ASSET_DIR):
			versioncontrol.save_difflog(vresult.version_type, update_assets, CLIENT_ASSET_DIR)


if __name__ == "__main__":
	# setup argument parser
	parser = ArgumentParser()
	parser.add_argument("client", type=str, choices=Client.__members__, help="client to update")
	args = parser.parse_args()

	# execute
	main(Client[args.client])