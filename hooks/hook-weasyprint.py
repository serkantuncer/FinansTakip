from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# WeasyPrint'in tüm alt modüllerini topla
hiddenimports = collect_submodules('weasyprint')

# Cairo kütüphanelerini dahil et
hiddenimports.extend([
    'cairocffi._generated.ffi',
    'cairocffi._generated.lib',
    'cffi.backend_ctypes'
])

# CSS ve font dosyalarını dahil et
datas = collect_data_files('weasyprint', include_py_files=True)
datas.extend(collect_data_files('html5lib'))
datas.extend(collect_data_files('cssselect2'))