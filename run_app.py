import streamlit.web.cli as stcli
import os
import sys
import threading
import time
import webview

# Streamlit sunucusunu çalıştıracak fonksiyon
def run_streamlit():
    if hasattr(sys, '_MEIPASS'):
        app_path = os.path.join(sys._MEIPASS, 'app.py')
    else:
        app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    
    # Streamlit'i BAŞSIZ modda çalıştır (tarayıcı açmaz) ve portu sabitle
    sys.argv = [
        "streamlit", 
        "run", 
        app_path, 
        "--server.port=8501",
        "--server.headless=true" 
    ]
    sys.exit(stcli.main())

if __name__ == '__main__':
    # 1. Streamlit sunucusunu arka planda bir thread olarak başlat
    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()

    # 2. Sunucunun kendine gelmesi için birkaç saniye bekle
    time.sleep(5)

    # 3. Sunucuyu gösteren bir uygulama penceresi oluştur ve göster
    webview.create_window(
        'Karlılık Paneli', 
        'http://localhost:8501',
        width=1280,
        height=800,
        resizable=True
    )
    webview.start()