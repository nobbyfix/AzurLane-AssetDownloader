import hashlib
import io
import itertools
import json
import re
import shutil
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tqdm import tqdm
from zipfile import ZipFile

from . import updater
from .classes import BundlePath, Client, CompareType, DownloadType, UpdateResult
from .config import load_user_config
from .versioncontrol import SimpleVersionResult, VersionController, VersionType, compare_version_string, parse_hash_rows


def calc_md5hash(data: bytes) -> str:
	"""
	Calculate MD5 hash of ``data``.

	Args:
		data: Raw bytes to hash

	Returns:
		str: The MD5 hash as a lowercase hexadecimal string
	"""
	md5 = hashlib.md5()
	md5.update(data)
	return md5.hexdigest()


def unpack(zipfile: ZipFile, client: Client):
	"""
	Unpack an OBB/APK archive into the client's asset directory.

	Args:
		zipfile: Open archive to unpack
		client: Client whose asset directory will receive the extracted files
	"""
	# load config data from files
	userconfig = load_user_config()
	CLIENT_ASSET_DIR = Path(userconfig.asset_directory, client.name)
	CLIENT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
	versioncontroller = VersionController(CLIENT_ASSET_DIR)

	# create {filename: filesize} dict for later recovery of missed files
	file_info_list = {f.filename: f.file_size for f in zipfile.filelist if not f.is_dir()}

	print("Unpacking archive...")
	for versiontype in VersionType:
		# make sure the version file exists
		if "assets/" + versiontype.version_filename not in zipfile.namelist():
			print(
				f"{versiontype.name}: The file {versiontype.version_filename} could not be found in the archive. Has the archive been modified?"
			)
			continue

		# read version string from obb
		with zipfile.open("assets/" + versiontype.version_filename, "r") as zf:
			obbversion = zf.read().decode("utf8")

		# if the obbversion is older, don't extract data from obb
		currentversion = versioncontroller.load_version_string(versiontype)
		if not compare_version_string(obbversion, currentversion):
			print(f"{versiontype.name}: Current version {currentversion} is same or newer than obb version {obbversion}.")
			continue

		# read hash files from obb and current file and compare them
		with zipfile.open("assets/" + versiontype.hashes_filename, "r") as hashfile:
			obbhashes = parse_hash_rows(hashfile.read().decode("utf8"))
		currenthashes = versioncontroller.load_hash_file(versiontype)
		comparison_results = updater.compare_hashes(currenthashes or [], obbhashes)

		# extract and delete files
		assetbasepath = Path(CLIENT_ASSET_DIR, "AssetBundles")
		update_files = list(
			itertools.chain(*[v for comp_type, v in comparison_results.items() if comp_type != CompareType.Unchanged])
		)
		update_results = [
			UpdateResult(r, DownloadType.NoChange, BundlePath.construct(assetbasepath, r.new_hash.filepath))  # pyright: ignore [reportOptionalMemberAccess]
			for r in comparison_results[CompareType.Unchanged]
		]

		fileamount = len(update_files)
		if fileamount > 0:
			files_not_found = []
			with tqdm(total=fileamount, desc=f"Extracting '{versiontype.hashname}' Files", unit="files") as progressbar:
				for result in update_files:
					if result.compare_type in [CompareType.New, CompareType.Changed]:
						assetpath = BundlePath.construct(assetbasepath, result.new_hash.filepath)  # pyright: ignore [reportOptionalMemberAccess]
						if pathresult := extract_asset(zipfile, assetpath.inner, assetpath.full):
							file_info_list.pop(pathresult)
							update_results.append(
								UpdateResult(
									result, DownloadType.Success if assetpath.full.exists() else DownloadType.Failed, assetpath
								)
							)
						else:
							files_not_found.append((assetpath, result))
					elif result.compare_type == CompareType.Deleted:
						assetpath = BundlePath.construct(assetbasepath, result.current_hash.filepath)  # pyright: ignore [reportOptionalMemberAccess]
						updater.delete_asset_safe(assetpath.full)
						update_results.append(UpdateResult(result, DownloadType.Removed, assetpath))
					progressbar.update()

			# try to find remaining files using their md5hash
			if len(files_not_found) > 0:
				file_info_groupby_size = defaultdict(list)
				for k, v in file_info_list.items():
					file_info_groupby_size[v].append(k)

				with tqdm(total=len(files_not_found), desc="Retrieving failed files", unit="files") as progressbar:
					for assetpath, result in files_not_found:
						fileinfo = file_info_groupby_size.get(result.new_hash.size)
						if not fileinfo:
							continue

						for zipf_path in fileinfo:
							with zipfile.open(zipf_path, "r") as zf:
								zipf_data = zf.read()
								zipf_md5hash = calc_md5hash(zipf_data)
								if result.new_hash.md5hash != zipf_md5hash:
									continue
								with open(assetpath.full, "wb") as f:
									f.write(zipf_data)
									update_results.append(
										UpdateResult(
											result,
											DownloadType.Success if assetpath.full.exists() else DownloadType.Failed,
											assetpath,
										)
									)
									break
						# else:
						# print( LOG ERROR MESSAGE HERE )
						progressbar.update()

		# update version string, hashes and difflog
		version = SimpleVersionResult(version=obbversion, version_type=versiontype)
		hashes_updated = updater.filter_hashes(update_results)
		versioncontroller.update_version_diffdata(version, hashes_updated, update_results)


def extract_asset(zipfile: ZipFile, filepath: str, target: Path) -> str | None:
	"""
	Extract a single asset from the archive to ``target``.

	Args:
		zipfile: Open archive to extract from
		filepath: Asset path relative to ``assets/AssetBundles/``
		target: Destination path to save the extracted file to

	Returns:
		str or None: The resolved in-archive path on success, None if not found
	"""
	target.parent.mkdir(exist_ok=True, parents=True)

	if "." in Path(filepath).name:
		assetpath = "assets/AssetBundles/" + filepath
	else:
		assetpath = "assets/AssetBundles/" + filepath + ".ys"

	try:
		with zipfile.open(assetpath, "r") as zf, open(target, "wb") as f:
			shutil.copyfileobj(zf, f)
			return assetpath
	except KeyError:
		pass


def extract_obb(path: Path, fallback_client: Client | None = None):
	"""
	Extract an OBB file, inferring the client from the filename.

	Args:
		path: Path to the OBB file
		fallback_client: Client to use if client can't be determined from filename
	"""
	for client in Client:
		if client.package_name and re.match(rf".*{client.package_name}\.obb", path.name):
			print(f"Determined client {client.name} from filename.")
			with ZipFile(path, "r") as zipfile:
				unpack(zipfile, client)
			break
	else:
		if fallback_client:
			print(f"Unpacking using provided client {fallback_client.name}.")
			with ZipFile(path, "r") as zipfile:
				unpack(zipfile, fallback_client)
		else:
			sys.exit(f'Filename "{path.name}" could not be associated with any known client.')


@dataclass
class ApkArchiveFormat:
	manifest_file: str
	package_name_key: str
	expansions_key: str
	expansion_path_fn: Callable


APK_FORMATS = {
	".xapk": ApkArchiveFormat(
		manifest_file="manifest.json",
		package_name_key="package_name",
		expansions_key="expansions",
		expansion_path_fn=lambda entry: entry["file"],
	),
	".apkm": ApkArchiveFormat(
		manifest_file="info.json",
		package_name_key="pname",
		expansions_key="obb_files",
		expansion_path_fn=lambda entry: entry,
	),
}


def extract_special_apk(path: Path, fmt: ApkArchiveFormat):
	"""
	Extract assets from an XAPK or APKM archive.

	Args:
	    path: Path to the XAPK or APKM file
	"""
	with ZipFile(path, "r") as archive:
		with archive.open(fmt.manifest_file, "r") as f:
			manifest = json.loads(f.read().decode("utf8"))

		if client := Client.from_package_name(manifest[fmt.package_name_key]):
			print(f"Determined client {client.name} from {fmt.manifest_file}.")
			for expansion in manifest[fmt.expansions_key]:
				obb_path = fmt.expansion_path_fn(expansion)
				with archive.open(obb_path, "r") as obb_file:
					# load full obb into memory to avoid repeated seeks over the outer zip
					obb_data = io.BytesIO(obb_file.read())
					with ZipFile(obb_data, "r") as obb:
						unpack(obb, client)
		else:
			print(f"Could not determine client from {fmt.manifest_file}.")


def detect_and_extract_special_apk(path: Path) -> bool:
	"""
	Detects the format and then extracts assets from an XAPK or APKM archive.

	Args:
		path: Path to the XAPK or APKM file

	Returns:
		bool: False if the format does not match XAPK or APKMm else True
	"""
	fmt = APK_FORMATS.get(path.suffix.lower())
	if fmt:
		extract_special_apk(path, fmt)
		return True
	return True


def extract(path: Path, fallback_client: Client | None = None):
	"""
	Dispatch extraction based on file extension.
	Exits with an error message if the file doesn't exist or has an unknown extension.

	Args:
		path: Path to the archive file
		fallback_client: Client to use when it cannot be inferred from the file
	"""
	if not path.exists():
		sys.exit("This file does not exist.")

	if path.suffix == ".obb":
		print("File has .obb extension.")
		extract_obb(path, fallback_client)
	elif path.suffix == ".apk":
		if fallback_client:
			apk_client = fallback_client
			print(f"File has .apk extension, using provided fallback client {apk_client.name}.")
		else:
			apk_client = Client.CN
			print(f"File has .apk extension and no fallback client has been provided, assuming {apk_client.name} client.")

		with ZipFile(path, "r") as zipfile:
			unpack(zipfile, apk_client)
	elif detect_and_extract_special_apk(path):
		pass
	else:
		sys.exit(f"Unknown file extension {path.suffix!r}.")


def execute_from_args(args):
	extract(Path(args.file[0]), args.client)
