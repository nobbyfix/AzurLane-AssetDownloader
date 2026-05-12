import asyncio
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from . import downloader, versioncontrol
from .classes import BundlePath, CompareResult, CompareType, DownloadType, HashRow, UpdateResult, UserConfig, VersionResult


def delete_asset_safe(filepath: Path):
	"""
	Delete an asset, printing a warning instead of raising if it doesn't exist.

	Args:
		filepath: Path to the file to delete
	"""
	try:
		filepath.unlink()
	except FileNotFoundError:
		print(f"WARN: Tried to remove non-existant asset at {filepath}")


downloader_semaphore = asyncio.Semaphore(6)


async def handle_asset_download(
	downloader_session: downloader.AzurlaneAsyncDownloader, assetbasepath: Path, result: CompareResult
) -> UpdateResult:
	"""
	Handle downloading a single asset.

	Args:
		downloader_session: Active downloader session
		assetbasepath: Root directory for asset bundles
		result: Compare result providing the new hash and file path

	Returns:
		UpdateResult: The update result
	"""
	newhash = result.new_hash
	if newhash is None:
		raise ValueError(f"ERROR: New hash for {result} is None!")

	assetpath = BundlePath.construct(assetbasepath, newhash.filepath)
	async with downloader_semaphore:  # prevent queueing into connection pool, since wait time in pool counts towards timeout
		download_success = await downloader_session.download_asset(newhash.md5hash, assetpath.full, newhash.size)

	return UpdateResult(result, DownloadType.Success if download_success else DownloadType.Failed, assetpath)


async def update_assets(
	downloader_session: downloader.AzurlaneAsyncDownloader,
	comparison_results: dict[CompareType, list[CompareResult]],
	client_directory: Path,
	allow_deletion: bool = True,
) -> list[UpdateResult]:
	"""
	Apply a full set of comparison results: download new/changed files and handle deletions.

	Args:
		downloader_session: Active downloader session
		comparison_results: Output of :func:`compare_hashes`
		client_directory: Client root directory
		allow_deletion: Whether to allow deletion of files

	Returns:
		list[UpdateResult]: The list of update results
	"""
	assetbasepath = Path(client_directory, "AssetBundles")
	update_results = [
		UpdateResult(r, DownloadType.NoChange, BundlePath.construct(assetbasepath, r.new_hash.filepath))  # pyright: ignore [reportOptionalMemberAccess]
		for r in comparison_results[CompareType.Unchanged]
	]

	# handle all new or changed files
	update_files = comparison_results[CompareType.New] + comparison_results[CompareType.Changed]
	if len(update_files) > 0:
		tasks = [handle_asset_download(downloader_session, assetbasepath, result) for result in update_files]
		update_results += await tqdm_asyncio.gather(*tasks, desc="Download Progress", unit="files")

	# handle all deleted files
	deleted_files = comparison_results[CompareType.Deleted]
	if len(deleted_files) > 0:
		if allow_deletion:
			with tqdm(total=len(deleted_files), desc="Deletion Progress", unit="files") as progressbar:
				for result in deleted_files:
					assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)  # pyright: ignore [reportOptionalMemberAccess]
					delete_asset_safe(assetpath.full)
					update_results.append(UpdateResult(result, DownloadType.Removed, assetpath))
					progressbar.update()
		else:
			for result in deleted_files:
				assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)  # pyright: ignore [reportOptionalMemberAccess]
				update_results.append(UpdateResult(result, DownloadType.ForDeletionNoChange, assetpath))

	return update_results


async def download_and_parse_hashes(
	version_result: VersionResult, downloader_session: downloader.AzurlaneAsyncDownloader, userconfig: UserConfig
) -> list[HashRow] | None:
	"""
	Download, filter, and parse the hash file for a version.

	Args:
		version_result: Version whose hash file should be fetched
		downloader_session: Active downloader session
		userconfig: The user configuration

	Returns:
		list[HashRow] or None: Filtered hash rows, or None if the server returned an empty response
	"""
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
	"""
	Diff two hash lists and classify each file as New, Changed, Unchanged, or Deleted.

	Args:
		oldhashes: Previously stored hash rows
		newhashes: New hash rows to compare to

	Returns:
		dict[CompareType, list[CompareResult]]: Results grouped by compare type
	"""
	results = {row.filepath: CompareResult(None, row, CompareType.New) for row in newhashes}
	for hashrow in oldhashes:
		res = results.get(hashrow.filepath)
		if res is None:
			results[hashrow.filepath] = CompareResult(hashrow, None, CompareType.Deleted)
		elif hashrow == res.new_hash:
			res.current_hash = hashrow
			res.compare_type = CompareType.Unchanged
		else:  # file has changed
			res.current_hash = hashrow
			res.compare_type = CompareType.Changed

	sorted_results = defaultdict(list)
	for r in results.values():
		sorted_results[r.compare_type].append(r)
	return sorted_results


def filter_hashes(update_results: list[UpdateResult]) -> list[HashRow]:
	"""
	Derive the updated hash list from a set of update results.

	Uses ``new_hash`` for successful and unchanged files, ``current_hash`` for
	files pending deletion (``ForDeletionNoChange``) or failed downloads.
	Failed downloads with no ``current_hash`` are dropped entirely. Emits a
	warning for any unexpectedly empty hash row.

	Args:
		update_results: Results produced by :func:`update_assets`

	Returns:
		list[HashRow]: Hash rows representing the current on-disk state
	"""
	hashes_updated = []
	for update_result in update_results:
		if update_result.download_type in {DownloadType.Success, DownloadType.NoChange}:
			hashrow = update_result.compare_result.new_hash
		elif update_result.download_type == DownloadType.ForDeletionNoChange:
			hashrow = update_result.compare_result.current_hash
		elif update_result.download_type == DownloadType.Failed:
			hashrow = update_result.compare_result.current_hash
			if not hashrow:
				continue
		else:
			continue

		# ensure hashrow is not None
		if hashrow:
			hashes_updated.append(hashrow)

	return hashes_updated


async def _update_from_hashes(
	version_result: VersionResult,
	downloader_session: downloader.AzurlaneAsyncDownloader,
	versioncontroller: versioncontrol.VersionController,
	oldhashes: Iterable[HashRow],
	newhashes: Iterable[HashRow],
	allow_deletion: bool = True,
) -> list[UpdateResult]:
	"""
	Compare hashes, download/delete assets, and persist the updated version data.

	Composes :func:`compare_hashes`, :func:`update_assets`, :func:`filter_hashes`,
	and ``versioncontroller.update_version_data`` into a single operation.

	Args:
		version_result: Version to update
		downloader_session: Active downloader session
		versioncontroller: Used to persist the updated hash file and version string
		oldhashes: Previously stored hash rows
		newhashes: New hash rows to compare to
		allow_deletion: Whether to allow deletion of files

	Returns:
		list[UpdateResult]: The list of update results
	"""
	comparison_results = compare_hashes(oldhashes, newhashes)
	update_results = await update_assets(
		downloader_session, comparison_results, versioncontroller.client_directory, allow_deletion
	)
	hashes_updated = filter_hashes(update_results)
	versioncontroller.update_version_data(version_result, hashes_updated)
	return update_results


async def _update(
	version_result: VersionResult,
	downloader_session: downloader.AzurlaneAsyncDownloader,
	userconfig: UserConfig,
	versioncontroller: versioncontrol.VersionController,
	ignore_hashfile: bool = False,
) -> list[UpdateResult] | None:
	"""
	Download the server hash file and run an update if it is non-empty.

	When ``ignore_hashfile`` is True, the local hash file is skipped and all
	server files are treated as new. Returns None if the server hash file is
	empty.

	Args:
		version_result: Version to update
		downloader_session: Active downloader session
		userconfig: The user configuration
		versioncontroller: Used to load the local hash file and persist results
		ignore_hashfile: If True, treat all server files as new regardless of local state

	Returns:
		list[UpdateResult] or None: List of update results, or None if the server returned an empty hash file
	"""
	newhashes = await download_and_parse_hashes(version_result, downloader_session, userconfig)
	if newhashes:
		if ignore_hashfile:
			oldhashes = []
		else:
			oldhashes = versioncontroller.load_hash_file(version_result.version_type)
		return await _update_from_hashes(version_result, downloader_session, versioncontroller, oldhashes or [], newhashes)


async def update(
	version_result: VersionResult,
	downloader_session: downloader.AzurlaneAsyncDownloader,
	userconfig: UserConfig,
	versioncontroller: versioncontrol.VersionController,
	force_refresh: bool = False,
	ignore_hashfile: bool = False,
) -> list[UpdateResult] | None:
	"""
	Update a version type if the server version is newer than the local one.

	Compares ``version_result.version`` against the locally stored version
	string. Skips the update and returns None if already up to date, unless
	``force_refresh`` is True.

	Args:
		version_result: Version to update
		downloader_session: Active downloader session
		userconfig: The user configuration
		versioncontroller: Used to load the local version string and persist results
		force_refresh: If True, run the update even when the local version is current
		ignore_hashfile: If True, treat all server files as new regardless of local state

	Returns:
		list[UpdateResult] or None:  List of update results, or None if skipped
	"""
	oldversion = versioncontroller.load_version_string(version_result.version_type)
	if versioncontrol.compare_version_string(version_result.version, oldversion):
		print(
			f"{version_result.version_type.name}: Current version {oldversion} is older than latest version {version_result.version}."
		)
		return await _update(version_result, downloader_session, userconfig, versioncontroller, ignore_hashfile)
	else:
		print(f"{version_result.version_type.name}: Current version {oldversion} is latest. ", end="")
		if force_refresh:
			print("(force check enabled: Try downloading files anyway.)")
			return await _update(version_result, downloader_session, userconfig, versioncontroller, ignore_hashfile)
		else:
			print("(Nothing to check.)")
