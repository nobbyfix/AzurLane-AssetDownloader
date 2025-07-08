import hashlib
import itertools
import aiofile
import asyncio
from pathlib import Path

from . import downloader, updater, versioncontrol
from .classes import HashRow, UserConfig, VersionResult, VersionType, UpdateResult


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
	tasks = [hashrow_from_file(assetbasepath, fp) for fp in assetbasepath.rglob("*") if not fp.is_dir()]
	return await asyncio.gather(*tasks)

async def repair(cdnurl: str, userconfig: UserConfig, client_directory: Path) -> list[UpdateResult]:
	current_hashes = await hashrows_from_files(client_directory)
	expected_hashes = itertools.chain(*filter(lambda x: x is not None, [versioncontrol.load_hash_file(vtype, client_directory) for vtype in VersionType]))
	comparison_results = updater.compare_hashes(current_hashes, expected_hashes)
	async with downloader.AzurlaneAsyncDownloader(cdnurl, useragent=userconfig.useragent) as downloader_session:
		update_results = await updater.update_assets(downloader_session, comparison_results, client_directory)
	return update_results

async def repair_hashfile(version_result: VersionResult, cdnurl: str, userconfig: UserConfig, client_directory: Path) -> list[UpdateResult]:
	async with downloader.AzurlaneAsyncDownloader(cdnurl, useragent=userconfig.useragent) as downloader_session:
		newhashes = await updater.download_and_parse_hashes(version_result, downloader_session, userconfig) or []
		assetbasepath = client_directory / "AssetBundles"
		
		oldhashes_tasks = [hashrow_from_relative_file(assetbasepath, hrow.filepath) for hrow in newhashes]
		oldhashes = await asyncio.gather(*oldhashes_tasks)
		
		update_results = await updater._update_from_hashes(version_result, downloader_session, client_directory, oldhashes, newhashes, allow_deletion=False)
	return update_results
