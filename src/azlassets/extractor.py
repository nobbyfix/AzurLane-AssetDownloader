import itertools
import multiprocessing as mp
from argparse import ArgumentError
from pathlib import Path

from azlassets import config, imgrecon, versioncontrol
from azlassets.classes import BundlePath, Client, CompareType, DiffLog, SimpleVersionResult, UserConfig, VersionType


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


def extract_assetbundle(bpath: BundlePath, targetdir: Path) -> Path | None:
	"""
	Extract images from an assetbundle and write them as PNGs.
	Painting bundles are run through :func:`restore_painting` before saving.

	Args:
		bpath: Bundle path relative to the client assetbundle directory
		targetdir: Root output directory for extracted images

	Returns:
		Path or None: Output file (single image) or directory (multiple images),
		or None if no images were extracted
	"""
	all_images = []
	for reader, texture2d in imgrecon.load_images(str(bpath.full)):
		name = texture2d.m_Name
		if name == "UISprite":
			continue  # skip the UISprite element
		if "char" in (reader.container or ""):
			continue  # skip image if its of a chibi

		image = texture2d.image
		if bpath.inner.split("/")[0] == "painting":
			image = restore_painting(image, bpath.full, name, True)
		all_images.append((image, name))

	if len(all_images) == 1:
		image, imgname = all_images[0]
		target = Path(targetdir, bpath.inner).parent.joinpath(imgname + ".png")
		return try_safe_image(image, target)

	if len(all_images) > 1:
		img_target_dir = Path(targetdir, bpath.inner).parent.joinpath(bpath.full.name)
		for image, imgname in all_images:
			target = Path(img_target_dir, imgname + ".png")
			try_safe_image(image, target)
		return img_target_dir


class ClientExtractor:
	"""
	Handles asset bundle extraction for a specific game client.

	Manages the extraction pipeline from version difflog resolution through
	multiprocessed assetbundle extraction, applying user-configured directory
	filters along the way.
	"""

	userconfig: UserConfig
	client_asset_directory: Path
	client_extract_directory: Path
	vcontroller: versioncontrol.VersionController

	def __init__(
		self, client: Client, userconfig: UserConfig, vcontroller: versioncontrol.VersionController | None = None
	) -> None:
		"""
		Initialise a ClientExtractor for the given client.

		Args:
			client: The game client whose assets will be extracted.
			userconfig: User configuration supplying asset/extract directory paths and filter settings.
			vcontroller: Optional pre-constructed version controller. If omitted, one is created
				automatically from the client asset directory.
		"""
		self.userconfig = userconfig
		self.client_asset_directory = Path(userconfig.asset_directory, client.name)
		self.client_extract_directory = Path(userconfig.extract_directory, client.name)
		if not vcontroller:
			vcontroller = versioncontrol.VersionController(self.client_asset_directory)
		self.vcontroller = vcontroller

	def get_difflog_success_files(self, difflog: DiffLog) -> list[BundlePath]:
		"""
		Return all successfully processed bundle paths from a difflog, excluding deleted files.

		Args:
			difflog: The difflog whose successful file entries should be retrieved.

		Returns:
			list[BundlePath]: Successful bundle paths.
		"""
		return difflog.get_success_files(lambda ctype: ctype != CompareType.Deleted)

	def get_version_success_files(self, version: SimpleVersionResult) -> list[BundlePath]:
		"""
		Load the difflog for a version and return its successful (non-deleted) bundle paths.

		Args:
			version: The version result whose difflog should be loaded.

		Returns:
			list[BundlePath]: Successful bundle paths for the version, or an empty list if no
			difflog exists for it.
		"""
		if difflog := self.vcontroller.load_difflog(version):
			return self.get_difflog_success_files(difflog)
		return []

	def extract_difflog(self, difflog: DiffLog, with_linked_versions: bool = False):
		"""
		Extract all asset bundles referenced by a difflog.

		Collects changed and added files from the difflog (and optionally from any linked
		versions), applies the directory filter defined in ``userconfig``, then extracts
		the remaining bundles. Output images are written under ``client_extract_directory/<version>/``.

		Args:
			difflog: The difflog describing which asset bundles changed in a version.
			with_linked_versions: If ``True``, also extract assets from versions linked
				to this difflog. Defaults to ``False``.
		"""
		print(f"Extracting files for '{difflog.version}'", end="")
		file_collection = {difflog.version: self.get_difflog_success_files(difflog)}
		if with_linked_versions:
			print(" with linked versions.")
			for vtype, vstrings in difflog.linked_versions.items():
				for vstring in vstrings:
					svr = SimpleVersionResult(version_type=vtype, version=vstring)
					if success_file_result := self.get_version_success_files(svr):
						file_collection[svr] = success_file_result
		else:
			print(".")

		print("Pre-filter amount of changed and added files:")
		for svr, success_files in file_collection.items():
			print(f"* {svr}: {len(success_files)}")

		extract_filter_dirs = self.userconfig.extract_filter
		is_blacklist = self.userconfig.extract_isblacklist

		def _filter(bpath: BundlePath) -> bool:
			if bpath.inner.split("/")[0] in extract_filter_dirs:
				return not is_blacklist
			return is_blacklist

		filtered_file_collection = {}
		for svr, success_files in file_collection.items():
			if filtered_files := list(filter(_filter, success_files)):
				filtered_file_collection[svr] = filtered_files

		print("Amount of files to be extracted after applying userconfig filter:")
		for svr, filtered_files in filtered_file_collection.items():
			print(f"* {svr}: {len(filtered_files)}")

		total_files = list(itertools.chain.from_iterable(filtered_file_collection.values()))
		print(f"Total: {len(total_files)}")

		print("Starting extraction...")
		extract_directory = Path(self.client_extract_directory, difflog.version.version)
		with mp.Pool(processes=mp.cpu_count() - 1) as pool:
			for bundlepath in total_files:
				pool.apply_async(
					extract_assetbundle,
					(
						bundlepath,
						extract_directory,
					),
				)

			# explicitly join pool, to wait for all asnyc tasks to complete
			pool.close()
			pool.join()

		print("Extraction completed.")

	def extract_version(self, version: SimpleVersionResult, with_linked_versions: bool = False):
		"""
		Extract all asset bundles for a specific version.

		Loads the difflog for ``version`` and delegates to :meth:`extract_difflog`.
		Emits a warning if no difflog is found for the requested version.

		Args:
			version: The version whose assets should be extracted.
			with_linked_versions: Forwarded to :meth:`extract_difflog`. If ``True``,
				linked versions are extracted alongside the primary one.
		"""
		if difflog := self.vcontroller.load_difflog(version):
			self.extract_difflog(difflog, with_linked_versions)
		else:
			print(f"WARN: Tried to extract version '{version}' while it does not exist.")

	def extract_latest(self, vtype: VersionType = VersionType.AZL, with_linked_versions: bool = False):
		"""
		Extract assets for the latest available version of a given version type.

		Resolves the most recent version for ``vtype`` via the version controller and
		delegates to :meth:`extract_version`. Emits a warning if no version is found.

		Args:
			vtype: The version type to look up.
			with_linked_versions: Forwarded to :meth:`extract_version`. If ``True``,
				linked versions are extracted alongside the primary one.
		"""
		if latest_version := self.vcontroller.load_version(vtype):
			self.extract_version(latest_version, with_linked_versions)
		else:
			print(f"WARN: Tried to extract latest version {vtype.name!r} while it does not exist.")


def extract_latest_client(client: Client, vtype: VersionType = VersionType.AZL, with_linked_versions: bool = False):
	"""
	Convenience function to extract the latest assets for a client.

	Args:
		client: The game client whose assets should be extracted.
		vtype: The version type to extract.
		with_linked_versions: If ``True``, linked versions are extracted alongside the primary one.
	"""
	userconfig = config.load_user_config()
	client_extractor = ClientExtractor(client, userconfig)
	client_extractor.extract_latest(vtype, with_linked_versions)


def extract_single_assetbundle(assetpath_str: str, client: Client | None):
	"""
	Extract a single asset bundle (or all bundles in a directory) for a client.

	If ``assetpath`` points to a directory, all files within it are extracted
	recursively. Otherwise the single bundle at that path is extracted.

	Args:
		client: Client whose asset directory should be used
		assetpath_str: Path to a singular asset or directory, may be absolute or relative
			to the client assetbundle directory
	"""
	print(f"Extracting assets from '{assetpath_str}'")
	userconfig = config.load_user_config()
	assetpath = Path(assetpath_str)
	if client is None:
		if not assetpath.is_absolute():
			raise FileNotFoundError("ERROR: Extraction from relative path requires client information!")
		client = Client[assetpath.relative_to(Path(userconfig.asset_directory).absolute()).parts[0]]

	client_assetbundle_directory = Path(userconfig.asset_directory, client.name, "AssetBundles")
	extract_directory = Path(userconfig.extract_directory, client.name, "single_extractions")
	if not assetpath.is_absolute():
		assetpath = Path(client_assetbundle_directory, assetpath)

	if assetpath.is_file():
		assetpath_inner = assetpath.relative_to(client_assetbundle_directory.absolute())
		bpath = BundlePath.construct(client_assetbundle_directory, assetpath_inner)
		extract_assetbundle(bpath, extract_directory)
		print("Finished extraction of singular asset bundle.")

	elif assetpath.is_dir():
		client_assetbundle_directory_abs = client_assetbundle_directory.absolute()
		for p in assetpath.rglob("*"):
			if p.is_file():
				assetpath_inner = p.relative_to(client_assetbundle_directory_abs)
				bpath = BundlePath.construct(client_assetbundle_directory, assetpath_inner)
				extract_assetbundle(bpath, extract_directory)
		print("Finished extraction of directory.")
	else:
		raise FileNotFoundError("ERROR: Invalid file path!")


def execute_from_args(args):
	# parse arguments and execute
	client = Client.__members__.get(args.client)
	if filepath := args.filepath:
		extract_single_assetbundle(filepath, client)
	elif client:
		extract_latest_client(client, with_linked_versions=True)
	else:
		raise ArgumentError(None, "At least one of either 'client' or 'filepath' argument is required!")
