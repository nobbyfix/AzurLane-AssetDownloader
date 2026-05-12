import itertools
import multiprocessing as mp
from pathlib import Path

from azlassets import config, imgrecon, versioncontrol
from azlassets.classes import BundlePath, Client, CompareType, SimpleVersionResult, VersionType


def restore_painting(image, abpath: Path, imgname: str, _do_retry: bool = True):
	"""
	Reconstruct a painting image using its associated mesh data.

	Args:
		image: Source image to reconstruct
		abpath: Path to the asset bundle containing the mesh
		imgname: Base name of the image, used to locate the mesh
		_do_retry: Internal use only. If ``True`` and mesh was not found on first try,
			try to find it in other locations.

	Returns:
		PIL.Image: Reconstructed image, or the original if no mesh is found
	"""
	if mesh := imgrecon.load_mesh(str(abpath), imgname + "-mesh"):
		return imgrecon.recon(image, mesh)

	if not _do_retry:
		return image

	# for some images, the mesh is in the non-tex asset bundle for some reason
	if abpath.name.endswith("_tex"):
		return restore_painting(image, abpath.with_name(abpath.name[:-4]), imgname, False)

	return restore_painting(image, abpath.with_name(abpath.name + "_tex"), imgname, False)


def try_safe_image(image, target: Path) -> Path:
	"""
	Save an image to ``target``, appending ``_`` to the stem if the path is taken until a free path is found.

	Args:
		image: PIL image to save
		target: Desired output path

	Returns:
		Path: The path the image was actually saved to
	"""
	target.parent.mkdir(parents=True, exist_ok=True)
	while True:
		if target.exists():
			print(f"ERROR: Tried to save '{target}', but the file already exists.")
			target = target.with_name(target.stem + "_" + target.suffix)
		else:
			image.save(target)
			return target


def extract_assetbundle(root_asset_directory: Path, filepath: str, targetfolder: Path) -> Path | None:
	"""
	Extract images from an assetbundle and write them as PNGs.
	Painting bundles are run through :func:`restore_painting` before saving.

	Args:
		root_asset_directory: Root directory containing asset bundles
		filepath: Bundle path relative to ``root_asset_directory``
		targetfolder: Root output directory for extracted images

	Returns:
		Path or None: Output file (single image) or directory (multiple images),
		or None if no images were extracted
	"""
	all_images = []
	path_assetbundle = Path(root_asset_directory, filepath)
	for reader, texture2d in imgrecon.load_images(str(path_assetbundle)):
		name = texture2d.m_Name
		if name == "UISprite":
			continue  # skip the UISprite element
		if "char" in (reader.container or ""):
			continue  # skip image if its of a chibi

		image = texture2d.image
		if filepath.split("/")[0] == "painting":
			image = restore_painting(image, path_assetbundle, name, True)
		all_images.append((image, name))

	if len(all_images) == 1:
		image, imgname = all_images[0]
		target = Path(targetfolder, filepath).parent.joinpath(imgname + ".png")
		return try_safe_image(image, target)

	if len(all_images) > 1:
		img_target_dir = Path(targetfolder, filepath).parent.joinpath(path_assetbundle.name)
		for image, imgname in all_images:
			target = Path(img_target_dir, imgname + ".png")
			try_safe_image(image, target)
		return img_target_dir


def get_diff_files(versioncontroller: versioncontrol.VersionController, vresult: SimpleVersionResult) -> list[BundlePath]:
	"""
	Return the successfully updated bundle paths recorded in a difflog.
	Entries with ``CompareType.Deleted`` are excluded.

	Args:
		versioncontroller: The version controller used to load the difflog
		vresult: Version type and string identifying the difflog to load

	Returns:
		list[BundlePath]: Bundle paths from the difflog's success files,
		or an empty list if no difflog is found
	"""
	if difflog := versioncontroller.load_difflog(SimpleVersionResult(version=vresult.version, version_type=vresult.version_type)):
		filtered_success_file_entries = filter((lambda i: i[1] != CompareType.Deleted), difflog.success_files.items())
		bundlepaths = [i[0] for i in filtered_success_file_entries]
		return bundlepaths
	return []


def extract_by_client(client: Client, target_version: str | None = None, do_iterative_version_check: bool = False):
	"""
	Extract assets for a client using difflog records, in parallel.

	Version types searched depend on ``target_version``: ``None``/``"latest"``
	scans AZL, PAINTING, MANGA, and PIC; any specific version scans AZL only.

	When ``do_iterative_version_check`` is True, all difflog versions up to and
	including ``target_version`` are included; otherwise only the exact version
	is used.

	Asset bundle paths are filtered by ``userconfig.extract_filter`` before
	extraction. Extraction runs across ``cpu_count - 1`` worker processes.

	Args:
		client: Client whose assets should be extracted
		target_version: Version string to extract, ``"latest"``, or None for latest
		do_iterative_version_check: If True, include all versions up to ``target_version``
	"""
	userconfig = config.load_user_config()
	client_directory = Path(userconfig.asset_directory, client.name)
	extract_directory = Path(userconfig.extract_directory, client.name)

	downloaded_files_collection = []
	if target_version is None or target_version == "latest":
		target_versiontypes = [VersionType.AZL, VersionType.PAINTING, VersionType.MANGA, VersionType.PIC]
	else:
		target_versiontypes = [VersionType.AZL]

	versioncontroller = versioncontrol.VersionController(client_directory)
	for vtype in target_versiontypes:
		if do_iterative_version_check:
			version_strings = []
			for vstring in versioncontroller.get_difflog_versionlist(vtype):
				if versioncontrol.compare_version_string(vstring, target_version) or vstring == target_version:
					version_strings.append(vstring)
		else:
			if not target_version:
				target_version = versioncontroller.load_version_string(vtype)
			version_strings = [target_version]

		for vstring in version_strings:
			if vstring:
				vresult = SimpleVersionResult(version=vstring, version_type=vtype)
				downloaded_files = get_diff_files(versioncontroller, vresult)
				downloaded_files_collection.append(downloaded_files)
	downloaded_files_collection = itertools.chain(*downloaded_files_collection)

	def _filter(bundlepath: BundlePath) -> bool:
		if bundlepath.inner.split("/")[0] in userconfig.extract_filter:
			return not userconfig.extract_isblacklist
		return userconfig.extract_isblacklist

	with mp.Pool(processes=mp.cpu_count() - 1) as pool:
		for bundlepath in filter(_filter, downloaded_files_collection):
			pool.apply_async(
				extract_assetbundle,
				(
					Path(client_directory, "AssetBundles"),
					bundlepath.inner,
					extract_directory,
				),
			)

		# explicitly join pool
		# this causes the pool to wait for all asnyc tasks to complete
		pool.close()
		pool.join()


def extract_single_assetbundle(client: Client, assetpath: str):
	"""
	Extract a single asset bundle (or all bundles in a directory) for a client.

	If ``assetpath`` points to a directory, all files within it are extracted
	recursively. Otherwise the single bundle at that path is extracted.

	Args:
		client: Client whose asset directory should be used
		assetpath: Path relative to the client's ``AssetBundles`` directory
	"""
	userconfig = config.load_user_config()
	client_directory = Path(userconfig.asset_directory, client.name, "AssetBundles")
	extract_directory = Path(userconfig.extract_directory, client.name)

	abpath = Path(client_directory, assetpath)
	if abpath.is_dir():
		for ab_in_dir_path in abpath.rglob("*"):
			if not ab_in_dir_path.is_dir():
				extract_assetbundle(client_directory, str(ab_in_dir_path.relative_to(client_directory)), extract_directory)
	else:
		extract_assetbundle(client_directory, assetpath, extract_directory)


def execute_from_args(args):
	# parse arguments and execute
	client = Client[args.client]
	if filepath := args.filepath:
		extract_single_assetbundle(client, filepath)
	else:
		if version := args.until_version:
			extract_by_client(client, version, True)
		elif version := args.version:
			extract_by_client(client, version)
		else:
			extract_by_client(client)
