import aiofile
import aiohttp
import traceback
from pathlib import Path

from .classes import VersionResult


def get_chunk_size(file_size: int) -> int:
	"""
	Return an appropriate chunk size for streaming a file of the given size.

	Args:
		file_size: Expected file size in bytes

	Returns:
		int: Chunk size in bytes
	"""
	if file_size <= 16_384:  # ≤ 16 KB (~50% files) -> one chunk
		return file_size or 1024  # fallback for 0-byte files
	if file_size <= 131_072:  # ≤ 128 KB (~35% files) -> 64 KB
		return 65_536
	if file_size <= 4_194_304:  # ≤ 4 MB: (~14% files) -> 256 KB
		return 262_144
	return 1_048_576  # > 4 MB (top ~1% files): -> 1 MB


class AzurlaneAsyncDownloader(aiohttp.ClientSession):
	"""
	Async HTTP client for downloading Azur Lane assets and hash files.

	Extends :class:`aiohttp.ClientSession` with a base URL of``{cdn_url}/android/``.
	"""

	def __init__(self, cdn_url: str, useragent: str):
		base_url = f"{cdn_url}/android/"
		limited_tcp_connector = aiohttp.TCPConnector(limit_per_host=10, enable_cleanup_closed=True)
		timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=10)
		super().__init__(base_url=base_url, headers={"user-agent": useragent}, connector=limited_tcp_connector, timeout=timeout)

	async def get_hashes(self, versionhash: str) -> aiohttp.ClientResponse:
		"""
		Send a GET request for a hash list file at ``hash/{versionhash}``.

		Args:
			versionhash: The raw version hash string identifying the file

		Returns:
			aiohttp.ClientResponse: The raw response
		"""
		return await self.get(f"hash/{versionhash}")

	async def get_asset(self, filehash: str) -> aiohttp.ClientResponse:
		"""
		Send a GET request for an asset file at ``resource/{filehash}``.

		Args:
			filehash: The file hash identifying the asset

		Returns:
			aiohttp.ClientResponse: The raw response
		"""
		return await self.get(f"resource/{filehash}")

	async def download_hashes(self, version_result: VersionResult) -> str | None:
		"""
		Download and return the hash file for a version result.
		Prints an error and traceback to stdout on any exception.

		Args:
			version_result: The version result whose hash file should be fetched

		Returns:
			str or None: The full hash file text on success, None on failure
		"""
		try:
			async with await self.get_hashes(version_result.rawstring) as response:
				response: aiohttp.ClientResponse
				response.raise_for_status()  # raises error on bad HTTP status

				hashes = await response.text()
				return hashes

		except Exception as e:
			print(f"ERROR: An unexpected error occured while downloading '{version_result.version_type.name}' hashfile.")
			traceback.print_exception(type(e), e, e.__traceback__)
			return

	async def download_asset(self, filehash: str, save_destination: Path, expected_file_size: int, _retry_count: int = 0) -> bool:
		"""
		Download an asset file and write it to disk.
		Prints an error and traceback to stdout on any exception.

		Args:
			filehash: The file hash identifying the asset
			save_destination: Path where the file will be written
			expected_file_size: Expected ``Content-Length`` in bytes; mismatch aborts the download

		Returns:
			bool: True on success, False otherwise
		"""
		try:
			async with await self.get_asset(filehash) as response:
				response.raise_for_status()  # raises error on bad HTTP status

				# reject response if response size doesn't match expected size
				response_size = response.content_length
				if expected_file_size != response_size:
					print(
						f"ERROR: Received asset '{filehash}' with target '{save_destination}' has wrong size ({response_size}/{expected_file_size})."
					)
					return False

				save_destination.parent.mkdir(parents=True, exist_ok=True)
				async with aiofile.async_open(save_destination, "wb") as file:
					# adjust chunksize based on filesize to reduce over-buffer for small files
					# and syscalls for large files
					chunksize = get_chunk_size(expected_file_size)
					async for chunk in response.content.iter_chunked(chunksize):
						await file.write(chunk)

			return True
		except TimeoutError:
			if _retry_count < 2:
				return await self.download_asset(filehash, save_destination, expected_file_size, _retry_count + 1)
			print(
				f"ERROR: Connection timed out 3 times while downloading '{filehash}' to '{save_destination}'. Aborting file download."
			)
			return False
		except Exception as e:
			print(f"ERROR: An unexpected error occured while downloading '{filehash}' to '{save_destination}'.")
			traceback.print_exception(type(e), e, e.__traceback__)
			return False

	# override return type from superclass
	async def __aenter__(self) -> "AzurlaneAsyncDownloader":
		return await super().__aenter__()  # pyright: ignore [reportReturnType]
