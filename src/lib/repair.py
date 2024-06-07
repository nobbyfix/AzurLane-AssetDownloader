import hashlib
import itertools
from pathlib import Path
from typing import Generator

from lib import updater, versioncontrol
from lib.classes import HashRow, UserConfig, VersionResult, VersionType, UpdateResult


def calc_md5hash(filepath: Path, buf_size: int = 65536) -> str:
	md5 = hashlib.md5()
	with open(filepath, 'rb') as f:
		while data := f.read(buf_size):
			md5.update(data)
	return md5.hexdigest()

def get_filedata(filepath: Path) -> tuple[str, int]:
	if filepath.exists():
		current_md5 = calc_md5hash(filepath)
		current_size = filepath.stat().st_size
		return current_md5, current_size
	else:
		return "", 0

def hashrow_from_file(assetbasepath: Path, filepath: Path) -> HashRow:
	current_md5, current_size = get_filedata(filepath)
	clean_filepath = str(filepath.relative_to(assetbasepath)).replace("\\", "/")
	return HashRow(clean_filepath, current_size, current_md5)

def hashrows_from_files(client_directory: Path) -> Generator[HashRow, None, None]:
	assetbasepath = Path(client_directory, "AssetBundles")
	for filepath in assetbasepath.rglob("*"):
		if not filepath.is_dir():
			yield hashrow_from_file(assetbasepath, filepath)

def repair(cdnurl: str, userconfig: UserConfig, client_directory: Path):
	current_hashes = hashrows_from_files(client_directory)
	expected_hashes = itertools.chain(*filter(lambda x: x is not None, [versioncontrol.load_hash_file(vtype, client_directory) for vtype in VersionType]))
	comparison_results = updater.compare_hashes(current_hashes, expected_hashes)
	update_results = updater.update_assets(cdnurl, comparison_results, userconfig, client_directory)
	return update_results

def repair_hashfile(version_result: VersionResult, cdnurl: str, userconfig: UserConfig, client_directory: Path) -> list[UpdateResult]:
	newhashes = updater.download_hashes(version_result, cdnurl, userconfig)
	assetbasepath = Path(client_directory, "AssetBundles")
	
	oldhashes = []
	for hrow in newhashes:
		fp = Path(assetbasepath, hrow.filepath)
		current_md5, current_size = get_filedata(fp)
		oldhrow = HashRow(hrow.filepath, current_size, current_md5)
		oldhashes.append(oldhrow)
	
	return updater._update_from_hashes(version_result, cdnurl, userconfig, client_directory, oldhashes, newhashes, allow_deletion=False)
