import hashlib
import itertools
import aiofile
import asyncio
from pathlib import Path

from . import downloader, updater, versioncontrol
from .classes import *


async def execute_coro_with_progressbar(coro, progressbar: ProgressBar):
	r = await coro
	progressbar.update()
	return r


semaphore_concurrent_files = asyncio.Semaphore(5)

async def calc_md5hash(filepath: Path, chunk_size: int = 65536) -> str:
	md5 = hashlib.md5()
	async with semaphore_concurrent_files:
		async with aiofile.async_open(filepath, "rb") as f:
			async for chunk in f.iter_chunked(chunk_size):
				if chunk:
					md5.update(chunk)
	return md5.hexdigest()

async def get_filedata(filepath: Path) -> tuple[str, int]:
	if filepath.exists():
		current_md5 = await calc_md5hash(filepath)
		current_size = filepath.stat().st_size
		return current_md5, current_size
	else:
		return "", 0

async def hashrow_from_file(assetbasepath: Path, filepath: Path) -> HashRow:
	current_md5, current_size = await get_filedata(filepath)
	clean_filepath = str(filepath.relative_to(assetbasepath)).replace("\\", "/")
	return HashRow(clean_filepath, current_size, current_md5)

async def hashrow_from_relative_file(assetbasepath: Path, relative_filepath: Path) -> HashRow:
	current_md5, current_size = await get_filedata(assetbasepath / relative_filepath)
	return HashRow(relative_filepath, current_size, current_md5)

async def hashrows_from_files(client_directory: Path) -> list[HashRow]:
	assetbasepath = client_directory / "AssetBundles"
	progressbar = ProgressBar(0, "File Progress", details_unit="files", print_on_init=False)
	print("Loading list of all files... ", end="")
	tasks = [execute_coro_with_progressbar(hashrow_from_file(assetbasepath, fp), progressbar) for fp in assetbasepath.rglob("*") if not fp.is_dir()]
	progressbar.total = len(tasks)
	print("Done")
	print("Checking all files...")
	return await asyncio.gather(*tasks)

async def repair(cdnurl: str, userconfig: UserConfig, client_directory: Path) -> list[UpdateResult]:
	current_hashes = await hashrows_from_files(client_directory)
	expected_hashes = itertools.chain(*filter(lambda x: x is not None, [versioncontrol.load_hash_file(vtype, client_directory) for vtype in VersionType]))
	comparison_results = updater.compare_hashes(current_hashes, expected_hashes)
	async with downloader.AzurlaneAsyncDownloader(cdnurl, useragent=userconfig.useragent) as downloader_session:
		update_results = await updater.update_assets(downloader_session, comparison_results, client_directory)
	return update_results

async def repair_hashfile(version_result: VersionResult, cdnurl: str, userconfig: UserConfig, client_directory: Path) -> list[UpdateResult]:
	# read hashes that are stored in the local hash file
	localhashes = versioncontrol.load_hash_file(version_result.version_type, client_directory)

	async with downloader.AzurlaneAsyncDownloader(cdnurl, useragent=userconfig.useragent) as downloader_session:
		# load newest hashes from the game server
		serverhashes = await updater.download_and_parse_hashes(version_result, downloader_session, userconfig) or []
		assetbasepath = client_directory / "AssetBundles"

		# parse hashes from all files stored on disk, but only check files that are expected based on the new hashes
		# this skips deletion on unneeded files
		print("Generating hashes for all files on disk...")
		progressbar = ProgressBar(len(serverhashes), "File Progress", details_unit="files")
		diskhashes_tasks = [execute_coro_with_progressbar(hashrow_from_relative_file(assetbasepath, hrow.filepath), progressbar) for hrow in serverhashes]
		diskhashes = await asyncio.gather(*diskhashes_tasks)

		# compare localhashes to diskhashes to determine which files have already been successfully downloaded
		compare_results_disk = updater.compare_hashes(localhashes, diskhashes)
		update_results_disk = {comp_result.new_hash.filepath: UpdateResult(comp_result, DownloadType.Success, comp_result.new_hash.filepath) for comp_result in compare_results_disk[CompareType.Changed]}
		update_results_disk.update({comp_result.new_hash.filepath: UpdateResult(comp_result, DownloadType.Success, comp_result.new_hash.filepath) for comp_result in compare_results_disk[CompareType.New]})
		update_results_disk.update({comp_result.current_hash.filepath: UpdateResult(comp_result, DownloadType.Removed, comp_result.current_hash.filepath) for comp_result in compare_results_disk[CompareType.Deleted]})

		# download remaining files
		update_results_server = await updater._update_from_hashes(version_result, downloader_session, client_directory, diskhashes, serverhashes, allow_deletion=False)

		# add old update results to new update results list
		update_results = []
		for upres_server in update_results_server:
			update_result = upres_server
			# try to retrieve from old list only if there was no further change to the file
			if upres_server.download_type == DownloadType.NoChange:
				if upres_disk := update_results_disk.get(upres_server.path):
					update_result = upres_disk
			update_results.append(update_result)

	return update_results
