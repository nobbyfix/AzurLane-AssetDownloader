import re
import UnityPy.config
import warnings
from PIL import Image
from UnityPy import AssetsManager
from UnityPy.enums import ClassIDType
from UnityPy.exceptions import UnityVersionFallbackWarning

# some files have their version stripped recently, this is the last version used before that
UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.51f1"
# ignore warning completely since it's expected to occur
# additionally the default setting 'once' gets trigged multiple times anyway when using multiprocessing (once per process)
warnings.simplefilter("ignore", UnityVersionFallbackWarning)


VR = re.compile(r"v ")
TR = re.compile(r"vt ")
SR = re.compile(r" ")


def recon(src, mesh):
	sx, sy = src.size
	c = map(SR.split, list(filter(TR.match, mesh))[1::2])
	p = map(SR.split, list(filter(VR.match, mesh))[1::2])
	c = [(round(float(a[1]) * sx), round((1 - float(a[2])) * sy)) for a in c]
	p = [(-int(float(a[1])), int(float(a[2]))) for a in p]
	my = max(y for x, y in p)
	p = [(x, my - y) for x, y in p[::2]]
	cp = [(l + r, p) for l, r, p in zip(c[::2], c[1::2], p)]
	ox, oy = zip(*[(r - l + p, b - t + q) for (l, t, r, b), (p, q) in cp])
	out = Image.new("RGBA", (max(ox), max(oy)))
	for c, p in cp:
		out.paste(src.crop(c), p)
	return out


def load_mesh(filepath, require_name=None):
	am = AssetsManager(filepath)
	for obj in am.objects:
		if obj.type == ClassIDType.Mesh:
			objdata = obj.read()
			if require_name and require_name != objdata.m_Name:
				continue
			data = objdata.export().splitlines()
			return data


def load_images(filepath: str):
	am = AssetsManager(filepath)
	for obj in am.objects:
		if obj.type == ClassIDType.Texture2D:
			yield obj, obj.read()
