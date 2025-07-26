from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Self


CompareType = Enum('CompareType', 'New Changed Unchanged Deleted')
DownloadType = Enum('DownloadType', 'NoChange Removed Success Failed ForDeletionNoChange')

class VersionType(Enum):
	__hash2member_map__: dict[str, Self] = {}
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
	MAP			= (10,	"maphash",		"map")


	def __init__(self, _, hashname, suffix) -> None:
		# add attributes to enum objects
		self.hashname = hashname
		self.suffix = suffix
		# add enum objects to member maps
		self.__hash2member_map__[hashname] = self

	def __str__(self) -> str:
		return self.name.lower()

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
	def from_hashname(cls, hashname: str) -> Self | None:
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
	def from_package_name(cls, package_name) -> Self | None:
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
	current_hash: HashRow | None
	new_hash: HashRow | None
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


# stolen from https://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
def printProgressBar(iteration, total, prefix = '', suffix = 'Complete', decimals = 1, length = 50, fill = '█', printEnd = "\r", details_unit = None) -> None:
	"""
	Call in a loop to create terminal progress bar
	@params:
		iteration	- Required  : current iteration (Int)
		total		- Required  : total iterations (Int)
		prefix		- Optional  : prefix string (Str)
		suffix		- Optional  : suffix string (Str)
		decimals	- Optional  : positive number of decimals in percent complete (Int)
		length		- Optional  : character length of bar (Int)
		fill		- Optional  : bar fill character (Str)
		printEnd	- Optional  : end character (e.g. "\r", "\r\n") (Str)
	"""
	if total <= 0: return None
	percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
	filledLength = int(length * iteration // total)
	progress = fill * filledLength + '-' * (length - filledLength)
	details = f" [{iteration}/{total} {details_unit}]" if details_unit else ""
	print(f'\r{prefix} |{progress}| {percent}% {suffix}{details}', end = printEnd)
	# Print New Line on Complete
	if iteration == total:
		print()

# simplified progress bar class with only the useful stuff i use
class ProgressBar():
	def __init__(self, total: int, prefix: str, suffix: str = "Complete", iterstart: int = 0, details_unit: str | None = None, print_on_init: bool = True):
		self.iteration = iterstart
		self.total = total
		self.prefix = prefix
		self.suffix = suffix
		self.details_unit = details_unit
		if print_on_init:
			printProgressBar(iterstart, total, prefix, suffix, details_unit=details_unit)

	def update(self, iteration: int | None = None):
		if iteration:
			self.iteration = iteration
		else:
			self.iteration += 1
		printProgressBar(self.iteration, self.total, self.prefix, self.suffix, details_unit=self.details_unit)


__all__ = [
	"CompareType",
	"DownloadType",
	"VersionType",
	"Client",
	"HashRow",
	"CompareResult",
	"VersionResult",
	"BundlePath",
	"UpdateResult",
	"UserConfig",
	"ClientConfig",
	"ProgressBar",
]
