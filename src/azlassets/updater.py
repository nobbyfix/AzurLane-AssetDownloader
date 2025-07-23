import asyncio
from pathlib import Path
from typing import Iterable
from collections import defaultdict

from . import downloader, versioncontrol
from .classes import *


def remove_asset(filepath: Path):
	if filepath.exists():
		filepath.unlink()
	else:
		print(f"WARN: Tried to remove non-existant asset at {filepath}")


downloader_semaphore = asyncio.Semaphore(6)

async def handle_asset_download(
		downloader_session: downloader.AzurlaneAsyncDownloader,
		assetbasepath: Path,
		result: CompareResult,
		progressbar: ProgressBar | None = None
	) -> UpdateResult:

	newhash = result.new_hash
	assert newhash is not None

	assetpath = BundlePath.construct(assetbasepath, newhash.filepath)
	async with downloader_semaphore:  # prevent queueing into connection pool, since wait time in pool counts towards timeout
		download_success = await downloader_session.download_asset(newhash.md5hash, assetpath.full, newhash.size)

	if progressbar:
		progressbar.update()
	return UpdateResult(result, DownloadType.Success if download_success else DownloadType.Failed, assetpath)


async def update_assets(
		downloader_session: downloader.AzurlaneAsyncDownloader,
		comparison_results: dict[CompareType, list[CompareResult]],
		client_directory: Path,
		allow_deletion: bool = True
	) -> list[UpdateResult]:

	assetbasepath = client_directory / "AssetBundles"
	update_results = [UpdateResult(r, DownloadType.NoChange, BundlePath.construct(assetbasepath, r.new_hash.filepath)) for r in comparison_results[CompareType.Unchanged]]

	# handle all new or changed files
	update_files = comparison_results[CompareType.New] + comparison_results[CompareType.Changed]
	if len(update_files) > 0:
		progressbar = ProgressBar(len(update_files), "Download Progress", details_unit="files")
		tasks = [handle_asset_download(downloader_session, assetbasepath, result, progressbar) for result in update_files]
		update_results += await asyncio.gather(*tasks)

	# handle all deleted files
	deleted_files = comparison_results[CompareType.Deleted]
	if len(deleted_files) > 0:
		if allow_deletion:
			progressbar = ProgressBar(len(deleted_files), "Deletion Progress", details_unit="files")
			for result in deleted_files:
				assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)
				remove_asset(assetpath.full)
				update_results.append(UpdateResult(result, DownloadType.Removed, assetpath))
				progressbar.update()
		else:
			for result in deleted_files:
				assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)
				update_results.append(UpdateResult(result, DownloadType.ForDeletionNoChange, assetpath))

	return update_results


async def download_and_parse_hashes(
		version_result: VersionResult,
		downloader_session: downloader.AzurlaneAsyncDownloader,
		userconfig: UserConfig
	) -> list[HashRow] | None:

	hashes = await downloader_session.download_hashes(version_result)
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


def compare_hashes(oldhashes: Iterable[HashRow], newhashes: Iterable[HashRow]) -> dict[CompareType, list[CompareResult]]:
	results = {row.filepath: CompareResult(None, row, CompareType.New) for row in newhashes}
	for hashrow in oldhashes:
		res = results.get(hashrow.filepath)
		if res is None:
			results[hashrow.filepath] = CompareResult(hashrow, None, CompareType.Deleted)
		elif hashrow == res.new_hash:
			res.current_hash = hashrow
			res.compare_type = CompareType.Unchanged
		else: # file has changed
			res.current_hash = hashrow
			res.compare_type = CompareType.Changed

	sorted_results = defaultdict(list)
	for r in results.values():
		sorted_results[r.compare_type].append(r)
	return sorted_results


def filter_hashes(update_results: list[UpdateResult]) -> list[HashRow]:
	hashes_updated = []
	for update_result in update_results:
		if update_result.download_type in [DownloadType.Success, DownloadType.NoChange]:
			hashrow = update_result.compare_result.new_hash
		elif update_result.download_type == DownloadType.ForDeletionNoChange:
			hashrow = update_result.compare_result.current_hash
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


async def _update_from_hashes(
		version_result: VersionResult,
		downloader_session: downloader.AzurlaneAsyncDownloader,
		client_directory: Path,
		oldhashes: Iterable[HashRow],
		newhashes: Iterable[HashRow],
		allow_deletion: bool = True
	) -> list[UpdateResult]:

	comparison_results = compare_hashes(oldhashes, newhashes)
	update_results = await update_assets(downloader_session, comparison_results, client_directory, allow_deletion)
	hashes_updated = filter_hashes(update_results)
	versioncontrol.update_version_data2(version_result, client_directory, hashes_updated)
	return update_results


async def _update(
		version_result: VersionResult,
		downloader_session: downloader.AzurlaneAsyncDownloader,
		userconfig: UserConfig,
		client_directory: Path,
		ignore_hashfile: bool = False
	) -> list[UpdateResult] | None:

	newhashes = await download_and_parse_hashes(version_result, downloader_session, userconfig)
	if newhashes:
		if ignore_hashfile:
			oldhashes = []
		else:
			oldhashes = versioncontrol.load_hash_file(version_result.version_type, client_directory)
		return await _update_from_hashes(version_result, downloader_session, client_directory, oldhashes or [], newhashes)


async def update(
		version_result: VersionResult,
		downloader_session: downloader.AzurlaneAsyncDownloader,
		userconfig: UserConfig,
		client_directory: Path,
		force_refresh: bool = False,
		ignore_hashfile: bool = False
	)-> list[UpdateResult] | None:

	oldversion = versioncontrol.load_version_string(version_result.version_type, client_directory)
	if versioncontrol.compare_version_string(version_result.version, oldversion):
		print(f"{version_result.version_type.name}: Current version {oldversion} is older than latest version {version_result.version}.")
		return await _update(version_result, downloader_session, userconfig, client_directory, ignore_hashfile)
	else:
		print(f"{version_result.version_type.name}: Current version {oldversion} is latest. ", end="")
		if force_refresh:
			print("(force check enabled: Try downloading files anyway.)")
			return await _update(version_result, downloader_session, userconfig, client_directory, ignore_hashfile)
		else:
			print("(Nothing to check.)")
