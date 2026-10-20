#!/usr/bin/env python3
"""部署用:替每個專案產生成品,並複製到 public/<網址名稱>/index.html"""
import shutil
from pathlib import Path
import build

HERE = Path(__file__).resolve().parent
# 資料夾名稱: 網址名稱
PROJECTS = {
    "RockyRoller": "rocky",
    "CaramelMotor": "caramel",
}

for name, slug in PROJECTS.items():
    proj = HERE / "projects" / name
    build.build(proj)
    src = proj / f"{name}_viewer.html"
    dst = HERE / "public" / slug / "index.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"[發佈] {dst}")
