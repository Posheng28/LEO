# 組出網頁：src/template.html ＋ src/co_data.js ＋ src/co_viz.js ＋ src/ft_data.js ＋ src/viz_card.js／viz_card.css → LEO.html、index.html（兩份內容相同）
# 用法：python -X utf8 build.py
import io, os

here = os.path.dirname(os.path.abspath(__file__))
rd = lambda *p: io.open(os.path.join(here, *p), encoding="utf-8").read()
out = rd("src", "template.html")
for mark, name in (("/*@CO@*/", "co_data.js"), ("/*@CV@*/", "co_viz.js"), ("/*@VZJS@*/", "viz_card.js"), ("/*@VZCSS@*/", "viz_card.css"), ("/*@FT@*/", "ft_data.js")):
    assert mark in out, mark
    out = out.replace(mark, rd("src", name).strip())
for name in ("LEO.html", "index.html"):
    io.open(os.path.join(here, name), "w", encoding="utf-8", newline="\n").write(out)
print("built", len(out), "chars")
