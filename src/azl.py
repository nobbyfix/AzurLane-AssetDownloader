#!/usr/bin/env python
import argparse

# Import all necessary modules
from azlassets import __version__, downloadmgr, extractor, importer, config
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

def execute_from_parser_args(args):
    if args.command == "download":
        execute_download(args)
    elif args.command == "extract":
        execute_extract(args)
    elif args.command == "import":
        execute_import(args)


def add_subparser_download(parser):
    download_parser = parser.add_parser("download", help="Download assets for a client")
    download_parser.add_argument("client", type=str, choices=Client.__members__,
        help="client to update")
    download_parser.add_argument("--force-refresh", default=False, action=argparse.BooleanOptionalAction,
        help="Compares asset hashes even when the version file is up to date.")
    download_parser.add_argument("--repair", default=False, action=argparse.BooleanOptionalAction,
        help="Downloads missing files if the update process failed partially.")
    download_parser.add_argument("--check-integrity", default=False, action=argparse.BooleanOptionalAction,
        help="Checks if all files are correct using the local hash file.")
    download_parser.add_argument("--ignore-hashfile", default=False, action=argparse.BooleanOptionalAction,
        help="Ignores the local hashfile and downloads ALL files again. This is only intended for testing purposes.")
    download_parser.add_argument("--skip-unknown-version-error", default=False, action=argparse.BooleanOptionalAction,
        help="Skips the UnknownVersionTypeError termination as a temporary fix if a new version type gets added.")

def add_subparser_extract(parser):
    extract_parser = parser.add_parser("extract", help="Extract image assets as pngs")
    extract_parser.add_argument("client", type=str, choices=Client.__members__,
        help="client to extract files of")
    extract_parser.add_argument("-f", "--filepath", type=str,
        help="Path to the file or directly to extract only single file or all directory content")
    extract_parser.add_argument("-v", "--version", type=str,
        help="Extract files of a specific version (Currently only applies to AZL Versiontype!)")
    extract_parser.add_argument("-u", "--until-version", type=str,
        help="Extract files from the latest until a specific version (Currently only applies to AZL Versiontype!)")

def add_subparser_import(parser):
    import_parser = parser.add_parser("import", help="Import assets from obb/apk/xapk files")
    import_parser.add_argument('file', nargs=1, help='xapk/apk/obb file to extract')
    import_parser.add_argument('-c', '--client', help='fallback client if it cannot be determined automatically (obb/apk only)', choices=Client.__members__)

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

    execute_from_parser_args(args)

if __name__ == "__main__":
    main()
