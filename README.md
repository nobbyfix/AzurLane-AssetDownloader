# Azur Lane Asset Downloader and Extractor
This tool automatically downloads the newest assets directly from the game's CDN servers and allows extraction of Texture2D files as PNG images.

## Upgrade Notice
### From 2.x / no version number to 3.x+
When upgrading from versions 2.x or with no version number, the project has to be newly set up. To retain all current data, the following folders should be copied to the new working directory:
- `config`: Only `user_config.yml` is required, the rest can be deleted.
- `ClientAssets` or directory set in `asset-directory` of the config: Contains all currently downloaded assets, version information, and update logs used for extraction. Highly recommended  to transfer to the new working directory.

## Setup
Before installation, Python 3.11 or newer needs to be available on the system. It is recommended to set the project up using [venv](https://docs.python.org/3/tutorial/venv.html) or a similar virtual environment manager.

Install the project using pip:
```bash
pip install azlassets
```

To create the config file for editing before first usage, execute `azl` in a terminal.

### Settings
The `config/user_config.yml` file provides a few settings to filter which files will be downloaded and extracted. The options `download-folder-listtype` and `extract-folder-listtype` can be set to either "blacklist" or "whitelist". Depending on this it will filter by the top-level folder names (subfolders are not supported) or top-level filenames (files inside top-level folders or lower cannot be filtered) set in `download-folder-list` and `extract-folder-list`. This allows for reduced download and extraction times by skipping unneeded assets.

## Usage
The program can be executed using `azl <command>` with different commands available depending on the desired functionality, which will be explained in the following sections.

### Importer
Using this is *not necessary* to get all files, but **recommended** as the asset server may not have all files available. An import will guarantee that all game assets will be available on your system (if so desired) and avoid potentially spamming the asset server with errors of missing files on the first download.

The import supports all game clients (EN, JP, CN, KR, TW) and multiple forms of importing the assets. The recommended and easiest way is by downloading the `.xapk` from one of many Google Play Store app distributors (like APKMirror or APKPure). They can be found by searching for the package name, which are as follows:
- EN: com.YoStarEN.AzurLane
- JP: com.YoStarJP.AzurLane
- KR: kr.txwy.and.blhx
- TW: com.hkmanjuu.azurlane.gp

If the game is already installed on emulators, copy the obb file to your system. On Android it can be found in `/storage/emulated/0/Android/obb/[PACKAGE_NAME]/`.

For CN client (not distributed through Google Play Store), download an APK from the [official website](https://game.bilibili.com/blhx/). Alternatively, the APK can be found in `/data/app/com.bilibili.azurlane-1/` on Android (Note: Root access required).

The `import` command can be executed by passing it the filepath to the xapk/apk/obb:
```bash
azl import [FILEPATH]
```

If the program cannot detect the client automatically, specify it with:
```bash
azl import [FILEPATH] -c {CLIENT}
```

### Downloader
All assets normally distributed via the in-app downloader can be downloaded by executing:
```bash
azl download [CLIENT]
```

Where `CLIENT` is one of EN, CN, JP, KR or TW. Check downloaded/deleted files using difflog files in `ClientAssets/[CLIENT]/difflog`.

#### Additional Arguments
- `--force-refresh`: Ignores version check, useful after editing config
- `--repair`: Checks all files and downloads only missing ones, useful for resuming crashed downloads
- `--check-integrity`: Checks for modified, deleted, or corrupt files and redownloads them
- `--skip-unknown-version-error`: Ignores the error when a new version type gets added to the game

### Extractor
The asset extraction supports extraction of all newly downloaded files or single asset bundles.

```bash
azl extract [CLIENT]
```

Where `CLIENT` is one of EN, CN, JP, KR or TW. Extracted images will be saved in `ClientExtract/[CLIENT]/`. Since only Texture2D assets are exported, it's not desired to try to export from all assetbundles (See [settings section](#settings)).

A single assetbundle can be extracted by passing the filepath to the script:
```bash
azl extractor -f [FILEPATH]
```
