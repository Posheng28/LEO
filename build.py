# 組出網頁：src/template.html ＋ src/co_data.js → LEO.html、index.html（兩份內容相同）
# 用法：python -X utf8 build.py
import io, os

here = os.path.dirname(os.path.abspath(__file__))
tpl = io.open(os.path.join(here, "src", "template.html"), encoding="utf-8").read()
co = io.open(os.path.join(here, "src", "co_data.js"), encoding="utf-8").read()
assert "/*@CO@*/" in tpl
out = tpl.replace("/*@CO@*/", co.strip())
for name in ("LEO.html", "index.html"):
    io.open(os.path.join(here, name), "w", encoding="utf-8", newline="\n").write(out)
print("built", len(out), "chars,", co.count("{c:"), "companies")
