# FinansTakipSistemi main.py
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import socket
import threading
import webbrowser
import base64
import urllib.request
from io import BytesIO
import psutil
import signal
import platform

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox

from PIL import Image, ImageTk
# pystray'i güvenli şekilde import et
try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("📋 pystray mevcut değil, sistem tepsisi devre dışı")

from app import app  # Flask app

# ===========================
# GÖMÜLÜ BASE64 İKONLAR
# ===========================
ICON_BROWSER = """<BASE64_BROWSER_DATA>"""
ICON_INFO = """<BASE64_INFO_DATA>"""
ICON_EXIT = """<BASE64_EXIT_DATA>"""

# ===========================
# GLOBAL DEĞİŞKENLER
# ===========================
last_request_time = 0
recent_requests = 0

# ===========================
# AYAR DOSYASI
# ===========================
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".FinansTakipSistemi", "config.json")

# PyInstaller .app içinde unpack edilen klasör
bundle_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

# DYLD_LIBRARY_PATH ayarla (macOS için .dylib yükleme yolu)
os.environ['DYLD_LIBRARY_PATH'] = bundle_dir + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')

def load_config():
    default = {
        "preferred_port": None,
        "theme": "darkly",
        "open_browser_automatically": False,
        "enable_system_tray": True  # Sistem tepsisi açma/kapama seçeneği
    }
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(default, f, indent=4)
        return default
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

# ===========================
# PORT VE FLASK KONTROLLERİ
# ===========================

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def check_port_available(port):
    """Belirtilen port kullanılabilir mi kontrol et"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except socket.error:
            return False

def get_active_connections(port):
    """Port üzerindeki aktif bağlantı sayısını döndür"""
    try:
        connections = psutil.net_connections(kind='inet')
        active_count = 0
        for conn in connections:
            if conn.laddr.port == port and conn.status == 'ESTABLISHED':
                active_count += 1
        return active_count
    except:
        return 0

def check_server_accessible(port):
    """Sunucunun erişilebilir olup olmadığını kontrol et"""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
        return True
    except:
        return False

# ===========================
# FLASK SUNUCU YÖNETİMİ
# ===========================

flask_server = None
flask_thread = None

def run_flask(port):
    global flask_server
    try:
        # Werkzeug sunucusunu kontrol edebilmek için
        from werkzeug.serving import make_server
        flask_server = make_server('127.0.0.1', port, app)
        print(f"🚀 Flask sunucusu {port} portunda başlatıldı")
        flask_server.serve_forever()
    except Exception as e:
        print(f"❌ Flask başlatılamadı: {e}")

def stop_flask():
    global flask_server
    if flask_server:
        try:
            flask_server.shutdown()
            print("🛑 Flask sunucusu durduruldu")
        except Exception as e:
            print(f"⚠ Flask durdurma hatası: {e}")

def check_flask_ready(port, max_attempts=10):
    for _ in range(max_attempts):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
            return True
        except:
            time.sleep(0.5)
    return False

# ===========================
# GÖMÜLÜ İKON YÜKLEME
# ===========================

def load_icon(base64_string):
    try:
        if not base64_string or base64_string.startswith("<BASE64_"):
            # Eğer base64 verisi yoksa, basit bir fallback ikon oluştur
            return create_fallback_icon()
        return Image.open(BytesIO(base64.b64decode(base64_string)))
    except Exception as e:
        print(f"İkon yükleme hatası: {e}")
        return create_fallback_icon()

def create_fallback_icon():
    """Base64 verisi olmadığında kullanılacak basit ikon"""
    try:
        # 16x16 basit beyaz kare ikon
        img = Image.new('RGBA', (16, 16), (255, 255, 255, 255))
        return img
    except:
        return None

# ===========================
# PLATFORM UYUMLULUK
# ===========================

def is_macos():
    """macOS kontrolü"""
    return platform.system() == 'Darwin'

def is_windows():
    """Windows kontrolü"""
    return platform.system() == 'Windows'

def is_linux():
    """Linux kontrolü"""
    return platform.system() == 'Linux'

# ===========================
# GUI VE TRAY - KOMPAKT VERSİYON
# ===========================

def run_gui(port, config):
    theme = config.get("theme", "darkly")
    app_win = ttk.Window(title="Finans Takip Sistemi", themename=theme, size=(420, 250))

    # Uygulama pencere ikonunu platforma göre ayarla.
    # EXE dosya ikonu spec ile gömülür, fakat pencere ikonu ayrıca set edilmelidir.
    try:
        if is_windows():
            ico_path = os.path.join(bundle_dir, "icon.ico")
            png_path = os.path.join(bundle_dir, "icon.png")
            if os.path.exists(ico_path):
                app_win.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                app_icon = tk.PhotoImage(file=png_path)
                app_win.iconphoto(True, app_icon)
                app_win._app_icon_ref = app_icon  # GC koruması
        elif is_linux():
            png_path = os.path.join(bundle_dir, "icon.png")
            if os.path.exists(png_path):
                app_icon = tk.PhotoImage(file=png_path)
                app_win.iconphoto(True, app_icon)
                app_win._app_icon_ref = app_icon  # GC koruması
    except Exception as e:
        print(f"⚠️ Pencere ikonu ayarlanamadı: {e}")
    
    if is_macos():
        try:
            import ctypes
            from AppKit import NSApplication, NSImage
            from Foundation import NSURL

            icns_path = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', 'Resources', 'icon.icns'))
            if os.path.exists(icns_path):
                icon = NSImage.alloc().initByReferencingFile_(icns_path)
                if icon:
                    NSApplication.sharedApplication().setApplicationIconImage_(icon)
                    print("🍎 Dock ikonu zorla yeniden ayarlandı (icon.icns)")
        except Exception as e:
            print(f"⚠️ macOS Dock ikon override hatası: {e}")

    app_win.resizable(False, False)

    # Global değişken tanımla
    global tray_icon
    tray_icon = None

    # İkonları yükle
    browser_icon = None
    info_icon = None
    exit_icon = None
    
    try:
        if ICON_BROWSER and not ICON_BROWSER.startswith("<BASE64_"):
            browser_img = load_icon(ICON_BROWSER)
            if browser_img:
                browser_icon = ImageTk.PhotoImage(browser_img.resize((16, 16)))
        
        if ICON_INFO and not ICON_INFO.startswith("<BASE64_"):
            info_img = load_icon(ICON_INFO)
            if info_img:
                info_icon = ImageTk.PhotoImage(info_img.resize((16, 16)))
        
        if ICON_EXIT and not ICON_EXIT.startswith("<BASE64_"):
            exit_img = load_icon(ICON_EXIT)
            if exit_img:
                exit_icon = ImageTk.PhotoImage(exit_img.resize((16, 16)))
    except Exception as e:
        print(f"⚠ Button ikonları yüklenemedi: {e}")

    def safe_exit():
        """Güvenli çıkış - Flask sunucusunu da durdur"""
        print("🔄 Güvenli çıkış işlemi başlatılıyor...")
        
        # Tray icon'u durdur
        if tray_icon:
            try:
                tray_icon.stop()
            except:
                pass
        
        # Flask sunucusunu durdur
        stop_flask()
        
        # GUI'yi kapat
        try:
            app_win.destroy()
        except:
            pass
        
        print("✅ Uygulama güvenli şekilde kapatıldı")
        os._exit(0)

    def on_close():
        """X butonuna basıldığında davranış"""
        if is_macos():
            # macOS'ta sistem tepsisi yok, minimize et
            print("🍎 Pencere minimize ediliyor (Dock'tan tekrar açabilirsiniz)")
            app_win.iconify()  # Minimize et, tamamen gizleme
        elif tray_icon and config.get("enable_system_tray", True):
            print("🔽 Pencere gizleniyor (sistem tepsisinden çıkış yapabilirsiniz)")
            app_win.withdraw()
        else:
            print("❌ Sistem tepsisi yok, uygulama kapatılıyor")
            safe_exit()

    def on_minimize():
        """Minimize'a basıldığında davranış"""
        # Minimize her platformda normal davranmalı (taskbar/dock).
        # Sadece X kapanışında tepsiye gizleme yapılır.
        return

    app_win.protocol("WM_DELETE_WINDOW", on_close)
    
    # Sistem tepsisine minimize için
    app_win.bind('<Unmap>', lambda e: on_minimize() if app_win.state() == 'iconic' else None)

    # BAŞLIK - Kompakt
    ttk.Label(app_win, text="Finans Takip Sistemi", font=("Segoe UI", 14, "bold"), bootstyle="info").pack(pady=(15, 5))
    ttk.Label(app_win, text=f"Port: {port} • http://127.0.0.1:{port}", bootstyle="secondary").pack(pady=(0, 8))

    status_label = ttk.Label(app_win, text="Hazır", bootstyle="success")
    status_label.pack(pady=3)

    # BAĞLANTI DURUMU - Tek satır
    connection_label = ttk.Label(app_win, text="Bekleniyor", bootstyle="info")
    connection_label.pack(pady=3)

    def update_connection_status():
        """Bağlantı durumunu güncelle"""
        try:
            # Sunucunun çalışıp çalışmadığını kontrol et
            if check_server_accessible(port):
                connection_label.config(text="✅ Sunucu Aktif", bootstyle="success")
            else:
                connection_label.config(text="❌ Sunucu Erişilemez", bootstyle="danger")
        except:
            connection_label.config(text="⚠️ Durum Bilinmiyor", bootstyle="warning")
        
        # Her 5 saniyede bir güncelle
        app_win.after(5000, update_connection_status)

    # İlk güncellemeyi başlat
    app_win.after(2000, update_connection_status)

    # BUTONLAR - 2 sıra halinde
    btn_frame1 = ttk.Frame(app_win)
    btn_frame1.pack(pady=8)
    
    btn_frame2 = ttk.Frame(app_win)
    btn_frame2.pack(pady=5)

    def open_browser():
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
            status_label.config(text="🌐 Tarayıcı açıldı", bootstyle="success")
            # 3 saniye sonra status'u resetle
            app_win.after(3000, lambda: status_label.config(text="Hazır", bootstyle="success"))
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            status_label.config(text="❌ Tarayıcı açılamadı", bootstyle="danger")

    def show_info():
        port_status = "✅ Kullanılabilir" if check_port_available(port) else "❌ Kullanımda"
        server_status = "✅ Erişilebilir" if check_server_accessible(port) else "❌ Erişilemez"
        platform_info = f"{platform.system()} {platform.release()}"
        tray_status = "✅ Aktif" if tray_icon else "❌ Devre dışı"
        
        # F-string içinde backslash kullanmamak için string'i böl
        close_behavior = "Minimize edilir (Dock)" if is_macos() else "Sistem tepsisine gizlenir" if tray_icon else "Tamamen çıkar"
        
        if is_macos():
            tray_info = "📌 Sistem Tepsisi:" + "\n" + "macOS'ta sistem tepsisi desteklenmez"
        else:
            tray_info = "📌 Sistem Tepsisi:" + "\n" + "Config dosyasında 'enable_system_tray': false ile kapatabilirsiniz."
        
        config_path = os.path.dirname(CONFIG_PATH)
        
        info_text = f"""Finans Takip Sistemi

    Platform: {platform_info}
    Sistem Tepsisi: {tray_status}

    Sunucu Durumu:
    • Port: {port} ({port_status})
    • Erişim: {server_status}

    Verileriniz şurada saklanır:
    {config_path}

    📌 Güvenlik Bilgileri:
    • Pencere kapatıldığında: {close_behavior}
    • Tamamen çıkmak için: "Çıkış" butonunu kullanın
    • Çıkış yapıldığında Flask sunucusu da KAPANIR

    📌 Tarayıcı Rehberi:
    • Tarayıcı sekmesi kapatılsa bile sunucu çalışır
    • Sunucuyu durdurmak için uygulamadan çıkın

    📌 Ayarlar:
    Config dosyasında port ve tema ayarlayabilirsiniz.

    {tray_info}

    Sürüm: Deluxe Kompakt v.1.1.0
    Geliştirici: Serkan TUNCER"""

        messagebox.showinfo("Hakkında", info_text)

    def full_exit():
        safe_exit()

    def open_config_file():
        try:
            if is_windows():
                os.startfile(CONFIG_PATH)
            elif is_macos():
                os.system(f"open '{CONFIG_PATH}'")
            else:  # Linux
                os.system(f"xdg-open '{CONFIG_PATH}'")
        except Exception as e:
            messagebox.showerror("Açma Hatası", f"config.json açılamadı:\n{e}")

    # Üst sıra butonlar
    ttk.Button(btn_frame1, 
              text="🌐 Tarayıcıda Aç" if not browser_icon else "Tarayıcıda Aç", 
              image=browser_icon if browser_icon else None,
              compound="left",
              command=open_browser, 
              bootstyle="primary", 
              width=18).pack(side=LEFT, padx=3)
    
    ttk.Button(btn_frame1, 
              text="ℹ️ Bilgi" if not info_icon else "Bilgi", 
              image=info_icon if info_icon else None,
              compound="left",
              command=show_info, 
              bootstyle="secondary", 
              width=18).pack(side=LEFT, padx=3)

    # Alt sıra butonlar
    ttk.Button(btn_frame2, 
              text="⚙️ Ayarlar", 
              command=open_config_file, 
              bootstyle="warning", 
              width=18).pack(side=LEFT, padx=3)
    
    ttk.Button(btn_frame2, 
              text="❌ Çıkış" if not exit_icon else "Çıkış", 
              image=exit_icon if exit_icon else None,
              compound="left",
              command=full_exit, 
              bootstyle="danger", 
              width=18).pack(side=LEFT, padx=3)

    # İkon referanslarını sakla (garbage collection'dan korunmak için)
    if browser_icon:
        app_win.browser_icon = browser_icon
    if info_icon:
        app_win.info_icon = info_icon  
    if exit_icon:
        app_win.exit_icon = exit_icon

    # macOS için pencereyi tekrar gösterme desteği
    def handle_focus_in(event=None):
        """Uygulamaya fokus geldiğinde pencereyi göster"""
        if not app_win.winfo_viewable():
            app_win.deiconify()
            app_win.lift()
            print("👁 Pencere tekrar gösterildi")

    def show_window_shortcut(event=None):
        """Klavye kısayolu ile pencereyi göster"""
        app_win.deiconify()
        app_win.lift()
        app_win.focus_force()
        print("⌨️ Klavye kısayolu ile pencere gösterildi")

    # macOS'ta Dock'tan tıklanma yakalama
    if is_macos():
        app_win.bind('<FocusIn>', handle_focus_in)
        # Uygulama etkinleştirildiğinde pencereyi göster
        app_win.bind('<Activate>', handle_focus_in)
        # Cmd+Shift+W ile pencereyi göster
        app_win.bind('<Command-Shift-W>', show_window_shortcut)
        print("💡 Pencere minimize edildiğinde: Dock'tan uygulamaya tıklayın veya Cmd+Shift+W tuşlayın")
    else:
        # Windows/Linux için Alt+Shift+W
        app_win.bind('<Alt-Shift-W>', show_window_shortcut)
        print("💡 Pencere gizlendiğinde: Alt+Shift+W tuşlayın veya sistem tepsisini kullanın")

    # TRAY İKONU KURULUMU - macOS uyumlu
    def setup_tray():
        """Sistem tepsisi kurulumu - macOS uyumlu"""
        global tray_icon
        
        # macOS'ta sistem tepsisini devre dışı bırak (pystray uyumsuzluğu)
        if is_macos():
            print("🍎 macOS'ta sistem tepsisi devre dışı (pystray uyumsuzluğu)")
            print("💡 Pencereyi gizlemek için minimize kullanın, Dock'tan geri açabilirsiniz")
            tray_icon = None
            return
        
        # pystray mevcut değilse sistem tepsisini devre dışı bırak
        if not PYSTRAY_AVAILABLE:
            print("📋 pystray kütüphanesi mevcut değil, sistem tepsisi devre dışı")
            tray_icon = None
            return
        
        # Sistem tepsisi devre dışı bırakılmışsa atla
        if not config.get("enable_system_tray", True):
            print("📋 Sistem tepsisi yapılandırmada devre dışı bırakıldı")
            tray_icon = None
            return
        
        # Sadece Windows ve Linux için sistem tepsisi
        try:
            icon_data = load_icon(ICON_BROWSER)
            if icon_data:
                def show_window():
                    app_win.after(0, lambda: app_win.deiconify())
                
                def exit_app():
                    app_win.after(0, safe_exit)
                
                tray_icon = pystray.Icon(
                    "Finans Takip Sistemi", 
                    icon=icon_data,
                    menu=pystray.Menu(
                        pystray.MenuItem("Göster", show_window),
                        pystray.MenuItem("Çıkış", exit_app)
                    )
                )
                
                threading.Thread(target=tray_icon.run, daemon=True).start()
                print("🖥 Sistem tepsisi başlatıldı (Windows/Linux)")
            else:
                print("⚠ Tray ikonu yüklenemedi")
                tray_icon = None
        except Exception as e:
            print(f"⚠ Tray kurulum hatası: {e}")
            tray_icon = None

    # Tray kurulumunu GUI başlatıldıktan sonra yap
    app_win.after(1000, setup_tray)
    
    # GUI'yi başlat
    app_win.mainloop()

# ===========================
# ANA ÇALIŞTIRICI
# ===========================

if __name__ == "__main__":
    # Ctrl+C yakalamak için signal handler
    def signal_handler(sig, frame):
        print("\n🛑 Ctrl+C algılandı, güvenli çıkış yapılıyor...")
        stop_flask()
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        config = load_config()
        
        # Platform bilgisini yazdır
        print(f"🖥 Platform: {platform.system()} {platform.release()}")
        if is_macos():
            print("🍎 macOS uyumluluk modu aktif")
        
        # Port belirleme mantığı
        preferred_port = config.get("preferred_port")
        if preferred_port:
            if check_port_available(preferred_port):
                port = preferred_port
                print(f"✅ Tercih edilen port {preferred_port} kullanılıyor")
            else:
                port = find_free_port()
                print(f"⚠ Tercih edilen port {preferred_port} meşgul, {port} portu kullanılıyor")
        else:
            port = find_free_port()
            print(f"🔍 Otomatik port bulundu: {port}")

        print(f"🚀 Sunucu başlatılıyor - Port: {port}")
        flask_thread = threading.Thread(target=run_flask, args=(port,), daemon=False)
        flask_thread.start()

        check_result = check_flask_ready(port)
        if check_result:
            print("✅ Flask sunucusu hazır")
            if config.get("open_browser_automatically", True):
                webbrowser.open(f"http://127.0.0.1:{port}")
                print("🌐 Tarayıcı açıldı")
        else:
            print("❌ Flask sunucusu başlatılamadı")

        run_gui(port, config)

    except Exception as e:
        error_msg = f"Uygulama başlatılamadı: {e}"
        print(error_msg)
        stop_flask()  # Hata durumunda da Flask'ı durdur
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Kritik Hata", error_msg)
        except:
            pass
        sys.exit(1)
