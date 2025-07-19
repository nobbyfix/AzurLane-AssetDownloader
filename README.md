# Azur Lane Asset Downloader and Extractor
This tool automatically downloads the newest assets directly from the game's CDN servers and allows extraction of Texture2D files as PNG images.

## Upgrade Notice
### From 2.x / no version number to 3.x+
When upgrading from versions 2.x or with no version number, the project has to be newly set up. To retain all current data the following folders can be copied to the new folder of the project:
- `config`: Only user_config.yml is required, the rest can be deleted.
- `ClientAssets` or directory set in `asset-directory` of the config: Contains all currently downloaded assets, version information und update logs used for extraction. Highly recommend to transfer to the new project folder.

## Setup
Before installation, Python 3.11 or newer needs to be available on the system. It is recommended to set the project up using [venv](https://docs.python.org/3/tutorial/venv.html) or a similar virtual environment manager. The project can be installed using pip:

```
pip install azlassets
```

Alternatively, to install the newest version from the repository (requires git on the system):
```
pip install git+https://github.com/nobbyfix/AzurLane-AssetDownloader.git
```

## Usage
There are three scripts to manage the assets:
- `obb_apk_import`: Importing assets from obb/apk/xapk files
- `downlader`: Downloading assets from the game server
- `extractor`: Extract PNGs from the assets

These can be executed using `py -m <scriptname>` on Windows or `python3 -m <scriptname>` on Linux/macOS (will be shortened to `py[thon3]` going forward, use the appropriate version for your system). Detailed usage will be explained in the following sections.

### 1. Import files from xapk/apk/obb
While this is *not necessary*, this step is **recommended** if you want all game assets available and not spam the game update server with errors of missing files on the first download.

The `obb_apk_import.py` supports all game clients (EN, JP, CN, KR, TW) and multiple forms of importing the assets. The recommended and easiest way is by downloading the `.xapk` from one of many Google Play Store app distributors (like APKMirror or APKPure). You can find them by searching for the package name, which are as follows:
- EN: com.YoStarEN.AzurLane
- JP: com.YoStarJP.AzurLane
- KR: kr.txwy.and.blhx
- TW: com.hkmanjuu.azurlane.gp

Alternatively if you already have the game installed, for example on emulators, you can copy the obb file onto your system and use it instead of the xapk. On Android it can be found in the folder `/storage/emulated/0/Android/obb/[PACKAGE_NAME]/`.

Since the CN client is not distributed through the Google Play Store, there is no xapk/obb file for it, but you can find the android download link on the [website](https://game.bilibili.com/blhx/) which will download an apk file (not xapk like the others). Alternatively, the APK is installed in the folder `/data/app/com.bilibili.azurlane-1/` on android (Note: Root access is required to access this folder).

You can then execute the script by passing it the filepath to the xapk/apk/obb:
```
py[thon3] -m obb_apk_import [FILEPATH]
```

### 2. Settings
The `config/user_config.yml` file provides a few settings to filter which files will be downloaded (and later also extracted). The options `download-folder-listtype` and `extract-folder-listtype` can be set to either "blacklist" or "whitelist". Depending on this it will filter by the top-level folder names (subfolders are not supported) or top-level filenames (files inside top-level folders or lower cannot be filtered) set in `download-folder-list` and `extract-folder-list`. This allows to cut down the download and extraction times by skipping unneeded assets.

### 3. Download new updates from the game
All assets normally distributed via the in-app downloader can be downloaded by simply executing:
```
py[thon3] -m downloader [CLIENT]
```
where `CLIENT` has to be either EN, CN, JP, KR or TW. You can check which files have been downloaded or deleted using the difflog files in `ClientAssets/[CLIENT]/difflog`.

### 4. Extract all new and changed files
The asset extraction script supports extraction of all newly downloaded files and single asset bundles. The newly downloaded assets can be extracted by executing:
```
py[thon3] -m extractor [CLIENT]
```
where `CLIENT` is again one of EN, CN, JP, KR or TW. The extracted images will then be saved in `ClientExtract/[CLIENT]/` Since only Texture2D assets are exported, it's not desired to try to export from all assetbundles (See [settings section](#2-settings)).

A single assetbundle can be extracted by passing the filepath to the script:
```
py[thon3] -m extractor -f [FILEPATH]
```

### 5. Enjoy the files
