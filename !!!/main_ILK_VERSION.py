import threading
import socket
import webbrowser
import tkinter as tk
from tkinter import messagebox
import sys
import os
import time
from app import app

def find_free_port():
    """Sistemde boşta olan bir port bulur."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def run_flask(port):
    """Flask uygulamasını belirlenen portta başlatır."""
    try:
        # Flask app'i import et
        from app import app
        print(f"Flask sunucusu port {port} üzerinde başlatılıyor...")
        # debug ve reloader kapalı olmalı pyinstaller için
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
    except ImportError as e:
        print(f"Flask app import edilemedi: {e}")
    except Exception as e:
        print(f"Flask başlatılamadı: {e}")

def run_gui(port):
    """Tkinter GUI oluşturur, port bilgisini gösterir ve tarayıcı açma butonu koyar."""
    root = tk.Tk()
    root.title("Financial Portal")
    root.geometry("450x250")
    root.resizable(False, False)
    
    # Ana çerçeve
    main_frame = tk.Frame(root, padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Başlık
    title_label = tk.Label(main_frame, text="Financial Portal", 
                          font=("Arial", 16, "bold"), fg="#2c3e50")
    title_label.pack(pady=(0, 15))
    
    # Port bilgisi
    port_label = tk.Label(main_frame, text=f"Sunucu port {port} üzerinde çalışıyor", 
                         font=("Arial", 11), fg="#34495e")
    port_label.pack(pady=5)
    
    # URL bilgisi
    url_label = tk.Label(main_frame, text=f"http://127.0.0.1:{port}", 
                        font=("Arial", 10), fg="#7f8c8d")
    url_label.pack(pady=5)

    def open_browser():
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
            status_label.config(text="Tarayıcı açıldı", fg="green")
        except Exception as e:
            messagebox.showerror("Hata", f"Tarayıcı açılamadı: {e}")
            status_label.config(text="Tarayıcı açılamadı", fg="red")

    def on_app_closing():
        """Uygulama kapatılırken temizlik işlemleri."""
        try:
            root.destroy()
        except:
            pass
        finally:
            # Tüm thread'leri ve process'i sonlandır
            os._exit(0)

    def show_info():
        """Uygulama hakkında bilgi göster."""
        info_text = """Financial Portal

Verileriniz güvenli bir şekilde aşağıdaki konumda saklanır:
{}

Bu konum sayesinde:
• Verileriniz uygulama güncellemelerinde korunur  
• Farklı kullanıcı hesaplarında ayrı veriler tutulur
• Manuel yedekleme yapabilirsiniz

Geliştirici: Serkan TUNCER
Sürüm: 1.2""".format(os.path.join(os.path.expanduser("~"), ".financial_portal"))
        
        messagebox.showinfo("Hakkında", info_text)

    # Butonlar çerçevesi
    button_frame = tk.Frame(main_frame)
    button_frame.pack(pady=20)
    
    # Ana butonlar
    btn_open = tk.Button(button_frame, text="🌐 Tarayıcıda Aç", 
                        command=open_browser, 
                        width=15, height=2,
                        bg="#3498db", fg="#333333",
                        font=("Arial", 10, "bold"),
                        relief="flat")
    btn_open.pack(side=tk.LEFT, padx=5)

    btn_info = tk.Button(button_frame, text="ℹ️ Bilgi", 
                        command=show_info,
                        width=8, height=2,
                        bg="#95a5a6", fg="#333333",
                        font=("Arial", 10),
                        relief="flat")
    btn_info.pack(side=tk.LEFT, padx=5)

    btn_quit = tk.Button(button_frame, text="❌ Çıkış", 
                        command=on_app_closing,
                        width=8, height=2,
                        bg="#e74c3c", fg="#333333",
                        font=("Arial", 10, "bold"),
                        relief="flat")
    btn_quit.pack(side=tk.RIGHT, padx=5)
    
    # Durum çubuğu
    status_frame = tk.Frame(main_frame)
    status_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))
    
    status_label = tk.Label(status_frame, text="Hazır - Tarayıcı açmak için butona tıklayın", 
                           font=("Arial", 9), fg="#27ae60",
                           anchor="w")
    status_label.pack(fill=tk.X)

    # Pencere kapatma olayını yakala
    root.protocol("WM_DELETE_WINDOW", on_app_closing)
    
    # Merkeze yerleştir
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

def check_flask_ready(port, max_attempts=10):
    """Flask sunucusunun hazır olup olmadığını kontrol eder."""
    import urllib.request
    import urllib.error
    
    for attempt in range(max_attempts):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
            return True
        except:
            time.sleep(0.5)
    return False

if __name__ == "__main__":
    try:
        print("Financial Portal Uygulaması başlatılıyor...")
        
        # Boş port bul
        port = find_free_port()
        print(f"Kullanılacak port: {port}")

        # Flask'ı ayrı threadde başlat
        flask_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
        flask_thread.start()
        
        # Flask'ın hazır olmasını bekle
        print("Flask sunucusu başlatılıyor...")
        if check_flask_ready(port):
            print("Flask sunucusu hazır!")
        else:
            print("Flask sunucusu başlatılamadı, ancak GUI açılacak...")

        # GUI'yi başlat
        print("GUI açılıyor...")
        run_gui(port)
        
    except Exception as e:
        error_msg = f"Uygulama başlatılamadı: {e}"
        print(error_msg)
        try:
            root = tk.Tk()
            root.withdraw()  # Ana pencereyi gizle
            messagebox.showerror("Kritik Hata", error_msg)
        except:
            pass
        sys.exit(1)