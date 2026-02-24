import json
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable

from .classes import DownloadType, HashRow, UpdateResult, VersionType, VersionResult, SimpleVersionResult, DiffLog


def parse_version_string(rawstring: str) -> VersionResult:
	"""
	Tries to parse the raw version string as returned by the game server into a `VersionResult`.

	Raises `NotImplementedError` if the versiontype does not exist.
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
	Path to clientassets directory of a specific client
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
		latest_versionfile = Path(version_diffdir, "latest")
		if latest_versionfile.exists():
			with open(latest_versionfile, "r", encoding="utf8") as f:
				return f.read()

	def save_latest_versionstring(self, version: SimpleVersionResult):
		version_diffdir = Path(self.client_directory, "difflog", version.version_type.name.lower())
		version_diffdir.mkdir(parents=True, exist_ok=True)
		latest_filepath = Path(version_diffdir, "latest")
		with open(latest_filepath, "w", encoding="utf8") as f:
			f.write(version.version)

	def _save_raw_difflog(self, difflog: DiffLog):
		version_diffdir = Path(self.client_directory, "difflog", difflog.version.version_type.name.lower())
		version_diffdir.mkdir(parents=True, exist_ok=True)
		difflog_filepath = Path(version_diffdir, difflog.version.version+".json")
		with open(difflog_filepath, "w", encoding="utf8") as f:
			json.dump(difflog.to_json(), f)

	def save_difflog(self, version: SimpleVersionResult, update_results: list[UpdateResult], linked_versions: list[SimpleVersionResult] = None):
		filtered_update_results = list(filter(lambda r: r.download_type != DownloadType.NoChange, update_results))
		if not filtered_update_results:
			return

		if version.version_type != VersionType.AZL and linked_versions:
			print(f"WARNING: Version linking with version types other than '{VersionType.AZL.name}' is currently not supported.")
			return

		# filter and format data for difflog class
		success_files = {res.path: res.compare_result.compare_type for res in filter(lambda r: r.download_type in [DownloadType.Success, DownloadType.Removed], filtered_update_results)}
		failed_files = {res.path: res.compare_result.compare_type for res in filter(lambda r: r.download_type == DownloadType.Failed, filtered_update_results)}
		difflog = DiffLog(version=version, major=False, success_files=success_files, failed_files=failed_files)
		for linkedv in (linked_versions or []):
			difflog.add_linked_version(linkedv)

		# save data to file
		self._save_raw_difflog(difflog)

		# update 'latest version' file if this version is newer than the currently latest one
		latest_version = self.get_latest_versionstring(version.version_type)
		if compare_version_string(version_new=version.version, version_old=latest_version):
			self.save_latest_versionstring(version)

	def load_difflog(self, version: SimpleVersionResult) -> DiffLog | None:
		version_diffdir = Path(self.client_directory, "difflog", version.version_type.name.lower())
		difflog_filepath = Path(version_diffdir, version.version+".json")
		try:
			with open(difflog_filepath, "r", encoding="utf8") as f:
				data = json.load(f)
				return DiffLog.from_json(data, version.version_type, self.client_directory)
		except FileNotFoundError:
			return

	def set_as_linked(self, subversion: SimpleVersionResult, mainversion: SimpleVersionResult):
		main_difflog = self.load_difflog(mainversion)
		main_difflog.add_linked_version(subversion)
		self._save_raw_difflog(main_difflog)
