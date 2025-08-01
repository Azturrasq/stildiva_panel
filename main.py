import webview
import subprocess
import threading
import time
import sys
import os

# PyInstaller'ın geçici dosya yolunu çözmek için yardımcı fonksiyon
def get_path(relative_path):
    try:
        # PyInstaller geçici bir _MEIPASS klasörü oluşturur
        base_path = sys._MEIPASS
    except Exception:
        # Normal Python ile çalıştırılıyorsa
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Streamlit sunucusunu ayrı bir iş parçacığında (thread) çalıştıracak fonksiyon
def run_streamlit():
    # PyInstaller ile paketlendiğinde app.py'nin yolunu doğru bulmalıyız
    app_path = get_path("app.py")
    
    # Streamlit'i "headless" modda çalıştır, böylece kendi tarayıcı penceresini açmaz
    command = ["streamlit", "run", app_path, "--server.headless", "true", "--server.port", "8501"]
    subprocess.run(command)

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