import json
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from pathlib import Path

from .classes import (
	DiffLog,
	DownloadType,
	HashRow,
	SimpleVersionResult,
	UnknownVersionTypeError,
	UpdateResult,
	VersionResult,
	VersionType,
)


def parse_version_string(rawstring: str) -> VersionResult:
	"""
	Parse a raw ``$``-delimited version string from the game server into a ``VersionResult``.

	Args:
		rawstring: The raw version string, e.g. ``"$AZL$1$2$3$abc123"`` or ``$MANGA$11$abc123``.

	Returns:
		``VersionResult``

	Raises:
		UnknownVersionTypeError: If the version name prefix is not a known ``VersionType``.
	"""
	parts = rawstring.split("$")[1:]
	versionname = parts[0]
	versiontype = VersionType.from_hashname(versionname)
	if not versiontype:
		raise UnknownVersionTypeError(version_name=versionname)

	if versiontype == VersionType.AZL:
		version = ".".join(parts[1:-1])
		return VersionResult(version=version, vhash=parts[-1], rawstring=rawstring, version_type=versiontype)
	return VersionResult(version=parts[1], vhash=parts[2], rawstring=rawstring, version_type=versiontype)


def compare_version_string(version_new: str, version_old: str | None) -> bool:
	"""
	Compare two dot-separated numeric version strings. Do not have to contain dots, can be simple integers.

	Args:
		version_new: The candidate version string to test.
		version_old: The baseline version string, or ``None`` to treat any version as newer.

	Returns:
		bool: ``True`` if ``version_new`` is greater, or if ``version_old`` is ``None`` or an empty string.
	"""
	if not version_old:
		return True
	new_to_int = [int(v) for v in version_new.split(".")]
	old_to_int = [int(v) for v in version_old.split(".")]
	return new_to_int > old_to_int


def iterate_hash_lines(hashes: str) -> Generator[list[str], None, None]:
	"""
	Split a multiline CSV string into individual rows, skipping blank lines.
	Each row is expected to have the format ``path,size,md5hash``.

	Args:
		hashes: A multiline CSV string where each line has the format ``path,size,md5hash``.

	Yields:
		list[str]: A three-element list ``[path, size, md5hash]`` for each non-blank line.
	"""
	for assetinfo in hashes.splitlines():
		if assetinfo == "":
			continue
		yield assetinfo.split(",")


def parse_hash_rows(hashes: str) -> Generator[HashRow, None, None]:
	"""
	Convert a multiline CSV string into ``HashRow`` objects, skipping blank lines.
	Each row is expected to have the format ``path,size,md5hash``.

	Args:
		hashes: A multiline CSV string where each line has the format ``path,size,md5hash``.

	Yields:
		``HashRow``
	"""
	for path, size, md5hash in iterate_hash_lines(hashes):
		yield HashRow(path, int(size), md5hash)


@dataclass
class VersionController:
	client_directory: Path

	def load_version_string(self, version_type: VersionType) -> str | None:
		"""
		Load the local version string for a given version type.

		Args:
			version_type: The version type to load the version string for.

		Returns:
			str | None: The local version string, or ``None`` if no version file exists.
		"""
		fpath = Path(self.client_directory, version_type.version_filename)
		if fpath.exists():
			with fpath.open("r", encoding="utf8") as f:
				return f.read()

	def load_version(self, version_type: VersionType) -> SimpleVersionResult | None:
		"""
		Load the local version string for a given version type and creates a ``SimpleVersionResult``.

		Args:
			version_type: The version type to load the version for.

		Returns:
			SimpleVersionResult | None: The local version, or ``None`` if no version file exists.
		"""
		if version_string := self.load_version_string(version_type):
			return SimpleVersionResult(version=version_string, version_type=version_type)

	def save_version_string(self, version_type: VersionType, version_string: str):
		"""
		Save the version string for a given version type.

		Args:
			version_type: The version type to save the version string for.
			content: The raw version string to save.
		"""
		fpath = Path(self.client_directory, version_type.version_filename)
		with fpath.open("w", encoding="utf8") as f:
			f.write(version_string)

	def load_hash_file(self, version_type: VersionType) -> Generator[HashRow, None, None] | None:
		"""
		Load the local asset information file for a given version type.

		Args:
			version_type: The version type to load asset info for.

		Yields:
			HashRow | None: A generator yielding ``HashRow`` objects, or ``None`` if no hash file exists.
		"""
		fpath = Path(self.client_directory, version_type.hashes_filename)
		if fpath.exists():
			with open(fpath, "r", encoding="utf8") as f:
				return parse_hash_rows(f.read())

	def save_hash_file(self, version_type: VersionType, hashrows: Iterable[HashRow | None]):
		"""
		Save asset information in CSV format for a given version type.
		Writes each ``HashRow`` as a CSV line ``path,size,md5hash``.

		Args:
			version_type: The version type to save hashes for.
			hashrows: An iterable of `HashRow` objects to write.
		"""
		rowstrings = [f"{row.filepath},{row.size},{row.md5hash}" for row in hashrows if row]
		content = "\n".join(rowstrings)
		fpath = Path(self.client_directory, version_type.hashes_filename)
		with fpath.open("w", encoding="utf8") as f:
			f.write(content)

	def update_version_data(self, version: SimpleVersionResult, hashrows: Iterable[HashRow]):
		"""
		Save both the version string and hash file for ``version`` in one call.
		Shorthand method that calls ``save_version_string`` and ``save_hash_file``.
		"""
		self.save_version_string(version.version_type, version.version)
		self.save_hash_file(version.version_type, hashrows)

	def load_difflog(self, version: SimpleVersionResult) -> DiffLog | None:
		"""
		Load and deserialize a saved difflog from JSON for ``version``, or return ``None`` if not found.

		Args:
			version: A `SimpleVersionResult` specifying the version to load.

		Returns:
			DiffLog | None: The loaded `DiffLog` object, or `None` if no log exists for this version.
		"""
		version_diffdir = Path(self.client_directory, "difflog", version.version_type.name.lower())
		difflog_filepath = Path(version_diffdir, version.version + ".json")
		try:
			with difflog_filepath.open("r", encoding="utf8") as f:
				data = json.load(f)
				return DiffLog.from_json(data, version.version_type, self.client_directory)
		except FileNotFoundError:
			return

	def save_difflog(self, difflog: DiffLog):
		"""Serialize a ``difflog`` to JSON and write it under the version type's difflog directory.

		Args:
			difflog: A `DiffLog` object to serialize and save.
		"""
		version_diffdir = Path(self.client_directory, "difflog", difflog.version.version_type.name.lower())
		version_diffdir.mkdir(parents=True, exist_ok=True)
		difflog_filepath = Path(version_diffdir, difflog.version.version + ".json")
		with difflog_filepath.open("w", encoding="utf8") as f:
			json.dump(difflog.to_json(), f)

	def update_difflog(
		self,
		version: SimpleVersionResult,
		update_results: list[UpdateResult],
		linked_versions: list[SimpleVersionResult] | None = None,
	):
		"""
		Save a difflog recording which assets changed in this version.
		Skips unchanged assets and returns early if nothing changed.

		Args:
			version: The version being recorded.
			update_results: Per-asset outcomes from the download; unchanged assets are filtered out.
			linked_versions: Versions of other types that were updated at the same time.
		"""
		filtered_update_results = list(filter(lambda r: r.download_type != DownloadType.NoChange, update_results))
		if not filtered_update_results:
			return

		if version.version_type != VersionType.AZL and linked_versions:
			print(f"WARNING: Version linking with version types other than '{VersionType.AZL.name}' is currently not supported.")
			return

		# filter and format data for difflog class
		success_files = {
			res.path: res.compare_result.compare_type
			for res in filter(lambda r: r.download_type in [DownloadType.Success, DownloadType.Removed], filtered_update_results)
		}
		failed_files = {
			res.path: res.compare_result.compare_type
			for res in filter(lambda r: r.download_type == DownloadType.Failed, filtered_update_results)
		}
		difflog = DiffLog(version=version, major=False, success_files=success_files, failed_files=failed_files)
		for linkedv in linked_versions or []:
			difflog.add_linked_version(linkedv)

		# save data to file
		self.save_difflog(difflog)

	def update_version_diffdata(
		self,
		version: SimpleVersionResult,
		hashrows: Iterable[HashRow],
		update_results: list[UpdateResult],
		linked_versions: list[SimpleVersionResult] | None = None,
	):
		"""
		Save the version string, hash file and difflog for ``version`` in one call.
		Shorthand method that calls ``update_version_data`` and ``update_difflog``.
		"""
		self.update_version_data(version=version, hashrows=hashrows)
		self.update_difflog(version=version, update_results=update_results, linked_versions=linked_versions)

	def set_as_linked(self, subversion: SimpleVersionResult, mainversion: SimpleVersionResult):
		"""
		Register the version of another version type with the main version by adding it to the main difflog.

		If the main version's difflog exists, the subversion is added as a linked version and the
		difflog is saved. Otherwise a warning is printed.

		Args:
			subversion: The subversion to register.
			mainversion: The main version whose difflog is updated.
		"""
		if main_difflog := self.load_difflog(mainversion):
			main_difflog.add_linked_version(subversion)
			self.save_difflog(main_difflog)
		else:
			print(
				f"WARN: Tried to link subversion '{subversion}' to  mainversion '{mainversion}' but mainversion has no difflog!"
			)

	def get_difflog_versionlist(self, version_type: VersionType) -> list[str]:
		"""
		Return version strings of all saved difflogs.

		Args:
			client_directory: Root client directory
			version_type: Version type to scan for

		Returns:
			list[str]: Version strings derived from difflog filenames
		"""
		version_diffdir = Path(self.client_directory, "difflog", version_type.name.lower())
		difflog_versionlist = [path.stem for path in version_diffdir.glob("*.json")]
		return difflog_versionlist
