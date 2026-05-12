import aiofile
import asyncio
import hashlib
import itertools
from pathlib import Path
from tqdm.asyncio import tqdm_asyncio

from . import downloader, updater, versioncontrol
from .classes import BundlePath, CompareType, DownloadType, HashRow, UpdateResult, UserConfig, VersionResult, VersionType

semaphore_concurrent_files = asyncio.Semaphore(16)


async def calc_md5hash(filepath: Path, chunk_size: int = 65536) -> str:
	"""
	Compute the MD5 hex digest of a file asynchronously.

	Args:
		filepath: Path to the file to hash
		chunk_size: Read chunk size in bytes (default 64 KB)

	Returns:
		str: The MD5 hash as a lowercase hexadecimal string
	"""
	md5 = hashlib.md5()
	async with semaphore_concurrent_files:
		async with aiofile.async_open(filepath, "rb") as f:
			async for chunk in f.iter_chunked(chunk_size):
				md5.update(chunk)  # pyright: ignore [reportArgumentType]
	return md5.hexdigest()


async def get_filedata(filepath: Path) -> tuple[str, int]:
	"""
	Return the MD5 hash and size of a file, or empty defaults if it doesn't exist.

	Args:
		filepath: Path to the file

	Returns:
		tuple[str, int]: ``(md5_hex, size_in_bytes)``, or ``("", 0)`` if the file is absent
	"""
	if filepath.exists():
		current_md5 = await calc_md5hash(filepath)
		current_size = filepath.stat().st_size
		return current_md5, current_size
	else:
		return "", 0


async def hashrow_from_file(assetbasepath: Path, filepath: Path) -> HashRow:
	"""
	Build a HashRow for a file using its absolute path.

	Args:
		assetbasepath: Root asset bundle directory, used to compute the relative path
		filepath: Absolute path to the file

	Returns:
		HashRow: File info containing the relative path, size, and MD5 hash
	"""
	current_md5, current_size = await get_filedata(filepath)
	clean_filepath = str(filepath.relative_to(assetbasepath)).replace("\\", "/")
	return HashRow(clean_filepath, current_size, current_md5)


async def hashrow_from_relative_file(assetbasepath: Path, relative_filepath: str) -> HashRow:
	"""
	Build a HashRow for a file using a path relative to ``assetbasepath``.

	Args:
		assetbasepath: Root asset bundle directory
		relative_filepath: File path relative to ``assetbasepath``

	Returns:
		HashRow: File info containing the relative path, size, and MD5 hash
	"""
	current_md5, current_size = await get_filedata(Path(assetbasepath, relative_filepath))
	return HashRow(relative_filepath, current_size, current_md5)


async def hashrows_from_files(client_directory: Path) -> list[HashRow]:
	"""
	Compute HashRows for every file under ``{client_directory}/AssetBundles/``.

	Args:
		client_directory: Client root directory

	Returns:
		list[HashRow]: List of hash rows
	"""
	assetbasepath = Path(client_directory, "AssetBundles")
	print("Loading list of all files... ", end="")
	filepaths = [fp for fp in assetbasepath.rglob("*") if fp.is_file()]
	tasks = [hashrow_from_file(assetbasepath, fp) for fp in filepaths]
	print("Done.\nChecking all files...")
	return await tqdm_asyncio.gather(*tasks, desc="File Progress", unit="files")


async def repair(
	downloader_session: downloader.AzurlaneAsyncDownloader, versioncontroller: versioncontrol.VersionController
) -> list[UpdateResult]:
	"""
	Full integrity repair: hash all files on disk and re-download anything that
	doesn't match the stored hash files.

	Args:
		downloader_session: Active downloader session
		versioncontroller: The version controller

	Returns:
		list[UpdateResult]: List of update results
	"""
	current_hashes = await hashrows_from_files(versioncontroller.client_directory)
	expected_hashes = itertools.chain.from_iterable(
		filter(None, [versioncontroller.load_hash_file(vtype) for vtype in VersionType])
	)
	comparison_results = updater.compare_hashes(current_hashes, expected_hashes)
	update_results = await updater.update_assets(downloader_session, comparison_results, versioncontroller.client_directory)
	return update_results


async def repair_hashfile(
	version_result: VersionResult,
	downloader_session: downloader.AzurlaneAsyncDownloader,
	userconfig: UserConfig,
	versioncontroller: versioncontrol.VersionController,
) -> list[UpdateResult]:
	"""
	Repair a single version type by reconciling local, disk, and server hashes.

	Args:
		version_result: Version type and string to repair
		downloader_session: Active downloader session
		userconfig: The user configuration
		versioncontroller: The version controller

	Returns:
		list[UpdateResult]: List of update results
	"""
	# read hashes that are stored in the local hash file
	localhashes = versioncontroller.load_hash_file(version_result.version_type) or []

	# load newest hashes from the game server
	serverhashes = await updater.download_and_parse_hashes(version_result, downloader_session, userconfig) or []
	assetbasepath = versioncontroller.client_directory / "AssetBundles"

	# parse hashes from all files stored on disk, but only check files that are expected based on the new hashes
	# this skips deletion on unneeded files
	print("Generating hashes for all files on disk...")
	diskhashes_tasks = [hashrow_from_relative_file(assetbasepath, hrow.filepath) for hrow in serverhashes]
	diskhashes = await tqdm_asyncio.gather(*diskhashes_tasks, desc="File Progress", unit="files")

	# compare localhashes to diskhashes to determine which files have already been successfully downloaded
	compare_results_disk = updater.compare_hashes(localhashes, diskhashes)
	_COMPARE_TO_DOWNLOAD_TYPE = {
		CompareType.Changed: (DownloadType.Success, "new_hash"),
		CompareType.New: (DownloadType.Success, "new_hash"),
		CompareType.Deleted: (DownloadType.Removed, "current_hash"),
	}

	update_results_disk = {}
	for comp_type, (download_type, hash_attr) in _COMPARE_TO_DOWNLOAD_TYPE.items():
		for comp_result in compare_results_disk[comp_type]:
			hashrow = getattr(comp_result, hash_attr)
			update_results_disk[hashrow.filepath] = UpdateResult(
				comp_result,
				download_type,
				BundlePath.construct(assetbasepath, hashrow.filepath),
			)

	# download remaining files
	update_results_server = await updater._update_from_hashes(
		version_result, downloader_session, versioncontroller, diskhashes, serverhashes, allow_deletion=False
	)

	# add old update results to new update results list
	update_results = []
	for upres_server in update_results_server:
		update_result = upres_server
		# try to retrieve from old list only if there was no further change to the file
		if upres_server.download_type == DownloadType.NoChange:
			if upres_disk := update_results_disk.get(str(upres_server.path)):
				update_result = upres_disk
		update_results.append(update_result)

	return update_results
