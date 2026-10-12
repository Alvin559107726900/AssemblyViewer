#!/usr/bin/env python3
"""把 STL 資料夾 + parts.csv 合成單一 HTML 檢視器。

用法:  python build.py projects/RockyRoller
只用 Python 標準函式庫,不需安裝套件。
"""
import base64, csv, io, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
REQUIRED = ["step", "stl_file", "part_name"]
OPTIONAL = ["pn", "qty", "explode_dir", "explode_dist", "delay", "tool", "torque", "note", "color"]
VALID_DIR = {"", "x", "y", "z", "-x", "-y", "-z"}
# 依序嘗試的編碼:UTF-8 優先,cp950/big5 是 Excel 在繁體中文 Windows 上
# 存「CSV(逗號分隔)」時常用的編碼,即使沒有選 UTF-8 也能正確讀取。
CSV_ENCODINGS = ["utf-8-sig", "cp950", "big5", "utf-16"]

# 顏色名稱對照表(parts.csv 的 color 欄直接填名稱即可,中英文皆可)
COLOR_NAMES = {
    "紅": "#d94f3d", "red": "#d94f3d",
    "橘": "#f08a24", "橙": "#f08a24", "orange": "#f08a24",
    "黃": "#f2c94c", "yellow": "#f2c94c",
    "綠": "#4caf78", "green": "#4caf78",
    "青": "#2ab3b3", "cyan": "#2ab3b3",
    "藍": "#3f7fd9", "blue": "#3f7fd9",
    "淺藍": "#7fb6f0", "lightblue": "#7fb6f0",
    "藍灰": "#8fa8c8", "bluegray": "#8fa8c8",
    "紫": "#9b6bd6", "purple": "#9b6bd6",
    "粉紅": "#f08fb0", "pink": "#f08fb0",
    "棕": "#8b5a2b", "咖啡": "#8b5a2b", "brown": "#8b5a2b",
    "金": "#d4af37", "gold": "#d4af37",
    "銀": "#d0d4da", "silver": "#d0d4da",
    "白": "#f4f4f4", "white": "#f4f4f4",
    "淺灰": "#b5bac2", "lightgray": "#b5bac2",
    "灰": "#8a9099", "gray": "#8a9099", "grey": "#8a9099",
    "深灰": "#5b6470", "darkgray": "#5b6470",
    "黑": "#25282d", "black": "#25282d",
}


def resolve_color(value, line):
    key = value.strip().replace("色", "").replace(" ", "").lower()
    if key in COLOR_NAMES:
        return COLOR_NAMES[key]
    if re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", key):  # 仍相容色碼
        return key
    names = "、".join(k for k in COLOR_NAMES if not k.isascii())
    fail(f"parts.csv 第 {line} 列:不認得顏色「{value}」。可用的名稱:{names}(或英文 red、blue 等)")


def fail(msg):
    sys.exit(f"[錯誤] {msg}")


def read_csv_text(path):
    raw = path.read_bytes()
    for enc in CSV_ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    fail(
        f"{path} 的編碼無法辨識(試過 {', '.join(CSV_ENCODINGS)} 都失敗)。\n"
        f"請在 Excel 用「另存新檔」,格式選「CSV UTF-8(逗號分隔)」再存一次。"
    )


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx_table(path):
    """只用標準函式庫讀 .xlsx 第一個工作表,回傳「列的清單」(每列是字串清單)。"""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid = wb.find("m:sheets", NS)[0].get(f"{{{NS['r']}}}id")
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = target.lstrip("/")
        sheet_path = target if target.startswith("xl/") else "xl/" + target
        sheet = ET.fromstring(z.read(sheet_path))
    rows = []
    for row in sheet.find("m:sheetData", NS).findall("m:row", NS):
        rn = int(row.get("r"))
        while len(rows) < rn - 1:
            rows.append([])
        cells = []
        for c in row.findall("m:c", NS):
            idx = _col_index(c.get("r"))
            while len(cells) <= idx:
                cells.append("")
            t, v = c.get("t"), c.find("m:v", NS)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
            elif v is None:
                val = ""
            elif t in ("str", "e"):
                val = v.text or ""
            elif t == "b":
                val = "TRUE" if v.text == "1" else "FALSE"
            else:  # 數字:整數不要顯示成 1.0
                try:
                    f = float(v.text)
                    val = str(int(f)) if f == int(f) else v.text
                except ValueError:
                    val = v.text or ""
            cells[idx] = val
        rows.append(cells)
    return rows


def load_rows(root):
    xlsx, csv_path = root / "parts.xlsx", root / "parts.csv"
    if xlsx.exists():
        print(f"[使用] {xlsx.name}" + ("(同資料夾的 parts.csv 已忽略)" if csv_path.exists() else ""))
        table = read_xlsx_table(xlsx)
        if not table or not any(table[0]):
            fail(f"{xlsx} 第 1 列必須是欄位名稱")
        names = [h.strip() for h in table[0]]
        records = [dict(zip(names, row + [""] * (len(names) - len(row)))) for row in table[1:]]
        fieldnames = names
    elif csv_path.exists():
        print(f"[使用] {csv_path.name}")
        reader = csv.DictReader(io.StringIO(read_csv_text(csv_path)))
        fieldnames = reader.fieldnames or []
        records = list(reader)
    else:
        fail(f"找不到 {xlsx} 或 {csv_path}")
    missing = [c for c in REQUIRED if c not in fieldnames]
    if missing:
        fail(f"parts 表格缺少必填欄位:{', '.join(missing)}")
    rows = []
    for i, r in enumerate(records, start=2):
        r = {k: (v or "").strip() for k, v in r.items() if k}
        if not r["stl_file"]:
            continue
        if not r["step"].isdigit():
            fail(f"parts 表格第 {i} 列:step 必須是整數,目前是「{r['step']}」")
        if r.get("explode_dir", "").lower() not in VALID_DIR:
            fail(f"parts 表格第 {i} 列:explode_dir 只能是 x/y/z/-x/-y/-z 或留空")
        if r.get("color", ""):
            r["color"] = resolve_color(r["color"], i)
        r["step"] = int(r["step"])
        r.setdefault("pn", "")
        if not r["pn"]:
            r["pn"] = Path(r["stl_file"]).stem
        for c in OPTIONAL:
            r.setdefault(c, "")
        r["_line"] = i
        rows.append(r)
    if not rows:
        fail("parts 表格沒有任何零件資料")
    return sorted(rows, key=lambda r: r["step"])


def build(project_dir):
    root = Path(project_dir)
    cfg_path = root / "project.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    rows = load_rows(root)

    stl_dir = root / "stl"
    listed = {r["stl_file"] for r in rows}
    for r in rows:
        if not (stl_dir / r["stl_file"]).exists():
            fail(f"parts.csv 第 {r['_line']} 列:stl/ 裡找不到 {r['stl_file']}")
    for extra in sorted(p.name for p in stl_dir.glob("*.stl") if p.name not in listed):
        print(f"[提醒] {extra} 在 stl/ 裡,但沒有列進 parts.csv")

    meshes = {
        name: base64.b64encode((stl_dir / name).read_bytes()).decode("ascii")
        for name in sorted(listed)
    }
    for r in rows:
        r.pop("_line", None)

    data = {
        "project": {
            "name": cfg.get("project_name", root.name),
            "confidential": cfg.get("confidential", ""),
            "unit": cfg.get("unit", "mm"),
            "up_axis": cfg.get("up_axis", "Z"),
            "version": cfg.get("version", ""),
            "built": date.today().isoformat(),
        },
        "parts": rows,
        "meshes": meshes,
    }
    payload = json.dumps(data, ensure_ascii=False)
    # U+2028/U+2029 是合法的 JSON 字元,但直接塞進 <script> 會被當成換行,
    # 讓整段 JS 語法錯誤(常見來源:從 Word/PDF 複製貼上的文字暗藏這兩個字元)。
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    payload = payload.replace("</", "<\\/")

    template = (HERE / "template.html").read_text(encoding="utf-8")
    if "/*__DATA__*/" not in template:
        fail("template.html 裡找不到 /*__DATA__*/ 佔位符")
    if "<!--__VENDOR__-->" not in template:
        fail("template.html 裡找不到 <!--__VENDOR__--> 佔位符")

    vendor_path = HERE / "vendor" / "three.min.js"
    if not vendor_path.exists():
        fail(f"找不到 {vendor_path}(three.js 函式庫,只需準備一次,所有專案共用)")
    vendor_js = vendor_path.read_text(encoding="utf-8").replace("</script", "<\\/script")

    html = template.replace("<!--__VENDOR__-->", f"<script>{vendor_js}</script>")
    html = html.replace("/*__DATA__*/", f"const DATA = {payload};")

    # 輸出檔名一律由資料夾名稱決定,避免複製專案後忘了改 project.json
    out_name = f"{root.name}_viewer.html"
    if cfg.get("output") and cfg["output"] != out_name:
        print(f"[提醒] project.json 的 output「{cfg['output']}」已忽略,改用 {out_name}")
    pn = cfg.get("project_name", "")
    if pn and pn.replace(" ", "").lower() != root.name.lower():
        print(f"[提醒] project_name「{pn}」與資料夾名稱 {root.name} 不同,請確認顯示名稱是否正確")
    out = root / out_name
    out.write_text(html, encoding="utf-8")
    print(f"[完成] {out}  ({len(rows)} 個零件,{out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("用法: python build.py <專案資料夾>")
    build(sys.argv[1])
