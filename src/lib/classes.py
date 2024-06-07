from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


CompareType = Enum('CompareType', 'New Changed Unchanged Deleted')
DownloadType = Enum('DownloadType', 'NoChange Removed Success Failed')

class VersionType(Enum):
	__hash2member_map__: dict[str, "VersionType"] = {}
	hashname: str
	"""Hash name used on the version result returned by the game server."""
	suffix: str
	"""Suffix used on version and hash files."""

	AZL			= (1,	"azhash",		"")
	CV			= (2,	"cvhash",		"cv")
	L2D			= (3,	"l2dhash",		"live2d")
	PIC			= (4,	"pichash",		"pic")
	BGM			= (5,	"bgmhash",		"bgm")
	CIPHER		= (6,	"cipherhash",	"cipher")
	MANGA		= (7,	"mangahash",	"manga")
	PAINTING	= (8,	"paintinghash",	"painting")
	DORM		= (9,	"dormhash",		"dorm")


	def __init__(self, _, hashname, suffix) -> None:
		# add attributes to enum objects
		self.hashname = hashname
		self.suffix = suffix
		# add enum objects to member maps
		self.__hash2member_map__[hashname] = self

	def __str__(self) -> str:
		return self.label

	@property
	def version_filename(self) -> str:
		"""
		Full version filename using the suffix.
		"""
		suffix = self.suffix
		if suffix: suffix = "-"+suffix
		return f"version{suffix}.txt"

	@property
	def hashes_filename(self) -> str:
		"""
		Full hashes filename using the suffix.
		"""
		suffix = self.suffix
		if suffix: suffix = "-"+suffix
		return f"hashes{suffix}.csv"


	@classmethod
	def from_hashname(cls, hashname: str) -> Optional["VersionType"]:
		"""
		Returns a VersionType member with matching *hashname* if match exists, otherwise None.
		"""
		return cls.__hash2member_map__.get(hashname)


class AbstractClient(Enum):
	active: bool
	locale_code: str
	package_name: str

	def __new__(cls, value, active, locale, package_name):
		# this should be done differently, but i am too lazy to do that now
		# TODO: change it
		if not hasattr(cls, "package_names"):
			cls.package_names = {}

		obj = object.__new__(cls)
		obj._value_ = value
		obj.active = active
		obj.locale_code = locale
		obj.package_name = package_name
		cls.package_names[package_name] = obj
		return obj

	@classmethod
	def from_package_name(cls, package_name) -> Optional['AbstractClient']:
		return cls.package_names.get(package_name)


class Client(AbstractClient):
	EN = (1, True, 'en-US', 'com.YoStarEN.AzurLane')
	JP = (2, True, 'ja-JP', 'com.YoStarJP.AzurLane')
	CN = (3, True, 'zh-CN', '')
	KR = (4, True, 'ko-KR', 'kr.txwy.and.blhx')
	TW = (5, True, 'zh-TW', 'com.hkmanjuu.azurlane.gp')


@dataclass
class HashRow:
	filepath: str
	size: int
	md5hash: str

@dataclass
class CompareResult:
	current_hash: HashRow
	new_hash: HashRow
	compare_type: CompareType

@dataclass
class VersionResult:
	version: str
	vhash: str
	rawstring: str
	version_type: VersionType

@dataclass
class BundlePath:
	full: Path
	inner: str

	@staticmethod
	def construct(parentdir: Path, inner: Union[Path, str]) -> "BundlePath":
		fullpath = Path(parentdir, inner)
		return BundlePath(fullpath, str(inner))

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
