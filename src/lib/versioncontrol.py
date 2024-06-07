import json
from pathlib import Path
from typing import Generator, Iterable, Optional

from .classes import DownloadType, HashRow, UpdateResult, VersionType, VersionResult


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
		return VersionResult(version, parts[-1], rawstring, versiontype)
	return VersionResult(parts[1], parts[2], rawstring, versiontype)


def load_version_string(version_type: VersionType, relative_parent_dir: Path) -> Optional[str]:
	fpath = Path(relative_parent_dir, version_type.version_filename)
	if fpath.exists():
		with open(fpath, 'r', encoding='utf8') as f:
			return f.read()

def save_version_string(version_type: VersionType, relative_parent_dir: Path, content: str):
	with open(Path(relative_parent_dir, version_type.version_filename), 'w', encoding='utf8') as f:
		f.write(content)

def save_version_string2(version_result: VersionResult, relative_parent_dir: Path):
	save_version_string(version_result.version_type, relative_parent_dir, version_result.version)


def iterate_hash_lines(hashes: str) -> Generator[tuple[str, str, str], None, None]:
	for assetinfo in hashes.splitlines():
		if assetinfo == '': continue
		yield assetinfo.split(',')

def parse_hash_rows(hashes: str) -> Generator[HashRow, None, None]:
	for path, size, md5hash in iterate_hash_lines(hashes):
		yield HashRow(path, int(size), md5hash)

def load_hash_file(version_type: VersionType, relative_parent_dir: Path) -> Optional[Generator[HashRow, None, None]]:
	fpath = Path(relative_parent_dir, version_type.hashes_filename)
	if fpath.exists():
		with open(fpath, 'r', encoding='utf8') as f:
			return parse_hash_rows(f.read())

def save_hash_file(version_type: VersionType, relative_parent_dir: Path, hashrows: Iterable[HashRow]):
	rowstrings = [f"{row.filepath},{row.size},{row.md5hash}" for row in hashrows if row]
	content = '\n'.join(rowstrings)
	with open(Path(relative_parent_dir, version_type.hashes_filename), 'w', encoding="utf8") as f:
		f.write(content)

def update_version_data(version_type: VersionType, relative_parent_dir: Path, version_string: str, hashrows: Iterable[HashRow]):
	save_version_string(version_type, relative_parent_dir, version_string)
	save_hash_file(version_type, relative_parent_dir, hashrows)

def update_version_data2(version_result: VersionResult, relative_parent_dir: Path, hashrows: Iterable[HashRow]):
	save_version_string2(version_result, relative_parent_dir)
	save_hash_file(version_result.version_type, relative_parent_dir, hashrows)


def save_difflog(version_type: VersionType, version_string: str, update_results: list[UpdateResult], relative_parent_dir: Path):
	filtered_update_results = list(filter(lambda r: r.download_type != DownloadType.NoChange, update_results))
	if not filtered_update_results:
		return

	version_diffdir = Path(relative_parent_dir, "difflog", version_type.name.lower())
	latest_difflog = Path(version_diffdir, "latest.json")
	if latest_difflog.exists():
		with open(latest_difflog, "r", encoding="utf8") as f:
			latest_data = json.load(f)
		latest_version = latest_data["version"]
		latest_difflog.rename(latest_difflog.with_stem(latest_version))
	
	version_diffdir.mkdir(parents=True, exist_ok=True)
	data = {
		"version": version_string,
		"major": False,
		"success_files": {res.path.inner: res.compare_result.compare_type.name for res in filter(lambda r: r.download_type in [DownloadType.Success, DownloadType.Removed], filtered_update_results)},
		"failed_files": {res.path.inner: res.compare_result.compare_type.name for res in filter(lambda r: r.download_type == DownloadType.Failed, filtered_update_results)},
	}

	with open(latest_difflog, "w", encoding="utf8") as f:
		json.dump(data, f)

def save_difflog2(version_result: VersionResult, update_results: list[UpdateResult], relative_parent_dir: Path):
	save_difflog(version_result.version_type, version_result.version, update_results, relative_parent_dir)