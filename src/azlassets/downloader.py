import aiohttp
import aiofile
import traceback
from pathlib import Path

from .classes import VersionResult


class AzurlaneAsyncDownloader(aiohttp.ClientSession):
	def __init__(self, cdn_url: str, useragent: str):
		base_url = f"{cdn_url}/android/"
		limited_tcp_connector = aiohttp.TCPConnector(limit_per_host=6)
		super().__init__(base_url=base_url, headers={"user-agent": useragent}, connector=limited_tcp_connector)

	async def get_hashes(self, versionhash: str) -> aiohttp.ClientResponse:
		return await self.get(f"hash/{versionhash}")

	async def get_asset(self, filehash: str) -> aiohttp.ClientResponse:
		return await self.get(f"resource/{filehash}")

	async def download_hashes(self, version_result: VersionResult) -> str | None:
		try:
			async with await self.get_hashes(version_result.rawstring) as response:
				response: aiohttp.ClientResponse
				response.raise_for_status() # raises error on bad HTTP status

				hashes = await response.text()
				return hashes

		except Exception as e:
			print(f"ERROR: An unexpected error occured while downloading '{version_result.version_type.name}' hashfile.")
			traceback.print_exception(type(e), e, e.__traceback__)
			return

	async def download_asset(self, filehash: str, save_destination: Path, expected_file_size: int) -> bool:
		"""
		Downloads the requested file using the session and saves it to 'save_destination' on disk.

		Returns `True` if the operation was successful, otherwise `False`.
		"""
		try:
			async with await self.get_asset(filehash) as response:
				response: aiohttp.ClientResponse
				response.raise_for_status() # raises error on bad HTTP status

				# reject response if response size doesn't match expected size
				response_size = response.content_length
				if expected_file_size != response_size:
					print(f"ERROR: Received asset '{filehash}' with target '{save_destination}' has wrong size ({response_size}/{expected_file_size}).")
					return False

				save_destination.parent.mkdir(parents=True, exist_ok=True)
				async with aiofile.async_open(save_destination, "wb") as file:
					async for chunk in response.content.iter_chunked(1024*16): # no idea what chuck size is best
						await file.write(chunk)

			return True
		except Exception as e:
			print(f"ERROR: An unexpected error occured while downloading '{filehash}' to '{save_destination}'.")
			traceback.print_exception(type(e), e, e.__traceback__)
			return False
