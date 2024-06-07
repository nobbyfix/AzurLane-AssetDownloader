import re
from UnityPy import AssetsManager
from UnityPy.enums import ClassIDType
from PIL import Image


VR = re.compile(r'v ')
TR = re.compile(r'vt ')
SR = re.compile(r' ')
def recon(src, mesh):
	sx, sy = src.size
	c = map(SR.split, list(filter(TR.match, mesh))[1::2])
	p = map(SR.split, list(filter(VR.match, mesh))[1::2])
	c = [(round(float(a[1])*sx), round((1-float(a[2]))*sy)) for a in c]
	p = [(-int(float(a[1])), int(float(a[2]))) for a in p]
	my = max(y for x, y in p)
	p = [(x, my-y) for x, y in p[::2]]
	cp = [(l+r, p) for l, r, p in zip(c[::2], c[1::2], p)]
	ox, oy = zip(*[(r-l+p, b-t+q) for (l, t, r, b), (p, q) in cp])
	out = Image.new('RGBA', (max(ox), max(oy)))
	for c, p in cp: out.paste(src.crop(c), p)
	return out

def load_mesh(filepath, require_name=None):
	am = AssetsManager(filepath)
	for obj in am.objects:
		if obj.type == ClassIDType.Mesh:
			objdata = obj.read()
			if require_name and require_name != objdata.name:
				continue
			data = objdata.export().splitlines()
			return data 

def load_images(filepath: str):
	am = AssetsManager(filepath)
	for obj in am.objects:
		if obj.type == ClassIDType.Texture2D:
			yield obj.read()
