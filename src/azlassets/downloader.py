import httpx
import aiofile
import traceback
from pathlib import Path

from .classes import VersionResult


class AzurlaneAsyncDownloader(httpx.AsyncClient):
	def __init__(self, cdn_url: str, useragent: str):
		base_url = f"{cdn_url}/android/"
		limits = httpx.Limits(max_connections=6, max_keepalive_connections=6)
		super().__init__(
			http2=True,
			base_url=base_url,
			headers={"user-agent": useragent},
			limits=limits,
			timeout=httpx.Timeout(60.0)
		)

	async def download_hashes(self, version_result: VersionResult) -> str | None:
		url = f"hash/{version_result.rawstring}"
		try:
			response = await self.get(url)
			response.raise_for_status()
			return response.text

		except httpx.HTTPError as http_e:
			print(f"ERROR: An HTTP error occurred while downloading '{version_result.version_type.name}' hashfile: {http_e}")
			return
		except httpx.TimeoutException:
			print(f"ERROR: A timeout occurred while downloading '{version_result.version_type.name}' hashfile.")
			return
		except Exception as e:
			print(f"ERROR: An unexpected error occured while downloading '{version_result.version_type.name}' hashfile.")
			traceback.print_exception(type(e), e, e.__traceback__)
			return

	async def download_asset(self, filehash: str, save_destination: Path, expected_file_size: int) -> bool:
		"""
		Downloads the requested file using the session and saves it to 'save_destination' on disk.

		Returns `True` if the operation was successful, otherwise `False`.
		"""
		url = f"resource/{filehash}"
		try:
			async with self.stream("GET", url) as response:
				response.raise_for_status()

				response_size_str = response.headers.get("content-length")
				if response_size_str is None:
					print(f"WARNING: 'Content-Length' header missing for asset '{filehash}'.")
				else:
					response_size = int(response_size_str)
					if expected_file_size != response_size:
						print(f"ERROR: Received asset '{filehash}' with target '{save_destination}' has wrong size ({response_size}/{expected_file_size}).")
						return False

				save_destination.parent.mkdir(parents=True, exist_ok=True)
				async with aiofile.async_open(save_destination, "wb") as file:
					async for chunk in response.aiter_bytes(chunk_size=1024 * 64):
						await file.write(chunk)
				return True

		except httpx.HTTPError as http_e:
			print(f"ERROR: An HTTP error occurred while downloading '{filehash}' to '{save_destination}'.: {http_e}")
			return
		except httpx.TimeoutException:
			print(f"ERROR: A timeout occurred while downloading '{filehash}' to '{save_destination}'.")
			return
		except Exception as e:
			print(f"ERROR: An unexpected error occured while downloading '{filehash}' to '{save_destination}'.")
			traceback.print_exception(type(e), e, e.__traceback__)
			return False
