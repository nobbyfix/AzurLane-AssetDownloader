import requests


def request(error_msg: str, *args, **kwargs):
	while True:
		try:
			response = requests.get(*args, **kwargs)
			break
		except TimeoutError:
			print(error_msg)

	if response.status_code == 200:
		return response

def download_hashes(cdnurl, versionhash, useragent):
	if response := request("Hash request timed out, retrying.",
							f"{cdnurl}/android/hash/{versionhash}", headers={"user-agent": useragent}, timeout=30):
		return response.text

def download_asset(cdnurl, filehash, useragent):
	if response := request("Asset request timed out, retrying.",
							f"{cdnurl}/android/resource/{filehash}", headers={"user-agent": useragent}, timeout=20):
		return response.content
