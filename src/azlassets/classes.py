from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Self

CompareType = Enum("CompareType", "New Changed Unchanged Deleted")
DownloadType = Enum("DownloadType", "NoChange Removed Success Failed ForDeletionNoChange")


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
