# Upgrade Guide
When upgrading from the following major versions to a newer one, manual action may be required:
* 4.x or lower → 5.x+
* 2.x / no version number → 3.x+

## 4.x or lower → 5.x+
With version 5.0.0, the user configuration file has been updated to use the TOML format, and a default configuration file has been introduced. This change allows the default configuration to update automatically, for example to update the extraction whitelist, when you upgrade the package. To ensure a smooth transition, **the old YAML configuration file will remain supported throughout version 5.x**, with support being fully removed in version 6.0.0.

**If you have never modified the configuration file**, you can simply delete `config/user_config.yml` to get rid the warning displayed every time the program runs. If you choose to keep the file, the warning will disappear once you update to version 6.0.0 or higher (once those are released) and the new default configuration will take effect.

Additionally **version 5.0.0 includes an automatic converter** that converts the existing YAML configuration file to the new TOML format. Use this only if you want a 1:1 conversion of your current settings. You can execute it with `azl convert`. The old YAML configuration file will be deleted once the conversion is complete.

## 2.x / no version number → 3.x+
When upgrading from versions 2.x or with no version number, the project has to be newly set up. To retain all current data, the following folders should be copied to the new working directory:
- `config`: Only `user_config.yml` is required, the rest can be deleted.
- `ClientAssets` or directory set in `asset-directory` of the config: Contains all currently downloaded assets, version information, and update logs used for extraction. Highly recommended  to transfer to the new working directory.
