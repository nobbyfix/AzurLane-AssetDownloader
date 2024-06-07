#!/usr/bin/env python3
import io, re, sys, json, shutil
from argparse import ArgumentParser, BooleanOptionalAction
from zipfile import ZipFile
from pathlib import Path

from lib import versioncontrol, updater, config
from lib.classes import BundlePath, Client, CompareType, DownloadType, UpdateResult, VersionType


def unpack(zipfile: ZipFile, client: Client, allow_older_version: bool = False):
	# load config data from files
	userconfig = config.load_user_config()
	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)

	print('Unpacking archive...')
	for versiontype in VersionType:
		# make sure the version file exists
		if not 'assets/'+versiontype.version_filename in zipfile.namelist():
			print(f'{versiontype.name}: The file {versiontype.version_filename} could not be found in the archive. Has the archive been modified?')
			continue

		# read version string from obb
		with zipfile.open('assets/'+versiontype.version_filename, 'r') as zf:
			obbversion = zf.read().decode('utf8')

		# if a version file already exists, compare the versions
		# if the obbversion is smaller (older), don't extract data from obb
		currentversion = versioncontrol.load_version_string(versiontype, CLIENT_ASSET_DIR)
		if currentversion and tuple(obbversion.split('.')) < tuple(currentversion.split('.')):
			print(f'{versiontype.name}: Current version {currentversion} is same or newer than obb version {obbversion}.')
			continue

		# read hash files from obb and current file and compare them
		with zipfile.open('assets/'+versiontype.hashes_filename, 'r') as hashfile:
			obbhashes = versioncontrol.parse_hash_rows(hashfile.read().decode('utf8'))
		currenthashes = versioncontrol.load_hash_file(versiontype, CLIENT_ASSET_DIR)
		comparison_results = updater.compare_hashes(currenthashes, obbhashes)

		# extract and delete files
		assetbasepath = Path(CLIENT_ASSET_DIR, 'AssetBundles')
		update_files = list(filter(lambda r: r.compare_type != CompareType.Unchanged, comparison_results.values()))
		update_results = [UpdateResult(r, DownloadType.NoChange, BundlePath.construct(assetbasepath, r.new_hash.filepath)) for r in filter(lambda r: r.compare_type == CompareType.Unchanged, comparison_results.values())]

		fileamount = len(update_files)
		for i, result in enumerate(update_files, 1):
			if result.compare_type in [CompareType.New, CompareType.Changed]:
				print(f'Saving {result.new_hash.filepath} ({i}/{fileamount}).')
				assetpath = BundlePath.construct(assetbasepath, result.new_hash.filepath)
				extract_asset(zipfile, assetpath.inner, assetpath.full)
				update_results.append(UpdateResult(result, DownloadType.Success if assetpath.full.exists() else DownloadType.Failed, assetpath))
			elif result.compare_type == CompareType.Deleted:
				print(f'Deleting {result.current_hash.filepath} ({i}/{fileamount}).')
				assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)
				updater.remove_asset(assetpath.full)
				update_results.append(UpdateResult(result, DownloadType.Removed, assetpath))

		# update version string, hashes and difflog
		hashes_updated = updater.filter_hashes(update_results)
		versioncontrol.update_version_data(versiontype, CLIENT_ASSET_DIR, obbversion, hashes_updated)
		versioncontrol.save_difflog(versiontype, obbversion, update_results, CLIENT_ASSET_DIR)


def extract_asset(zipfile: ZipFile, filepath: str, target: Path):
	target.parent.mkdir(exist_ok=True, parents=True)
	
	if "." in Path(filepath).name:
		assetpath = "assets/AssetBundles/"+filepath
	else:
		assetpath = "assets/AssetBundles/"+filepath+".ys"

	with zipfile.open(assetpath, 'r') as zf, open(target, 'wb') as f:
		shutil.copyfileobj(zf, f)


def extract_obb(path: Path, fallback_client: Client = None, allow_older_version: bool = False):
	for client in Client:
		if client.package_name and re.match(rf".*{client.package_name}\.obb", path.name):
			print(f'Determined client {client.name} from filename.')
			with ZipFile(path, 'r') as zipfile:
				unpack(zipfile, client, allow_older_version)
			break
	else:
		if fallback_client:
			print(f"Unpacking using provided client {fallback_client.name}.")
			with ZipFile(path, 'r') as zipfile:
				unpack(zipfile, fallback_client, allow_older_version)
		else:
			sys.exit(f'Filename "{path.name}" could not be associated with any known client.')

def extract_xapk(path: Path, allow_older_version: bool = False):
	with ZipFile(path, 'r') as xapk_archive:
		# read the manifest file for information about the client, obbs and the apk paths inside the archive
		with xapk_archive.open('manifest.json', 'r') as manifestfile:
			manifest = json.loads(manifestfile.read().decode('utf8'))
		
		# determine the client the xpak comes from
		if client := Client.from_package_name(manifest['package_name']):
			print(f'Determined client {client.name} from manifest.json file.')
			# find all obb archives and extract files from them
			for obb_expansion in manifest['expansions']:
				with xapk_archive.open(obb_expansion['file'], 'r') as mainobbfile:
					# need to load the full obb into memory, otherwise it has to constantly read the whole obb again and performance gets shit
					mainobb_filedata = io.BytesIO(mainobbfile.read())
					
					with ZipFile(mainobb_filedata, 'r') as main_obb:
						unpack(main_obb, client, allow_older_version)
		else:
			print("Could not determine client from xapk manifest.json.")


def extract(path: Path, fallback_client: Client = None, allow_older_version: bool = False):
	if not path.exists():
		sys.exit('This file does not exist.')

	if path.suffix == '.obb':
		print('File has .obb extension.')
		extract_obb(path, fallback_client, allow_older_version)
	elif path.suffix == '.apk':
		if fallback_client:
			apk_client = fallback_client
			print(f"File has .apk extension, using provided fallback client {apk_client.name}.")
		else:
			apk_client = Client.CN
			print(f"File has .apk extension and no fallback client has been provided, assuming {apk_client.name} client.")

		with ZipFile(path, 'r') as zipfile:
			unpack(zipfile, apk_client, allow_older_version)
	elif path.suffix == '.xapk':
		print('File has .xapk extension.')
		extract_xapk(path, allow_older_version)
	else:
		sys.exit(f'Unknown file extension "{path.suffix}".')


def main():
	parser = ArgumentParser()
	parser.add_argument('file', nargs=1, help='xapk/apk/obb file to extract')
	parser.add_argument('-c', '--client', help='fallback client if it cannot be determined automatically (obb/apk only)', choices=Client.__members__)
	parser.add_argument('--allow_old_version', help='when enabled, the old version check is not used', action=BooleanOptionalAction)
	args = parser.parse_args()
	extract(Path(args.file[0]), args.client, args.allow_old_version)

if __name__ == "__main__":
	main()
