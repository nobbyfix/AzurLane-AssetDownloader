#!/usr/bin/env python3.9
import itertools, json
from argparse import ArgumentParser
from pathlib import Path
import multiprocessing as mp
from typing import Iterable

from lib import imgrecon, config
from lib.classes import Client, VersionType


def get_diff_files(parent_directory: Path, vtype: VersionType, version_string: str = None) -> Iterable[str]:
	if version_string:
		p = Path(parent_directory, "difflog", vtype.name.lower(), version_string+".json")
	else:
		p = Path(parent_directory, "difflog", vtype.name.lower(), "latest.json")

	if p.exists():
		with open(p, "r", encoding="utf8") as f:
			diffdata = json.load(f)
			return diffdata["success_files"].keys()
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

def extract_assetbundle(rootfolder: Path, filepath: str, targetfolder: Path) -> Path:
	all_images = []
	abpath = Path(rootfolder, filepath)
	for imageobj in imgrecon.load_images(str(abpath)):
		if imageobj.name == 'UISprite': continue # skip the UISprite element
		if 'char' in (imageobj.container or ''): continue # skip image if its of a chibi

		image = imageobj.image
		if filepath.split('/')[0] == 'painting':
			image = restore_painting(image, abpath, imageobj.name, True)
		all_images.append((image, imageobj.name))

	if len(all_images) == 1:
		image, imgname = all_images[0]
		target = Path(Path(targetfolder, filepath).parent, imgname+'.png')
		return try_safe_image(image, target)

	if len(all_images) > 1:
		img_target_dir = Path(Path(targetfolder, filepath).parent, abpath.name)
		for image, imgname in all_images:
			target = Path(img_target_dir, imgname+'.png')
			try_safe_image(image, target)
		return img_target_dir


def extract_by_client(client: Client):
	userconfig = config.load_user_config()
	client_directory = Path(userconfig.asset_directory, client.name)
	extract_directory = Path(userconfig.extract_directory, client.name)

	downloaded_files_collection = []
	for vtype in [VersionType.AZL, VersionType.PAINTING, VersionType.MANGA, VersionType.PIC]:
		downloaded_files = get_diff_files(client_directory, vtype)
		downloaded_files_collection.append(downloaded_files)
	downloaded_files_collection = itertools.chain(*downloaded_files_collection)

	def _filter(assetpath: str):
		if assetpath.split('/')[0] in userconfig.extract_filter:
			return (not userconfig.extract_isblacklist)
		return userconfig.extract_isblacklist

	with mp.Pool(processes=mp.cpu_count()-1) as pool:
		for assetpath in filter(_filter, downloaded_files_collection):
			pool.apply_async(extract_assetbundle, (Path(client_directory, 'AssetBundles'), assetpath, extract_directory,))

		# explicitly join pool
		# this causes the pool to wait for all asnyc tasks to complete
		pool.close()
		pool.join()

def extract_single_assetbundle(client: Client, assetpath: str):
	userconfig = config.load_user_config()
	client_directory = Path(userconfig.asset_directory, client.name, 'AssetBundles')
	extract_directory = Path(userconfig.extract_directory, client.name)
	return extract_assetbundle(client_directory, assetpath, extract_directory)


def main():
	# setup argument parser
	parser = ArgumentParser(description="Extracts image assets as pngs.",
		epilog="If '-f/--filepath' is not set, all files from the latest update will be extracted.")
	parser.add_argument("client", type=str, choices=Client.__members__,
		help="client to extract files of")
	parser.add_argument("-f", "--filepath", type=str,
		help="Path to the file to extract only this single file")
	args = parser.parse_args()

	# parse arguments and execute
	client = Client[args.client]
	if filepath := args.filepath:
		extract_single_assetbundle(client, filepath)
	else:	
		extract_by_client(client)

if __name__ == "__main__":
	main()
