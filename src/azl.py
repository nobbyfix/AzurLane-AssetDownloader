#!/usr/bin/env python
import argparse

from azlassets import __version__, config, downloadmgr, extractor, importer
from azlassets.classes import Client


def ensure_installed() -> bool:
	"""
	Returns `True` if the installation sucessfully completed, else `False`.
	"""
	return config.create_user_config()


def execute_download(args):
	downloadmgr.execute_from_args(args)


def execute_extract(args):
	extractor.execute_from_args(args)


def execute_import(args):
	importer.execute_from_args(args)


def add_subparser_download(parser):
	download_parser = parser.add_parser("download", aliases=["d"], help="Download assets for a client")
	download_parser.add_argument("client", type=str, choices=Client.__members__, help="client to update")
	download_parser.add_argument(
		"-e",
		"--extract",
		default=False,
		action=argparse.BooleanOptionalAction,
		help="Extract downloaded asset bundles to PNG images after download.",
	)
	download_parser.add_argument(
		"--force-refresh",
		default=False,
		action=argparse.BooleanOptionalAction,
		help="Compares asset hashes even when the version file is up to date.",
	)
	download_parser.add_argument(
		"--repair",
		default=False,
		action=argparse.BooleanOptionalAction,
		help="Downloads missing files if the update process failed partially.",
	)
	download_parser.add_argument(
		"--check-integrity",
		default=False,
		action=argparse.BooleanOptionalAction,
		help="Checks if all files are correct using the local hash file.",
	)
	download_parser.add_argument(
		"--ignore-hashfile",
		default=False,
		action=argparse.BooleanOptionalAction,
		help="Ignores the local hashfile and downloads ALL files again. This is only intended for testing purposes.",
	)
	download_parser.add_argument(
		"--skip-unknown-version-error",
		default=False,
		action=argparse.BooleanOptionalAction,
		help="Skips the UnknownVersionTypeError termination as a temporary fix if a new version type gets added.",
	)
	download_parser.set_defaults(func=execute_download)


def add_subparser_extract(parser):
	extract_parser = parser.add_parser("extract", aliases=["x"], help="Extract image assets as pngs")
	extract_parser.add_argument("client", nargs="?", type=str, choices=Client.__members__, help="client to extract files of")
	extract_parser.add_argument(
		"-f",
		"--filepath",
		type=str,
		help="""Path to a file or directory to extract. Directories will be extracted recursively.
				Supports both absolute filepaths and paths relative to the client assetbundle directory in conjunction with the client argument.""",
	)
	extract_parser.add_argument(
		"-v",
		"--version",
		type=str,
		help="""Version extraction string to extract specific versions.
				Uses a subset of the PEP 508/440 compliant version specifier format.
				Check README for details.""",
	)
	extract_parser.add_argument(
		"-l",
		"--linked-versions",
		default=True,
		action=argparse.BooleanOptionalAction,
		help="Whether linked versions should be extracted. Enabled by default.",
	)
	extract_parser.set_defaults(func=execute_extract)


def add_subparser_import(parser):
	import_parser = parser.add_parser("import", aliases=["i"], help="Import assets from obb/apk/xapk files")
	import_parser.add_argument("file", nargs=1, help="xapk/apk/obb file to extract")
	import_parser.add_argument(
		"-c",
		"--client",
		help="fallback client if it cannot be determined automatically (obb/apk only)",
		choices=Client.__members__,
	)
	import_parser.set_defaults(func=execute_import)


def add_subparsers(parser):
	add_subparser_download(parser)
	add_subparser_extract(parser)
	add_subparser_import(parser)


def main():
	print(f"Running Azurlane asset manager v{__version__}.")

	if ensure_installed():
		print("First time usage installation successfully completed.")
		return

	parser = argparse.ArgumentParser(description="Tool for Azurlane assets management")
	subparsers = parser.add_subparsers(dest="command", help="Available commands")
	add_subparsers(subparsers)

	args = parser.parse_args()
	if not args.command:
		parser.print_help()
		return

	args.func(args)


if __name__ == "__main__":
	main()
