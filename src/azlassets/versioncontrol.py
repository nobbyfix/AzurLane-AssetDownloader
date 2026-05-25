import json
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Self

from .classes import (
	BundlePath,
	CompareType,
	DownloadType,
	HashRow,
	UpdateResult,
)


class UnknownVersionTypeError(NotImplementedError):
	"""Raised when a version hashname cannot be mapped to a known :class:`VersionType`."""

	def __init__(self, version_name, *args):
		super().__init__(f"Unknown versionname {version_name}.", *args)
		self.version_name = version_name


@dataclass
class VersionTypeDataMixin:
	"""
	Data fields shared by all :class:`VersionType` enum members.

	Used as a mixin so that each ``VersionType`` member carries typed metadata
	alongside its enum value.
	"""

	hashname: str
	"""Hash name used on the version result returned by the game server."""
	suffix: str
	"""Suffix used on version and hash files."""


class VersionType(VersionTypeDataMixin, Enum):
	"""
	Enumeration of all supported asset version types.
	"""

	__hash2member_map__: dict[str, Self] = {}

	AZL = "azhash", ""
	CV = "cvhash", "cv"
	L2D = "l2dhash", "live2d"
	PIC = "pichash", "pic"
	BGM = "bgmhash", "bgm"
	CIPHER = "cipherhash", "cipher"
	MANGA = "mangahash", "manga"
	PAINTING = "paintinghash", "painting"
	DORM = "dormhash", "dorm"
	MAP = "maphash", "map"

	def __str__(self) -> str:
		return self.name.lower()

	def __hash__(self) -> int:
		return Enum.__hash__(self)

	@property
	def version_filename(self) -> str:
		"""
		Get the full version filename for this type.

		For types without a suffix (e.g. ``AZL``), returns ``version.txt``.
		For types with a suffix (e.g. ``CV``), returns ``version-{suffix}.txt``
		(e.g. ``version-cv.txt``).

		Returns:
			str: The formatted version filename
		"""
		suffix = self.suffix
		if suffix:
			suffix = "-" + suffix
		return f"version{suffix}.txt"

	@property
	def hashes_filename(self) -> str:
		"""
		Get the full hashes filename for this type.

		For types without a suffix (e.g. ``AZL``), returns ``hashes.csv``.
		For types with a suffix (e.g. ``CV``), returns ``hashes-{suffix}.csv``
		(e.g. ``hashes-cv.csv``).

		Returns:
			str: The formatted hashes filename
		"""
		suffix = self.suffix
		if suffix:
			suffix = "-" + suffix
		return f"hashes{suffix}.csv"

	@classmethod
	def from_hashname(cls, hashname: str) -> Self | None:
		"""
		Get a VersionType member with matching hashname.

		Args:
			hashname: The hashname to match

		Returns:
			VersionType or None: The matching VersionType member or None if no match
		"""
		if not cls.__hash2member_map__:
			cls.__hash2member_map__ = {member.hashname: member for member in cls}
		return cls.__hash2member_map__.get(hashname)


@dataclass(eq=True, frozen=True)
class SimpleVersionResult:
	"""
	A minimal version descriptor pairing a version string with its type.

	Used wherever a full :class:`VersionResult` (which includes hash and raw
	server response) is unnecessary or unavailable. Instances are immutable and hashable.
	"""

	version: str
	version_type: VersionType

	def __str__(self):
		return f"{self.version_type.name} {self.version}"


@dataclass(eq=True, frozen=True)
class VersionResult(SimpleVersionResult):
	"""
	A full version descriptor as returned by the game server.

	Extends :class:`SimpleVersionResult` with the raw server response and the
	associated hash of the ``hashes*.csv`` file, enabling download the file from the server.
	"""

	vhash: str
	rawstring: str


@dataclass
class DiffLog:
	"""
	A record of which asset bundles changed between two versions of a client.
	"""

	version: SimpleVersionResult
	major: bool = False
	linked_versions: dict[VersionType, list[str]] = field(default_factory=dict)
	success_files: dict[BundlePath, CompareType] = field(default_factory=dict)
	failed_files: dict[BundlePath, CompareType] = field(default_factory=dict)

	def add_linked_version(self, version: SimpleVersionResult):
		"""
		Add a version as linked to this difflog.

		Args:
			version: The version to add as linked
		"""
		if version.version_type not in self.linked_versions:
			self.linked_versions[version.version_type] = []
		if version.version not in self.linked_versions[version.version_type]:
			self.linked_versions[version.version_type].append(version.version)

	def get_success_files(self, filter: Callable[[CompareType], bool] = (lambda *args, **kwargs: True)) -> list[BundlePath]:
		"""
		Return successfully processed bundle paths, optionally filtered by compare type.

		Args:
			filter: A predicate that receives a :class:`CompareType` and returns ``True``
				for entries that should be included. Defaults to including all entries.

		Returns:
			list[BundlePath]: Bundle paths from ``success_files`` whose compare type
			satisfies the predicate.
		"""
		return [bpath for bpath, ctype in self.success_files.items() if filter(ctype)]

	def get_failed_files(self, filter: Callable[[CompareType], bool] = (lambda *args, **kwargs: True)) -> list[BundlePath]:
		"""
		Return failed bundle paths, optionally filtered by compare type.

		Args:
			filter: A predicate that receives a :class:`CompareType` and returns ``True``
				for entries that should be included. Defaults to including all entries.

		Returns:
			list[BundlePath]: Bundle paths from ``failed_files`` whose compare type
			satisfies the predicate.
		"""
		return [bpath for bpath, ctype in self.failed_files.items() if filter(ctype)]

	def to_json(self) -> dict[str, Any]:
		"""
		Convert this DiffLog to a JSON-serialisable dict.

		The returned structure is::

			{
				"version":		 str,
				"major":		   bool,
				"linked_versions": {VersionType.name: [version_str, ...]},
				"success_files":   {inner_path: CompareType.name, ...},
				"failed_files":	{inner_path: CompareType.name, ...},
			}

		Returns:
			dict: The DiffLog data in JSON-serialisable format
		"""
		data = {
			"version": self.version.version,
			"major": self.major,
			"linked_versions": {vt.name: versions for vt, versions in self.linked_versions.items()},
			"success_files": {path.inner: ctype.name for path, ctype in self.success_files.items()},
			"failed_files": {path.inner: ctype.name for path, ctype in self.failed_files.items()},
		}
		return data

	@staticmethod
	def from_json(diffdata: dict[str, Any], vtype: VersionType, client_asset_directory: Path):
		"""
		Construct a DiffLog object from JSON data.

		Args:
			diffdata: Dict produced by :meth:``to_json``
			vtype: The VersionType that owns this log
			client_asset_directory: Root client directory

		Returns:
			DiffLog: The constructed DiffLog object
		"""
		version = SimpleVersionResult(version=diffdata["version"], version_type=vtype)
		major = diffdata.get("major", False)
		linked_versions = {VersionType[vt_str]: versions for vt_str, versions in diffdata.get("linked_versions", {}).items()}
		client_assetbundle_directory = Path(client_asset_directory, "AssetBundles")
		success_files = {
			BundlePath.construct(client_assetbundle_directory, path_str): CompareType[ctype]
			for path_str, ctype in diffdata.get("success_files", {}).items()
		}
		failed_files = {
			BundlePath.construct(client_assetbundle_directory, path_str): CompareType[ctype]
			for path_str, ctype in diffdata.get("failed_files", {}).items()
		}

		return DiffLog(
			version=version,
			major=major,
			linked_versions=linked_versions,
			success_files=success_files,
			failed_files=failed_files,
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
	"""
	Manages reading and writing of versioning data for a single game client.
	"""

	client_directory: Path

	def get_version_string_path(self, version_type: VersionType) -> Path:
		"""
		Return the filesystem path for the version string file of ``version_type``.

		Args:
			version_type: The version type whose version file path is needed.

		Returns:
			Path: Path to the ``version*.txt`` file.
		"""
		return Path(self.client_directory, version_type.version_filename)

	def load_version_string(self, version_type: VersionType) -> str | None:
		"""
		Load the local version string for a given version type.

		Args:
			version_type: The version type to load the version string for.

		Returns:
			str | None: The local version string, or ``None`` if no version file exists.
		"""
		fpath = self.get_version_string_path(version_type)
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

	def save_version(self, version: SimpleVersionResult):
		"""
		Save the version string for a given version type.

		Args:
			version: The version result whose ``version`` string should be saved.
		"""
		fpath = self.get_version_string_path(version.version_type)
		fpath.parent.mkdir(parents=True, exist_ok=True)
		with fpath.open("w", encoding="utf8") as f:
			f.write(version.version)

	def get_hash_file_path(self, version_type: VersionType) -> Path:
		"""
		Return the filesystem path for the hashes CSV file of ``version_type``.

		Args:
			version_type: The version type whose hash file path is needed.

		Returns:
			Path: Path to the ``hashes*.csv`` file.
		"""
		return Path(self.client_directory, version_type.hashes_filename)

	def load_hash_file(self, version_type: VersionType) -> Generator[HashRow, None, None] | None:
		"""
		Load the local asset hash CSV file for a given version type.

		Args:
			version_type: The version type to load asset info for.

		Yields:
			HashRow | None: A generator yielding :class:`HashRow` objects objects parsed from the CSV,
			or ``None`` if the hash file does not exist.
		"""
		fpath = self.get_hash_file_path(version_type)
		try:
			with open(fpath, "r", encoding="utf8") as f:
				return parse_hash_rows(f.read())
		except FileNotFoundError:
			return

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
		fpath = self.get_hash_file_path(version_type)
		fpath.parent.mkdir(parents=True, exist_ok=True)
		with fpath.open("w", encoding="utf8") as f:
			f.write(content)

	def update_version_data(self, version: SimpleVersionResult, hashrows: Iterable[HashRow]):
		"""
		Save both the version string and hash file for ``version`` in one call.
		Shorthand method that calls ``save_version`` and ``save_hash_file``.
		"""
		self.save_version(version)
		self.save_hash_file(version.version_type, hashrows)

	def get_difflog_dirpath(self, version_type: VersionType) -> Path:
		"""
		Return the directory path where difflogs for ``version_type`` are stored.

		Args:
			version_type: The version type whose difflog directory is needed.

		Returns:
			Path: Path to the directory.
		"""
		return Path(self.client_directory, "difflog", version_type.name.lower())

	def get_latest_difflog_version_path(self, version_type: VersionType) -> Path:
		"""
		Return the path to the ``latest.txt`` file that records the most recent difflog version.

		Args:
			version_type: The version type whose latest-version pointer is needed.

		Returns:
			Path: Path to ``latest.txt`` in the difflog directory for ``version_type``.
		"""
		version_diffdir = self.get_difflog_dirpath(version_type)
		latest_version_filepath = Path(version_diffdir, "latest.txt")
		return latest_version_filepath

	def load_latest_difflog_version(self, version_type: VersionType) -> SimpleVersionResult:
		"""
		Read the latest-version pointer from file and return the corresponding version descriptor.

		Args:
			version_type: The version type to look up.

		Returns:
			SimpleVersionResult: The version recorded as the latest difflog for ``version_type``.

		Raises:
			FileNotFoundError: If the file does not exist for this version type.
		"""
		latest_version_filepath = self.get_latest_difflog_version_path(version_type)
		with latest_version_filepath.open("r", encoding="utf8") as f:
			vstring = f.read()
			return SimpleVersionResult(version_type=version_type, version=vstring)

	def save_latest_difflog_version(self, version: SimpleVersionResult):
		"""
		Write ``version`` as the latest difflog pointer for its version type.

		Args:
			version: The version result to record as the latest difflog version.
		"""
		latest_version_filepath = self.get_latest_difflog_version_path(version.version_type)
		latest_version_filepath.parent.mkdir(parents=True, exist_ok=True)
		with latest_version_filepath.open("w", encoding="utf8") as f:
			f.write(version.version)

	def get_difflog_path(self, version: SimpleVersionResult) -> Path:
		"""
		Return the filesystem path for the JSON difflog file of ``version``.

		Args:
			version: The version whose difflog file path is needed.

		Returns:
			Path: Path to the difflog file.
		"""
		version_diffdir = self.get_difflog_dirpath(version.version_type)
		difflog_filepath = Path(version_diffdir, version.version + ".json")
		return difflog_filepath

	def load_difflog(self, version: SimpleVersionResult) -> DiffLog | None:
		"""
		Load and deserialize a saved difflog from JSON for ``version``, or return ``None`` if not found.

		Args:
			version: A `SimpleVersionResult` specifying the version to load.

		Returns:
			DiffLog | None: The loaded `DiffLog` object, or `None` if no log exists for this version.
		"""
		difflog_filepath = self.get_difflog_path(version)
		try:
			with difflog_filepath.open("r", encoding="utf8") as f:
				data = json.load(f)
				return DiffLog.from_json(data, version.version_type, self.client_directory)
		except FileNotFoundError:
			return

	def load_difflog_latest(self, version_type: VersionType) -> DiffLog | None:
		"""
		Load the difflog for the most recently recorded version of ``version_type``.

		Resolves the latest version via :meth:`load_latest_difflog_version`, then
		delegates to :meth:`load_difflog`.

		Args:
			version_type: The version type to load the latest difflog for.

		Returns:
			DiffLog | None: The latest :class:`DiffLog`, or ``None`` if the difflog
			file is missing.

		Raises:
			FileNotFoundError: If the ``latest.txt`` pointer itself does not exist.
		"""
		latest_difflog_version = self.load_latest_difflog_version(version_type)
		latest_difflog = self.load_difflog(latest_difflog_version)
		return latest_difflog

	def save_difflog(self, difflog: DiffLog, is_latest: bool = False):
		"""Serialize a ``difflog`` to JSON and write it under the version type's difflog directory.

		Args:
			difflog: A ``DiffLog`` object to serialize and save.
			is_latest: Updates the ``latest.txt`` with the version of the difflog.
		"""
		difflog_filepath = self.get_difflog_path(difflog.version)
		difflog_filepath.parent.mkdir(parents=True, exist_ok=True)
		with difflog_filepath.open("w", encoding="utf8") as f:
			json.dump(difflog.to_json(), f)
		if is_latest:
			self.save_latest_difflog_version(difflog.version)

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
		Return version strings of all saved difflogs for ``version_type``.

		Args:
			version_type: The version type to scan for saved difflogs.

		Returns:
			list[str]: Version strings derived from difflog filenames, in
			filesystem iteration order.
		"""
		version_diffdir = self.get_difflog_dirpath(version_type)
		difflog_versionlist = [path.stem for path in version_diffdir.glob("*.json")]
		return difflog_versionlist
