# 1. Temel imaj olarak Python'un hafif bir sürümünü kullan
FROM python:3.11-slim

# 2. Konteyner içinde çalışacağımız bir klasör oluştur
WORKDIR /app

# 3. Önce gereksinimler dosyasını kopyala ve kur. 
# Bu, kod değiştiğinde paketlerin tekrar tekrar kurulmasını engeller (Docker cache).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Proje dosyalarının geri kalanını konteyner içine kopyala
COPY . .

# 5. Streamlit uygulamasının çalışacağı portu dışarıya aç
EXPOSE 8501

# 6. Konteyner çalıştığında uygulamayı başlatacak komut
# --server.address=0.0.0.0 parametresi, konteynerin dışından gelen bağlantıları kabul etmesini sağlar.
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]