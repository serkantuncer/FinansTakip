from weasyprint import HTML

print("WeasyPrint modülü başarıyla yüklendi!")

# Basit bir HTML'den PDF üretmeyi deneyelim
html = HTML(string='<h1>Merhaba Dünya!</h1>')
html.write_pdf('test.pdf')

print("PDF başarıyla oluşturuldu: test.pdf")
