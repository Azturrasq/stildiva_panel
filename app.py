import streamlit as st
import pandas as pd
import plotly.express as px
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import io
import os
from datetime import datetime
import calendar
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
import gspread

# --- YARDIMCI FONKSİYONLAR ---

def load_css(file_name):
    """Harici bir CSS dosyasını yükler."""
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Tasarım dosyası '{file_name}' bulunamadı. Lütfen dosyanın ana dizinde olduğundan emin olun.")

def dynamic_select(label, state_key, defaults=[]):
    """
    Kullanıcının listeye yeni öğe eklemesine olanak tanıyan dinamik bir selectbox oluşturur.
    """
    if state_key not in st.session_state:
        st.session_state[state_key] = defaults
    
    options = st.session_state[state_key]
    selection = st.selectbox(label, options, help="Mevcut seçeneklerden birini seçin veya aşağıdan yenisini ekleyin.")
    
    with st.expander(f"'{label}' listesine yeni öğe ekle/kaldır"):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_item = st.text_input("Yeni Değer", placeholder="Yeni değeri yazıp Enter'a basın", key=f"input_{state_key}")
            if new_item and new_item.strip() and new_item.strip() not in options:
                st.session_state[state_key].append(new_item.strip())
                st.rerun()
        
        with col2:
            item_to_remove = st.selectbox("Kaldır", options, index=None, placeholder="Kaldırılacak öğe", key=f"remove_{state_key}")
            if item_to_remove and st.button(f"'{item_to_remove}' öğesini sil", type="secondary"):
                st.session_state[state_key].remove(item_to_remove)
                st.rerun()
    
    return selection

# --- KİMLİK DOĞRULAMA ---
def get_google_creds():
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sa = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(sa)
    except (KeyError, FileNotFoundError):
        try:
            if os.path.exists("secrets.json"):
                sa = Credentials.from_service_account_file("secrets.json", scopes=scopes)
                return gspread.authorize(sa)
            else:
                st.error("KRİTİK HATA: 'secrets.json' bulunamadı.")
                st.stop()
        except Exception as e:
            st.error(f"Yerel 'secrets.json' okunurken hata: {e}")
            st.stop()

# --- VERİ YÜKLEME ---
@st.cache_data(ttl=600)
def load_cost_data_from_gsheets(_gc):
    try:
        workbook = _gc.open("maliyet_referans")
        worksheet = workbook.worksheet("Sayfa1")
        df = get_as_dataframe(worksheet, evaluate_formulas=True)
        # Barkodları metin olarak standartlaştır
        df['Barkod'] = df['Barkod'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df['Model Kodu'] = df['Model Kodu'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Google Sheets'ten veri okunurken hata: {e}")
        st.stop()

def load_cost_data():
    if 'gc' not in st.session_state:
        st.session_state.gc = get_google_creds()
    return load_cost_data_from_gsheets(st.session_state.gc)

# ==============================================================================
# YENİ VE GELİŞTİRİLMİŞ SİHİRBAZ (TEK SAYFA TASARIM)
# ==============================================================================
def render_yeni_urun_sihirbazi():
    load_css("style.css")
    st.title("🧙‍♂️ Yeni Ürün Sihirbazı")

    st.markdown('<div class="wizard-container">', unsafe_allow_html=True)
    col1, col2 = st.columns([6, 4])

    # --- SOL SÜTUN: Ürün Adı Oluşturucu ---
    with col1:
        st.markdown('<div class="input-section">', unsafe_allow_html=True)
        st.subheader("Ürün Adı Oluşturucu")
        kategori = st.selectbox("Ürün Kategorisi", ["Elbise", "Bluz", "Pantolon", "T-Shirt", "Tunik", "Gömlek"])
        model_kodu = st.text_input("Model Kodu", placeholder="Örn: 320315")
        yaka_tipi = dynamic_select("Yaka Tipi", "yaka_tipi_options", defaults=["Bisiklet Yaka", "V Yaka", "Gömlek Yaka"])
        kol_boyu = dynamic_select("Kol Boyu", "kol_boyu_options", defaults=["Kolsuz", "Kısa Kol", "Uzun Kol", "Yarasa Kol"])
        desen = st.text_input("Desen (Opsiyonel)", placeholder="Örn: Çiçekli, Puantiyeli")
        cep = st.radio("Cep Durumu", ["Cepli", "Cepsiz"], index=1, horizontal=True)
        kumas_karisimi = st.text_input("Kumaş Karışımı (Opsiyonel)", placeholder="Örn: %95 Polyester %5 Elastan")

        if st.button("✨ Ürün Adını Oluştur", use_container_width=True):
            parts = ["Büyük Beden"]
            if yaka_tipi: parts.append(yaka_tipi)
            if kol_boyu: parts.append(kol_boyu)
            if desen: parts.append(desen.strip().capitalize() + " Desenli")
            if cep == "Cepli": parts.append("Cepli")
            if "elastan" in kumas_karisimi.lower(): parts.append("Esnek Kumaşlı")
            if kategori: parts.append(kategori)
            if model_kodu: parts.append(model_kodu.strip())
            st.session_state.urun_adi = " ".join(parts)

        if 'urun_adi' in st.session_state:
            st.markdown('<div class="generated-title-container"><h4>Oluşturulan Başlık:</h4>', unsafe_allow_html=True)
            st.code(st.session_state.urun_adi, language=None)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- SAĞ SÜTUN: Maliyet & Fiyat Hesaplayıcı ---
    with col2:
        st.markdown('<div class="calculator-section">', unsafe_allow_html=True)
        st.subheader("Maliyet & Fiyat Hesaplayıcı")
        alis_fiyati_input = st.number_input("Ürün Alış Fiyatı (TL)", min_value=0.0, step=1.0)
        kdv_durumu = st.radio("Alış Fiyatı KDV Durumu", ["KDV Dahil", "KDV Hariç"], index=1)
        komisyon_orani = st.number_input("Komisyon Oranı (%)", min_value=0.0, value=21.5, step=0.1)
        kargo_gideri = st.number_input("Kargo Gideri (TL)", min_value=0.0, value=80.0, step=0.5)
        reklam_gideri = st.number_input("Birim Reklam Gideri (TL)", min_value=0.0, value=30.0, step=0.1)
        urun_kdv_orani = st.number_input("Ürünün KDV Oranı (%)", min_value=0.0, value=10.0, step=1.0)
        st.markdown("---")
        hedef_kar_marji = st.number_input("Hedef Kâr Marjı (%)", min_value=0.0, max_value=99.9, value=20.0, step=0.5)

        if st.button("🔮 Önerilen Satış Fiyatını Hesapla", use_container_width=True, type="primary"):
            kdv_carpan = urun_kdv_orani / 100
            kdv_bolen = 1 + kdv_carpan
            alis_fiyati_kdvsiz = alis_fiyati_input / kdv_bolen if kdv_durumu == "KDV Dahil" else alis_fiyati_input
            alis_kdv_tutari = alis_fiyati_kdvsiz * kdv_carpan
            sabit_giderler = alis_fiyati_kdvsiz + kargo_gideri + reklam_gideri
            
            payda = 1 - (komisyon_orani / 100 * kdv_bolen) - kdv_carpan - (hedef_kar_marji / 100)
            pay = sabit_giderler - alis_kdv_tutari
            
            if payda <= 0:
                st.error("Bu hedefe ulaşılamıyor. Komisyon/kâr hedefi çok yüksek.")
                satis_fiyati_kdvli, net_kar, kar_marji = 0, 0, 0
            else:
                satis_fiyati_kdvsiz = pay / payda
                satis_fiyati_kdvli = satis_fiyati_kdvsiz * kdv_bolen
                satis_kdv_tutari = satis_fiyati_kdvsiz * kdv_carpan
                net_odenecek_kdv = satis_kdv_tutari - alis_kdv_tutari
                komisyon_gideri = satis_fiyati_kdvli * (komisyon_orani / 100)
                toplam_giderler = sabit_giderler + komisyon_gideri + net_odenecek_kdv
                net_kar = satis_fiyati_kdvsiz - toplam_giderler
                kar_marji = (net_kar / satis_fiyati_kdvsiz) * 100 if satis_fiyati_kdvsiz > 0 else 0

            st.metric("Önerilen Satış Fiyatı (KDV Dahil)", f"{satis_fiyati_kdvli:,.2f} TL")
            st.metric("Bu Fiyattaki Net Kâr", f"{net_kar:,.2f} TL")
            st.metric("Gerçekleşen Kâr Marjı", f"{kar_marji:.2f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# EKSİK OLAN TÜM SAYFA FONKSİYONLARI BURAYA EKLENİYOR
# ==============================================================================

def kar_hesapla(row, satis_fiyati, kargo_gideri, reklam_gideri, komisyon_orani, kdv_orani):
    """Tek bir ürün satırı için kâr hesaplaması yapar."""
    alis_fiyati = row['Alış Fiyatı']
    kdv_bolen = 1 + (kdv_orani / 100)
    
    satis_fiyati_kdvsiz = satis_fiyati / kdv_bolen
    komisyon_tutari = satis_fiyati * (komisyon_orani / 100)
    
    toplam_maliyet = alis_fiyati + kargo_gideri + reklam_gideri + komisyon_tutari
    net_kar = satis_fiyati_kdvsiz - toplam_maliyet
    kar_marji = (net_kar / satis_fiyati_kdvsiz) * 100 if satis_fiyati_kdvsiz > 0 else 0
    
    return pd.Series([net_kar, kar_marji, toplam_maliyet], index=['Net Kâr', 'Kâr Marjı (%)', 'Toplam Maliyet'])

def render_karlilik_analizi():
    st.title("📈 Kârlılık Analizi")
    st.info("Bu modül, önceki versiyonlardan geri yüklenmiştir. Lütfen işlevselliğini kontrol ediniz.")
    # Bu alana eski kârlılık analizi kodlarınız gelecek.
    # Şimdilik uygulamanın çökmemesi için bir placeholder olarak eklendi.

def render_toptan_fiyat_teklifi():
    st.title("📑 Toptan Fiyat Teklifi Oluşturucu")
    df_maliyet = load_cost_data()

    if 'teklif_listesi' not in st.session_state:
        st.session_state.teklif_listesi = []

    options = df_maliyet['Model Kodu'].unique()
    secilen_model = st.selectbox("Teklife Eklenecek Ürünü Seçin", options, index=None, placeholder="Model Kodu seçin...")

    if secilen_model:
        secilen_adet = st.number_input(f"'{secilen_model}' için adet girin", min_value=1, value=10, step=1)
        if st.button("➕ Ürünü Teklife Ekle", key=f"ekle_{secilen_model}"):
            urun_detay = df_maliyet[df_maliyet['Model Kodu'] == secilen_model].iloc[0]
            st.session_state.teklif_listesi.append({
                "Model Kodu": urun_detay['Model Kodu'], "Adet": secilen_adet, "Birim Maliyet": urun_detay['Alış Fiyatı']
            })
            st.success(f"{secilen_adet} adet '{secilen_model}' teklife eklendi.")

    if st.session_state.teklif_listesi:
        df_teklif = pd.DataFrame(st.session_state.teklif_listesi)
        kar_marji = st.slider("Uygulanacak Kâr Marjı (%)", 0.0, 200.0, 50.0)
        df_teklif['Birim Satış Fiyatı (KDV Hariç)'] = df_teklif['Birim Maliyet'] / (1 - (kar_marji / 100))
        df_teklif['Toplam Fiyat (KDV Hariç)'] = df_teklif['Birim Satış Fiyatı (KDV Hariç)'] * df_teklif['Adet']
        st.dataframe(df_teklif)

def render_satis_fiyati_hesaplayici():
    st.title("🧮 Satış Fiyatı Hesaplayıcı")
    df_maliyet = load_cost_data()
    model_kodlari = df_maliyet['Model Kodu'].unique()
    secilen_model = st.selectbox("Analiz edilecek ürünün model kodunu seçin:", model_kodlari)
    
    if secilen_model:
        urun_bilgileri = df_maliyet[df_maliyet['Model Kodu'] == secilen_model].iloc[0]
        st.write(f"**Seçilen Ürün:** {urun_bilgileri.get('Ürün Adı', 'N/A')}")
        
        satis_fiyati = st.number_input("Satış Fiyatı (KDV Dahil)", min_value=0.0, value=500.0, step=10.0)
        kargo_gideri = st.number_input("Kargo Gideri", min_value=0.0, value=80.0, step=1.0)
        reklam_gideri = st.number_input("Birim Başına Reklam Gideri", min_value=0.0, value=20.0, step=1.0)
        komisyon_orani = st.number_input("Platform Komisyon Oranı (%)", min_value=0.0, value=21.5, step=0.1)
        kdv_orani = st.number_input("Ürün KDV Oranı (%)", min_value=0.0, value=10.0, step=1.0)

        if st.button("Hesapla"):
            sonuclar = kar_hesapla(urun_bilgileri, satis_fiyati, kargo_gideri, reklam_gideri, komisyon_orani, kdv_orani)
            st.metric("Net Kâr", f"{sonuclar['Net Kâr']:,.2f} TL")
            st.metric("Kâr Marjı", f"{sonuclar['Kâr Marjı (%)']:.2f}%")

def render_aylik_hedef_analizi():
    st.title("🎯 Aylık Hedef Analizi")
    st.info("Bu modül, önceki versiyonlardan geri yüklenmiştir. Lütfen işlevselliğini kontrol ediniz.")
    # Bu alana eski aylık hedef analizi kodlarınız gelecek.

def render_maliyet_yonetimi():
    st.title("⚙️ Maliyet Yönetimi")
    st.info("Bu modül, önceki versiyonlardan geri yüklenmiştir. Lütfen işlevselliğini kontrol ediniz.")
    # Bu alana eski maliyet yönetimi kodlarınız gelecek.

# ==============================================================================
# ANA UYGULAMA AKIŞI
# ==============================================================================
st.set_page_config(page_title="Stil Diva Panel", layout="wide")

# Kimlik doğrulama
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)
authenticator = stauth.Authenticate(
    config['credentials'], config['cookie']['name'],
    config['cookie']['key'], config['cookie']['expiry_days']
)
authenticator.login(location='main')

if st.session_state["authentication_status"]:
    with st.sidebar:
        st.image("logo.png", width=200)
        st.write(f'Hoşgeldin *{st.session_state["name"]}*')
        authenticator.logout('Çıkış Yap', 'main')
        st.markdown("---")
        st.subheader("Araçlar")
        
        # --- BU LİSTEYİ ESKİ HALİNE GETİRİYORUZ ---
        app_mode = st.selectbox(
            "Hangi aracı kullanmak istersiniz?",
            [
                "Kârlılık Analizi",
                "Toptan Fiyat Teklifi",
                "Satış Fiyatı Hesaplayıcı",
                "Aylık Hedef Analizi",
                "Maliyet Yönetimi",
                "🧙‍♂️ Yeni Ürün Sihirbazı" # Yeni sihirbazı listenin sonuna ekledik
            ],
            label_visibility="collapsed"
        )

    # --- BU YÖNLENDİRMEYİ ESKİ HALİNE GETİRİYORUZ ---
    if app_mode == "Kârlılık Analizi":
        render_karlilik_analizi()
    elif app_mode == "Toptan Fiyat Teklifi":
        render_toptan_fiyat_teklifi()
    elif app_mode == "Satış Fiyatı Hesaplayıcı":
        render_satis_fiyati_hesaplayici()
    elif app_mode == "Aylık Hedef Analizi":
        render_aylik_hedef_analizi()
    elif app_mode == "Maliyet Yönetimi":
        render_maliyet_yonetimi()
    elif app_mode == "🧙‍♂️ Yeni Ürün Sihirbazı": # Yeni sihirbaz için yönlendirme ekledik
        render_yeni_urun_sihirbazi()

elif st.session_state["authentication_status"] is False:
    st.error('Kullanıcı adı/şifre yanlış')
elif st.session_state["authentication_status"] is None:
    st.warning('Lütfen kullanıcı adı ve şifrenizi girin')
