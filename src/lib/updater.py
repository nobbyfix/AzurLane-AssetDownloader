import traceback
from pathlib import Path
from typing import Iterable, Optional, Union

from . import downloader, versioncontrol
from .classes import *


def download_asset(cdnurl: str, filehash: str, useragent: str, save_destination: Path, size: int) -> Optional[Union[bytes, bool]]:
	try:
		assetbinary = downloader.download_asset(cdnurl, filehash, useragent)
		if assetbinary is None:
			print(f"ERROR: No response for asset '{filehash}' with target '{save_destination}'.")
			return False
		elif len(assetbinary) != size:
			print(f"ERROR: Received asset '{filehash}' with target '{save_destination}' has wrong size ({len(assetbinary)}/{size}).")
			return False

		save_destination.parent.mkdir(parents=True, exist_ok=True)
		with open(save_destination, 'wb') as f:
			f.write(assetbinary)
		return assetbinary
	except Exception as e:
		print(f"ERROR: An error occured while downloading '{filehash}' to '{save_destination}'.")
		traceback.print_exception(e, e, e.__traceback__)
		return False

def remove_asset(filepath: Path):
	if filepath.exists():
		filepath.unlink()
	else:
		print(f"WARN: Tried to remove non-existant asset at {filepath}")


def compare_hashes(oldhashes: Iterable[HashRow], newhashes: Iterable[HashRow]) -> dict[str, CompareResult]:
	results = {row.filepath: CompareResult(None, row, CompareType.New) for row in newhashes}
	for hashrow in oldhashes or []:
		res = results.get(hashrow.filepath)
		if res is None:
			results[hashrow.filepath] = CompareResult(hashrow, None, CompareType.Deleted)
		elif hashrow == res.new_hash:
			res.current_hash = hashrow
			res.compare_type = CompareType.Unchanged
		else: # file has changed
			res.current_hash = hashrow
			res.compare_type = CompareType.Changed
	return results


def update_assets(cdnurl: str, comparison_results: dict[str, CompareResult], userconfig: UserConfig, client_directory: Path, allow_deletion: bool = True) -> list[UpdateResult]:
	assetbasepath = Path(client_directory, "AssetBundles")
	update_files = list(filter(lambda r: r.compare_type != CompareType.Unchanged, comparison_results.values()))
	update_results = [UpdateResult(r, DownloadType.NoChange, BundlePath.construct(assetbasepath, r.new_hash.filepath)) for r in filter(lambda r: r.compare_type == CompareType.Unchanged, comparison_results.values())]

	fileamount = len(update_files)
	for i, result in enumerate(update_files, 1):
		if result.compare_type in [CompareType.New, CompareType.Changed]:
			print(f"Downloading {result.new_hash.filepath} ({i}/{fileamount}).")
			assetpath = BundlePath.construct(assetbasepath, result.new_hash.filepath)
			if download_asset(cdnurl, result.new_hash.md5hash, userconfig.useragent, assetpath.full, result.new_hash.size):
				update_results.append(UpdateResult(result, DownloadType.Success, assetpath))
			else:
				update_results.append(UpdateResult(result, DownloadType.Failed, assetpath))

		elif result.compare_type == CompareType.Deleted:
			if allow_deletion:
				print(f"Deleting {result.current_hash.filepath} ({i}/{fileamount}).")
				assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)
				remove_asset(assetpath.full)
				update_results.append(UpdateResult(result, DownloadType.Removed, assetpath))
			else:
				print(f"Deleting {result.current_hash.filepath} ({i}/{fileamount}) [SKIPPED].")
	return update_results

def download_hashes(version_result: VersionResult, cdnurl: str, userconfig: UserConfig):
	hashes = downloader.download_hashes(cdnurl, version_result.rawstring, userconfig.useragent)
	if not hashes:
		print(f"Server returned empty hashfile for {version_result.version_type.name}, skipping.")
		return

	# hash filter function
	def _filter(row: HashRow):
		for path in userconfig.download_filter:
			if row.filepath.startswith(path):
				if not userconfig.download_isblacklist:
					return True
		return userconfig.download_isblacklist

	return list(filter(_filter, versioncontrol.parse_hash_rows(hashes)))

def filter_hashes(update_results: list[UpdateResult]) -> list[HashRow]:
	hashes_updated = []
	for update_result in update_results:
		if update_result.download_type in [DownloadType.Success, DownloadType.NoChange]:
			hashrow = update_result.compare_result.new_hash
		elif update_result.download_type == DownloadType.Failed:
			hashrow = update_result.compare_result.current_hash
			if not hashrow:
				continue
		else:
			continue

		# some error checking, although it should not be needed anymore
		if hashrow:
			hashes_updated.append(hashrow)
		else:
			print("WARN: Empty hashrow detected while it should not have been empty. Debug info below.")
			print(update_result)
	return hashes_updated

def _update_from_hashes(version_result: VersionResult, cdnurl: str, userconfig: UserConfig, client_directory: Path,
						oldhashes: Iterable[HashRow], newhashes: Iterable[HashRow], allow_deletion: bool = True) -> list[UpdateResult]:
	comparison_results = compare_hashes(oldhashes, newhashes)
	update_results = update_assets(cdnurl, comparison_results, userconfig, client_directory, allow_deletion)
	hashes_updated = filter_hashes(update_results)
	versioncontrol.update_version_data2(version_result, client_directory, hashes_updated)
	return update_results

def _update(version_result: VersionResult, cdnurl: str, userconfig: UserConfig, client_directory: Path) -> list[UpdateResult]:
	newhashes = download_hashes(version_result, cdnurl, userconfig)
	oldhashes = versioncontrol.load_hash_file(version_result.version_type, client_directory)
	return _update_from_hashes(version_result, cdnurl, userconfig, client_directory, oldhashes, newhashes)

def update(version_result: VersionResult, cdnurl: str, userconfig: UserConfig, client_directory: Path, force_refresh: bool) -> list[UpdateResult]:
	oldversion = versioncontrol.load_version_string(version_result.version_type, client_directory)
	if oldversion == version_result.version:
		print(f"{version_result.version_type.name}: Current version {oldversion} is latest.")
		if force_refresh:
			return _update(version_result, cdnurl, userconfig, client_directory)
	else:
		print(f"{version_result.version_type.name}: Current version {oldversion} is older than latest version {version_result.version}.")
		return _update(version_result, cdnurl, userconfig, client_directory)
