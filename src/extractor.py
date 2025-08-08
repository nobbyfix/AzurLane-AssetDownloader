#!/usr/bin/env python
import itertools, json
from argparse import ArgumentParser
from pathlib import Path
import multiprocessing as mp
from typing import Iterable, Generator

from azlassets import __version__, imgrecon, config, versioncontrol
from azlassets.classes import Client, VersionType


def get_difflog_versionlist(parent_directory: Path, vtype: VersionType) -> list[str]:
	difflog_dir = Path(parent_directory, "difflog", vtype.name.lower())
	# make sure latest.json does not exist anymore before retrieving file list
	versioncontrol.legacy_rename_latest_difflog(difflog_dir)
	difflog_versionlist = [path.stem for path in difflog_dir.glob("*.json")]
	return difflog_versionlist

def get_diff_files(parent_directory: Path, vtype: VersionType, version_string: str | None = None) -> Iterable[str]:
	if not version_string:
		version_string = versioncontrol.get_latest_versionstring(vtype, parent_directory)

	if version_string:
		difflog_path = parent_directory / "difflog" / vtype.name.lower() / version_string+".json"
		if difflog_path.exists():
			with open(difflog_path, "r", encoding="utf8") as f:
				diffdata = json.load(f)
				filtered_success_file_entries = filter((lambda i: i[1] != "Deleted"), diffdata["success_files"].items())
				filenames = [i[0] for i in filtered_success_file_entries]
				return filenames
		elif version_string is not None:
			raise FileExistsError(f"There is no difflog '{version_string}' for version type '{vtype.name}'")
	return []


def restore_painting(image, abpath: Path, imgname: str, do_retry: bool):
	mesh = imgrecon.load_mesh(str(abpath), imgname+'-mesh')
	if mesh is not None:
		return imgrecon.recon(image, mesh)

	if not do_retry:
		return image

	# for some images, the mesh is in the non-tex asset bundle for some reason
	if abpath.name.endswith('_tex'):
		return restore_painting(image, abpath.with_name(abpath.name[:-4]), imgname, False)

	return restore_painting(image, abpath.with_name(abpath.name+'_tex'), imgname, False)

def try_safe_image(image, target: Path) -> Path:
	target.parent.mkdir(parents=True, exist_ok=True)
	while True:
		if target.exists():
			print(f'ERROR: Tried to save "{target}", but the file already exists.')
			target = target.with_name(target.stem + "_" + target.suffix)
		else:
			image.save(target)
			return target

def extract_assetbundle(rootfolder: Path, filepath: str, targetfolder: Path) -> Path | None:
	all_images = []
	abpath = rootfolder / filepath
	for reader, texture2d in imgrecon.load_images(str(abpath)):
		name = texture2d.m_Name
		if name == 'UISprite': continue # skip the UISprite element
		if 'char' in (reader.container or ''): continue # skip image if its of a chibi

		image = texture2d.image
		if filepath.split('/')[0] == 'painting':
			image = restore_painting(image, abpath, name, True)
		all_images.append((image, name))

	if len(all_images) == 1:
		image, imgname = all_images[0]
		target = (targetfolder / filepath).parent / imgname+'.png'
		return try_safe_image(image, target)

	if len(all_images) > 1:
		img_target_dir = (targetfolder / filepath).parent / abpath.name
		for image, imgname in all_images:
			target = img_target_dir / imgname+'.png'
			try_safe_image(image, target)
		return img_target_dir


def extract_by_client(client: Client, target_version: str | None = None, do_iterative_version_check: bool = False):
	userconfig = config.load_user_config()
	client_directory = Path(userconfig.asset_directory, client.name)
	extract_directory = Path(userconfig.extract_directory, client.name)

	downloaded_files_collection = []
	if target_version is None or target_version == "latest":
		target_versiontypes = [VersionType.AZL, VersionType.PAINTING, VersionType.MANGA, VersionType.PIC]
	else:
		target_versiontypes = [VersionType.AZL]

	for vtype in target_versiontypes:
		if do_iterative_version_check:
			version_strings = []
			for vstring in get_difflog_versionlist(client_directory, vtype):
				if versioncontrol.compare_version_string(vstring, target_version) or vstring == target_version:
					version_strings.append(vstring)
		else:
			version_strings = [target_version]

		for vstring in version_strings:
			downloaded_files = get_diff_files(client_directory, vtype, vstring)
			downloaded_files_collection.append(downloaded_files)
	downloaded_files_collection = itertools.chain(*downloaded_files_collection)

	def _filter(assetpath: str) -> bool:
		if assetpath.split('/')[0] in userconfig.extract_filter:
			return (not userconfig.extract_isblacklist)
		return userconfig.extract_isblacklist

	with mp.Pool(processes=mp.cpu_count()-1) as pool:
		for assetpath in filter(_filter, downloaded_files_collection):
			pool.apply_async(extract_assetbundle, (client_directory / 'AssetBundles', assetpath, extract_directory,))

		# explicitly join pool
		# this causes the pool to wait for all asnyc tasks to complete
		pool.close()
		pool.join()

def extract_single_assetbundle(client: Client, assetpath: str) -> None:
	userconfig = config.load_user_config()
	client_directory = Path(userconfig.asset_directory, client.name, 'AssetBundles')
	extract_directory = Path(userconfig.extract_directory, client.name)

	abpath = Path(client_directory, assetpath)
	if abpath.is_dir():
		for ab_in_dir_path in abpath.rglob("*"):
			if not ab_in_dir_path.is_dir():
				extract_assetbundle(client_directory, str(ab_in_dir_path.relative_to(client_directory)), extract_directory)
	else:
		extract_assetbundle(client_directory, assetpath, extract_directory)


def main():
	print(f"Running Azurlane file extractor v{__version__}.")

	# setup argument parser
	parser = ArgumentParser(description="Extracts image assets as pngs.",
		epilog="If '-f/--filepath' is not set, all files from the latest update will be extracted.")
	parser.add_argument("client", type=str, choices=Client.__members__,
		help="client to extract files of")
	parser.add_argument("-f", "--filepath", type=str,
		help="Path to the file or directly to extract only single file or all directory content")
	parser.add_argument("-v", "--version", type=str,
		help="Extract files of a specific version (Currently only applies to AZL Versiontype!)")
	parser.add_argument("-u", "--until-version", type=str,
		help="Extract files from the latest until a specific version (Currently only applies to AZL Versiontype!)")
	args = parser.parse_args()

	# parse arguments and execute
	client = Client[args.client]
	if filepath := args.filepath:
		extract_single_assetbundle(client, filepath)
	else:
		if version := args.until_version:
			extract_by_client(client, version, True)
		elif version := args.version:
			extract_by_client(client, version)
		else:
			extract_by_client(client)

if __name__ == "__main__":
	main()
