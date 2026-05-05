from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Self


class UnknownVersionTypeError(NotImplementedError):
	def __init__(self, version_name, *args):
		super().__init__(f"Unknown versionname {version_name}.", *args)
		self.version_name = version_name


CompareType = Enum("CompareType", "New Changed Unchanged Deleted")
DownloadType = Enum("DownloadType", "NoChange Removed Success Failed ForDeletionNoChange")


@dataclass
class VersionTypeDataMixin:
	hashname: str
	"""Hash name used on the version result returned by the game server."""
	suffix: str
	"""Suffix used on version and hash files."""


class VersionType(VersionTypeDataMixin, Enum):
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

	@property
	def version_filename(self) -> str:
		"""
		Full version filename using the suffix.
		"""
		suffix = self.suffix
		if suffix:
			suffix = "-" + suffix
		return f"version{suffix}.txt"

	@property
	def hashes_filename(self) -> str:
		"""
		Full hashes filename using the suffix.
		"""
		suffix = self.suffix
		if suffix:
			suffix = "-" + suffix
		return f"hashes{suffix}.csv"

	@classmethod
	def from_hashname(cls, hashname: str) -> Self | None:
		"""
		Returns a VersionType member with matching *hashname* if match exists, otherwise None.
		"""
		if not cls.__hash2member_map__:
			cls.__hash2member_map__ = {member.hashname: member for member in cls}
		return cls.__hash2member_map__.get(hashname)


@dataclass
class AbstractClientDataMixin:
	locale_code: str
	package_name: str
	active: bool = field(repr=False, default=True)


class AbstractClient(AbstractClientDataMixin, Enum):
	__package_name_map__: dict[str, Self] = {}

	@classmethod
	def from_package_name(cls, package_name: str) -> Self | None:
		"""
		Returns a Client member with matching *package_name* if match exists, otherwise None.
		"""
		if not cls.__package_name_map__:
			cls.__package_name_map__ = {member.package_name: member for member in cls}
		return cls.__package_name_map__.get(package_name)


class Client(AbstractClient):
	EN = "en-US", "com.YoStarEN.AzurLane"
	JP = "ja-JP", "com.YoStarJP.AzurLane"
	CN = "zh-CN", ""
	KR = "ko-KR", "kr.txwy.and.blhx"
	TW = "zh-TW", "com.hkmanjuu.azurlane.gp"


@dataclass
class HashRow:
	filepath: str
	size: int
	md5hash: str


@dataclass
class CompareResult:
	current_hash: HashRow | None
	new_hash: HashRow | None
	compare_type: CompareType


@dataclass
class SimpleVersionResult:
	version: str
	version_type: VersionType


@dataclass
class VersionResult(SimpleVersionResult):
	vhash: str
	rawstring: str


@dataclass
class BundlePath:
	full: Path
	inner: str

	@staticmethod
	def construct(parentdir: Path, inner: Path | str) -> "BundlePath":
		fullpath = Path(parentdir, inner)
		return BundlePath(fullpath, str(inner))

	def __hash__(self):
		return hash(self.inner)


@dataclass
class UpdateResult:
	compare_result: CompareResult
	download_type: DownloadType
	path: BundlePath


@dataclass
class UserConfig:
	useragent: str
	download_isblacklist: bool
	download_filter: list
	extract_isblacklist: bool
	extract_filter: list
	asset_directory: Path
	extract_directory: Path


@dataclass
class ClientConfig:
	gateip: str
	gateport: int
	cdnurl: str


@dataclass
class DiffLog:
	version: SimpleVersionResult
	major: bool = False
	linked_versions: dict[VersionType, list[str]] = field(default_factory=dict)
	success_files: dict[BundlePath, CompareType] = field(default_factory=dict)
	failed_files: dict[BundlePath, CompareType] = field(default_factory=dict)

	def add_linked_version(self, version: SimpleVersionResult):
		if version.version_type not in self.linked_versions:
			self.linked_versions[version.version_type] = []
		if version.version not in self.linked_versions[version.version_type]:
			self.linked_versions[version.version_type].append(version.version)

	def to_json(self) -> dict:
		data = {
			"version": self.version.version,
			"major": self.major,
			"linked_versions": {vt.name: versions for vt, versions in self.linked_versions.items()},
			"success_files": {path.inner: ctype.name for path, ctype in self.success_files.items()},
			"failed_files": {path.inner: ctype.name for path, ctype in self.failed_files.items()},
		}
		return data

	@staticmethod
	def from_json(diffdata: dict, vtype: VersionType, client_directory: Path):
		version = SimpleVersionResult(version=diffdata["version"], version_type=vtype)
		major = diffdata.get("major", False)
		linked_versions = {VersionType[vt_str]: versions for vt_str, versions in diffdata.get("linked_versions", {}).items()}
		assetbasepath = Path(client_directory, "AssetBundles")
		success_files = {
			BundlePath.construct(assetbasepath, path_str): CompareType[ctype]
			for path_str, ctype in diffdata.get("success_files", {}).items()
		}
		failed_files = {
			BundlePath.construct(assetbasepath, path_str): CompareType[ctype]
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
