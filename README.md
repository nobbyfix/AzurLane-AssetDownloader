# Azur Lane Asset Downloader and Extractor
This tool automatically downloads the newest assets directly from the game cdn servers and extracts the Texture2D files as png from them.

## Before you start
Python 3.9+ is required with the following libraries: `requests`, `UnityPy`, `PyYAML`, `Pillow`.

## HOW TO USE
### 1. Import files from xapk/apk/obb
While this is *not neccessary*, this step is **recommended** if you want all game assets available and not spam the game update server with errors on the first download.

The `obb_apk_import.py` supports all game clients (EN, JP, CN, KR, TW) and multiple forms of importing the assets. The recommend and easiest way is by downloading the `.xapk` from one of many Google Play Store app distributors (like APKPure). You can find them by searching for the package name, which are as follows:
- EN: com.YoStarEN.AzurLane
- JP: com.YoStarJP.AzurLane
- KR: kr.txwy.and.blhx
- TW: com.hkmanjuu.azurlane.gp

Anternatively if you already have the game installed, for example on emulators, you can also copy the obb file onto your system and use it instead of the xapk. On android it can be found in the folder `/storage/emulated/0/Android/obb/[PACKAGE_NAME]/`.

Since the CN client is not distributed through the Google Play Store, there is no xapk/obb file for it but you can find the android download link on the [website](https://game.bilibili.com/blhx/) which will download an apk file (not xapk like the others). Alternatively the apk is installed in the folder `/data/app/com.bilibili.azurlane-1/` on android (Note: you need root permission to access this folder).

You can then execute the script by passing it the filepath to the xapk/apk/obb:
```
./obb_apk_import.py [FILEPATH]
```

### 2. Settings
The `config/user_config.yml` file provides a few settings to filter which files will be downloaded (and later also extracted). The options `download-folder-listtype` and `extract-folder-listtype` can be set to either "blacklist" or "whitelist". Depending on this it will filter by the top-level foldernames (sub folders are not supported) or top-level filenames (files inside top-level folders or lower can not be filtered) set in `download-folder-list` and `extract-folder-list`. This allows to cut down the download and extraction times by skipping unneeded assets.

### 3. Download new updates from the game
**Note: To prevent helping cheaters, two files needed for this part are missing. If you ask me nicely on Discord (nobbyfix#2338) i may provide them to you (usually only if you are an active wiki member).**

All assets that are usually distributed through the in-app downloader can be downloaded by simply executing:
```
./main.py [CLIENT]
```
where `CLIENT` has to be either EN, CN, JP, KR or TW. You can check which files have been downloaded or deleted using the difflog files in `ClientAssets/[CLIENT]/difflog`.

### 4. Extract all new and changed files
The asset extraction script supports extraction of all newly downloaded files and single asset bundles. The newly downloaded assets can be extracted by executing:
```
./extractor [CLIENT]
```
where `CLIENT` is again one of EN, CN, JP, KR or TW. The extracted images will then be saved in `ClientExtract/[CLIENT]/` Since only Texture2D assets are exported, its not desired to try to export from all assetbundles (See [settings section](#2-settings)).

A single assetbundle can be extracted by passing the filepath to the script:
```
./extractor -f [FILEPATH]
```

### 5. Enjoy the files
