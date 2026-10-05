"""Package explicit demo assets; never archive user databases or uploaded files."""
import hashlib
import json
from pathlib import Path
import zipfile
import shutil
import sys


def prepare_runtime(root):
    if sys.version_info[:2] != (3,12):raise RuntimeError("The offline Windows package requires Python 3.12")
    source=Path(sys.base_prefix)
    destination=root/"storage/packaging/python"
    destination.mkdir(parents=True,exist_ok=True)
    for folder in ("Lib","DLLs"):
        shutil.copytree(source/folder,destination/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns("site-packages","__pycache__","*.pyc"))
    for name in ("python.exe","pythonw.exe","python3.dll","python312.dll","vcruntime140.dll","vcruntime140_1.dll","LICENSE.txt"):
        shutil.copy2(source/name,destination/name)


def main():
    root=Path(__file__).resolve().parents[2]
    prepare_runtime(root)
    directories=("backend/app","backend/migrations","backend/tests","frontend/dist","frontend/src","storage/packaging/wheels","storage/packaging/python","storage/gold","storage/benchmark","storage/validation","docs")
    names=("Start-Demo.ps1","Prepare-Offline.ps1","README.md","backend/requirements.offline-lock.txt","backend/requirements.txt","backend/pyproject.toml","frontend/package.json","frontend/package-lock.json","frontend/index.html","frontend/tsconfig.json","frontend/tsconfig.app.json","frontend/tsconfig.node.json","frontend/vite.config.ts")
    paths=[root/name for name in names]
    paths.extend(p for name in directories for p in (root/name).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".log"})
    if any(not p.exists() for p in paths):raise RuntimeError("A required demo artifact is missing")
    manifest={"version":"nwis-offline-package/1.0","platform":"Windows x64; bundled Python 3.12 runtime","storage":"Demo seeds a separate local database; no user database or uploaded documents included", "files":[{"path":p.relative_to(root).as_posix(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size} for p in sorted(set(paths))]}
    destination=root/"storage/packaging/NWIS-offline-demo.zip"
    with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        archive.writestr("package-manifest.json",json.dumps(manifest,indent=2))
        for p in sorted(set(paths)):archive.write(p,p.relative_to(root).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip():raise RuntimeError("Package integrity check failed")
    print(json.dumps({"archive":str(destination),"files":len(set(paths)),"bytes":destination.stat().st_size,"sha256":hashlib.sha256(destination.read_bytes()).hexdigest()}))


if __name__ == "__main__":main()
