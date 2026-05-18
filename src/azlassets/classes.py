from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Self


class UnknownVersionTypeError(NotImplementedError):
	"""Raised when a version hashname cannot be mapped to a known :class:`VersionType`."""

	def __init__(self, version_name, *args):
		super().__init__(f"Unknown versionname {version_name}.", *args)
		self.version_name = version_name


CompareType = Enum("CompareType", "New Changed Unchanged Deleted")
DownloadType = Enum("DownloadType", "NoChange Removed Success Failed ForDeletionNoChange")


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


@dataclass
class ClientDataMixin:
	"""
	Data fields shared by all :class:`Client` enum members.

	Used as a mixin so that each ``Client`` member carries typed metadata
	alongside its enum value.
	"""

	locale_code: str
	package_name: str
	"""Package name on the Google Play Store."""
	active: bool = field(repr=False, default=True)
	"""Whether the Client is receiving updates."""


class Client(ClientDataMixin, Enum):
	"""
	Enumeration of supported Azur Lane game clients.
	"""

	__package_name_map__: dict[str, Self] = {}

	EN = "en-US", "com.YoStarEN.AzurLane"
	JP = "ja-JP", "com.YoStarJP.AzurLane"
	CN = "zh-CN", ""
	KR = "ko-KR", "kr.txwy.and.blhx"
	TW = "zh-TW", "com.hkmanjuu.azurlane.gp"

	@classmethod
	def from_package_name(cls, package_name: str) -> Self | None:
		"""
		Get a Client member with matching package name.

		Args:
			package_name: The package name to match

		Returns:
			Client or None: The matching Client member or None if no match
		"""
		if not cls.__package_name_map__:
			cls.__package_name_map__ = {member.package_name: member for member in cls}
		return cls.__package_name_map__.get(package_name)


@dataclass(eq=True, frozen=True)
class HashRow:
	"""
	A single row from a client hashes CSV file.

	Represents one asset entry as stored in ``hashes*.csv``. Instances are immutable and hashable.
	"""

	filepath: str
	size: int
	md5hash: str


@dataclass(eq=True)
class CompareResult:
	"""
	The outcome of comparing an asset bundle between two snapshots.
	"""

	current_hash: HashRow | None
	new_hash: HashRow | None
	compare_type: CompareType


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


@dataclass(eq=True)
class BundlePath:
	"""
	A resolved asset bundle path, storing both a resolvable path and
	the normalised inner path relative to the client AssetBundles directory.

	The inner path uses forward slashes regardless of the host OS.
	"""

	full: Path
	inner: str

	@staticmethod
	def construct(parentdir: Path, inner: Path | str) -> "BundlePath":
		"""
		Construct a BundlePath from parent directory and inner path.

		Args:
			parentdir: The parent directory
			inner: The inner path

		Returns:
			BundlePath: The constructed BundlePath object
		"""
		fullpath = Path(parentdir, inner)
		return BundlePath(fullpath, str(inner).replace("\\", "/"))

	def __hash__(self):
		return hash(self.inner)


@dataclass
class UpdateResult:
	"""
	The combined outcome of comparing and downloading a single asset bundle.
	"""

	compare_result: CompareResult
	download_type: DownloadType
	path: BundlePath


@dataclass
class UserConfig:
	"""
	User-supplied configuration controlling download and extraction behaviour.
	"""

	useragent: str
	download_isblacklist: bool
	download_filter: list
	extract_isblacklist: bool
	extract_filter: list
	asset_directory: Path
	extract_directory: Path


@dataclass
class ClientConfig:
	"""
	Server connection parameters for a game client.
	"""

	gateip: str
	gateport: int
	cdnurl: str


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


__all__ = [
	"CompareType",
	"DownloadType",
	"VersionType",
	"Client",
	"HashRow",
	"CompareResult",
	"SimpleVersionResult",
	"VersionResult",
	"BundlePath",
	"UpdateResult",
	"UserConfig",
	"ClientConfig",
	"DiffLog",
]
