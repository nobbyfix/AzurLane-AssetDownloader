import builtins
import fnmatch
from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")


class PathFilter:
	whitelist: list[str]
	whitelist_glob: list[str]
	blacklist: list[str]
	blacklist_glob: list[str]

	def __init__(self, raw_patterns_whitelist: Iterable[str], raw_patterns_blacklist: Iterable[str]) -> None:
		self.whitelist, self.whitelist_glob = parse_raw_patterns(raw_patterns_whitelist)
		self.blacklist, self.blacklist_glob = parse_raw_patterns(raw_patterns_blacklist)

	def filter(self, paths: Iterable[T], access_func: Callable | None = None) -> Iterable[T]:
		if access_func is None:
			access_func = lambda v: v

		return builtins.filter(lambda path: self.is_allowed(access_func(path)), paths)

	def is_allowed(self, path: str) -> bool:
		whitelisted = True if not (self.whitelist or self.whitelist_glob) else self.is_whitelisted(path)
		blacklisted = self.is_blacklisted(path)
		return whitelisted and not blacklisted

	def is_whitelisted(self, path: str) -> bool:
		for pattern in self.whitelist:
			if path.startswith(pattern):
				return True
		for pattern in self.whitelist_glob:
			if fnmatch.fnmatch(path, pattern):
				return True
		return False

	def is_blacklisted(self, path: str) -> bool:
		for pattern in self.blacklist:
			if path.startswith(pattern):
				return True
		for pattern in self.blacklist_glob:
			if fnmatch.fnmatch(path, pattern):
				return True
		return False


def contains_glob_char(pattern: str) -> bool:
	return "*" in pattern or "?" in pattern or "[" in pattern or "]" in pattern or "!" in pattern


def parse_raw_patterns(raw_patterns: Iterable[str]) -> tuple[list[str], list[str]]:
	startswith_patterns = []
	glob_patterns = []

	for p in raw_patterns:
		if contains_glob_char(p):
			glob_patterns.append(p)
		else:
			startswith_patterns.append(p)

	return startswith_patterns, glob_patterns
