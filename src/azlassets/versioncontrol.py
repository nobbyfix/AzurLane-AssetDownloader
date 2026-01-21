import json
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable

from .classes import DownloadType, HashRow, UpdateResult, VersionType, VersionResult, SimpleVersionResult


def parse_version_string(rawstring: str) -> VersionResult:
	"""
	Tries to parse the raw version string as returned by the game server into a VersionResult.

	Raises NotImplementedError if the versiontype does not exist.
	"""
	parts = rawstring.split('$')[1:]
	versionname = parts[0]
	versiontype = VersionType.from_hashname(versionname)
	if not versiontype:
		raise NotImplementedError(f'Unknown versionname {versionname}.')

	if versiontype == VersionType.AZL:
		version = '.'.join(parts[1:-1])
		return VersionResult(version=version, vhash=parts[-1], rawstring=rawstring, version_type=versiontype)
	return VersionResult(version=parts[1], vhash=parts[2], rawstring=rawstring, version_type=versiontype)

def compare_version_string(version_new: str, version_old: str | None) -> bool:
	"""
	Returns `True` if `version_new` is newer than `version_old`.
	"""
	if not version_old:
		return True
	new_to_int = [int(v) for v in version_new.split(".")]
	old_to_int = [int(v) for v in version_old.split(".")]
	return new_to_int > old_to_int

def iterate_hash_lines(hashes: str) -> Generator[list[str], None, None]:
	for assetinfo in hashes.splitlines():
		if assetinfo == '': continue
		yield assetinfo.split(',')

def parse_hash_rows(hashes: str) -> Generator[HashRow, None, None]:
	for path, size, md5hash in iterate_hash_lines(hashes):
		yield HashRow(path, int(size), md5hash)


@dataclass
class VersionController:
	client_directory: Path
	"""
	Path to clientassets directory of specific client
	"""

	def load_version_string(self, version_type: VersionType) -> str | None:
		fpath = Path(self.client_directory, version_type.version_filename)
		if fpath.exists():
			with open(fpath, 'r', encoding='utf8') as f:
				return f.read()

	def save_version_string(self, version_type: VersionType, content: str):
		with open(Path(self.client_directory, version_type.version_filename), 'w', encoding='utf8') as f:
			f.write(content)

	def load_hash_file(self, version_type: VersionType) -> Generator[HashRow, None, None] | None:
		fpath = Path(self.client_directory, version_type.hashes_filename)
		if fpath.exists():
			with open(fpath, 'r', encoding='utf8') as f:
				return parse_hash_rows(f.read())

	def save_hash_file(self, version_type: VersionType, hashrows: Iterable[HashRow]):
		rowstrings = [f"{row.filepath},{row.size},{row.md5hash}" for row in hashrows if row]
		content = '\n'.join(rowstrings)
		with open(Path(self.client_directory, version_type.hashes_filename), 'w', encoding="utf8") as f:
			f.write(content)

	def update_version_data(self, version: SimpleVersionResult, hashrows: Iterable[HashRow]):
		self.save_version_string(version.version_type, version.version)
		self.save_hash_file(version.version_type, hashrows)

	def get_latest_versionstring(self, version_type: VersionType) -> str | None:
		version_diffdir = Path(self.client_directory, "difflog", version_type.name.lower())

		legacy_rename_latest_difflog(version_diffdir)

		latest_versionfile = Path(version_diffdir, "latest")
		if latest_versionfile.exists():
			with open(latest_versionfile, "r", encoding="utf8") as f:
				return f.read()

	def save_difflog(self, version: SimpleVersionResult, update_results: list[UpdateResult]):
		filtered_update_results = list(filter(lambda r: r.download_type != DownloadType.NoChange, update_results))
		if not filtered_update_results:
			return

		version_diffdir = Path(self.client_directory, "difflog", version.version_type.name.lower())
		version_diffdir.mkdir(parents=True, exist_ok=True)
		legacy_rename_latest_difflog(version_diffdir)

		version_string = version.version
		data = {
			"version": version_string,
			"major": False,
			"success_files": {res.path.inner: res.compare_result.compare_type.name for res in filter(lambda r: r.download_type in [DownloadType.Success, DownloadType.Removed], filtered_update_results)},
			"failed_files": {res.path.inner: res.compare_result.compare_type.name for res in filter(lambda r: r.download_type == DownloadType.Failed, filtered_update_results)},
		}

		difflog_filepath = Path(version_diffdir, version_string+".json")
		with open(difflog_filepath, "w", encoding="utf8") as f:
			json.dump(data, f)

		latest_filepath = Path(version_diffdir, "latest")
		with open(latest_filepath, "w", encoding="utf8") as f:
			f.write(version_string)

def legacy_rename_latest_difflog(version_diffdir: Path):
	"""
	Rename the `latest.json` difflog file for users that used the tool while that file was being created.
	"""
	latest_difflog = Path(version_diffdir, "latest.json")
	if latest_difflog.exists():
		with open(latest_difflog, "r", encoding="utf8") as f:
			latest_data = json.load(f)
		latest_version = latest_data["version"]
		latest_difflog.rename(latest_difflog.with_stem(latest_version))

		latest_filepath = Path(version_diffdir, "latest")
		with open(latest_filepath, "w", encoding="utf8") as f:
			f.write(latest_version)
