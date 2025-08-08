# Changelog

## [3.4.0](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.3.2...v3.4.0) (2025-08-08)


### Features

* allow extraction of entire directories ([24db4c3](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/24db4c35bd4834b42748ac03f52977d1ed761fa7))


### Bug Fixes

* crash when progressbar total is non-positive number ([5578cd1](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/5578cd132334a8dea4841c5350e6a36a9482a244))

## [3.3.2](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.3.1...v3.3.2) (2025-07-21)


### Bug Fixes

* downloads timing out too soon ([049d4f0](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/049d4f07b66c01c1836324b1a6c23c567401d11c))

## [3.3.1](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.3.0...v3.3.1) (2025-07-21)


### Bug Fixes

* add minimum aiohttp version to support new url syntax ([58e2df4](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/58e2df4a87e278f5af6269349d4fd2affdbbbcfd))

## [3.3.0](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.2.1...v3.3.0) (2025-07-19)


### Features

* add build and publishing to pypi ([824292a](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/824292a51740d76d73353fc9124450417ab41a13))

## [3.2.1](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.2.0...v3.2.1) (2025-07-19)


### Bug Fixes

* bump version number ([70888c3](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/70888c3c24074e45b59511227a44e34d1e42670b))

## [3.2.0](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.1.0...v3.2.0) (2025-07-09)


### Features

* progress bars when using repair ([bbdcf9d](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/bbdcf9d07ac2bcd074b5070b2b466d5ed04f367f))
* re-enable repair functionality with asyncio support ([d4006cd](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/d4006cd9b809bd276114d959d67a0afcefd3fccb))


### Bug Fixes

* add missing hash function on BundlePath class ([91cb722](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/91cb7228567f51e34c68631074cff4a6712c82dc))
* deletion skipped files not being added to hashfile ([39707f9](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/39707f90b488f25262571bb5eab49840ad0e5fee))
* inaccurate difflog when using repair after partial download ([0c9ad29](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/0c9ad2985dd804f3831c810be0278cb3df1f075f))

## [3.1.0](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v3.0.0...v3.1.0) (2025-07-06)


### Features

* disable check integrity functionality ([7ea2fa5](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/7ea2fa5874891d535751c0bb9e03d6ece8c06a33))


### Bug Fixes

* correctly parse comparison results used for import processing ([5b97ba9](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/5b97ba99ad4314d314d58795380ce3f4ad351e08))

## [3.0.0](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v2.2.0...v3.0.0) (2025-07-06)


### ⚠ BREAKING CHANGES

* The installation and usage has changed and are not compatible with previous versions. Please refer to the README for updated installation and usage instructions.

### Features

* restructure project to allow installation through pip ([db4cd3b](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/db4cd3bf85ab7f5b961c4b6919e2f8ec294212f7))


### Bug Fixes

* correctly handle config filepaths ([241cf96](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/241cf965c6c35f3b93082de21563ba4cb9a4475e))
* correctly import protobuf modules ([0b704ce](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/0b704cec26ccf068a9dab56ca1e51c6319f7e96e))

## [2.2.0](https://github.com/nobbyfix/AzurLane-AssetDownloader/compare/v2.1.0...v2.2.0) (2025-07-05)


### Features

* add license ([efa1929](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/efa1929c82350630841ad78096683a31032acaf5))
* add version ([752a46a](https://github.com/nobbyfix/AzurLane-AssetDownloader/commit/752a46aac5f1e8c87be70c9e50ef9ef595f3c895))
