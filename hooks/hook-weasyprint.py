from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = []
for package_name in [
    "weasyprint",
    "tinycss2",
    "cssselect2",
    "pyphen",
    "fontTools",
    "pydyf",
    "tinyhtml5",
]:
    hiddenimports.extend(collect_submodules(package_name))

datas = []
for package_name in ["weasyprint", "tinycss2", "cssselect2", "pyphen", "fontTools"]:
    datas.extend(collect_data_files(package_name, include_py_files=True))
