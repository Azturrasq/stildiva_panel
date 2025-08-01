import webview
import subprocess
import threading
import time
import sys
import os

# PyInstaller'ın geçici dosya yolunu çözmek için yardımcı fonksiyon
def get_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Streamlit sunucusunu çalıştıracak ve log tutacak fonksiyon
def run_streamlit():
    app_path = get_path("app.py")
    log_path = os.path.join(os.path.expanduser("~"), "Desktop", "app_log.txt") # Log dosyasını Masaüstüne kaydet
    
    command = ["streamlit", "run", app_path, "--server.headless", "true", "--server.port", "8501"]
    
    # Hataları yakalamak için log dosyasını aç
    with open(log_path, "w") as log_file:
        # subprocess.run yerine Popen kullanarak işlemi başlat ve logları yönlendir
        process = subprocess.Popen(command, stdout=log_file, stderr=log_file, text=True)
        process.wait() # İşlem bitene kadar bekle

if __name__ == '__main__':
    # Streamlit'i başlat
    streamlit_thread = threading.Thread(target=run_streamlit)
    streamlit_thread.daemon = True
    streamlit_thread.start()

    # Sunucunun başlaması için kısa bir bekleme süresi
    time.sleep(5)

    # Streamlit sunucusuna bağlanan bir webview penceresi oluştur
    webview.create_window(
        "Stil Diva - Yönetim Paneli",
        "http://localhost:8501",
        width=1280,
        height=800,
        resizable=True
    )
    webview.start()