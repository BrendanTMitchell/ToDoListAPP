"""Builds Palace.html: one self-contained file that opens by double-clicking (no server needed)."""
import json
from pathlib import Path

here = Path(__file__).parent
html = (here / "index.html").read_text(encoding="utf-8")
css = (here / "style.css").read_text(encoding="utf-8")
js = (here / "app.js").read_text(encoding="utf-8")
files = {name: (here / name).read_text(encoding="utf-8") for name in ("palacegames.py", "web_bridge.py")}


def script_safe(text):
	return text.replace("</", "<\\/")


embedded = "window.PALACE_FILES = " + script_safe(json.dumps(files)) + ";"
html = html.replace('<link rel="stylesheet" href="style.css">', "<style>\n" + css + "\n</style>")
html = html.replace(
	'<script src="app.js"></script>',
	"<script>\n" + embedded + "\n</script>\n<script>\n" + script_safe(js) + "\n</script>",
)
(here / "Palace.html").write_text(html, encoding="utf-8")
print("Wrote", here / "Palace.html")
