import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
import io
from datetime import datetime
import calendar
import plotly.express as px

# --------------------------------------------------------------------------------
# Sayfa Yapılandırması ve Başlangıç Ayarları
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="Stil Diva - Yönetim Paneli",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Özel CSS Stilleri ---
def inject_custom_css():
    # Session state'den mevcut temayı al, yoksa varsayılan olarak 'dark' ata
    theme = st.session_state.get('theme', 'dark')

    # Temaya göre renk paletini belirle
    if theme == 'light':
        # Açık Tema Renkleri
        bg_color = "#f5f5f5"         # Beyaza yakın krem
        text_color = "#212121"       # Siyaha yakın gri
        card_bg_color = "#ffffff"    # Kartlar için saf beyaz
        sidebar_bg_color = "#e8e8e8" # Kenar çubuğu için biraz daha koyu
        accent_color = "#ff8c69"     # Ana renk
        secondary_bg_color = "#f0f2f6" # Selectbox gibi elemanlar için
    else:
        # Koyu Tema Renkleri (Varsayılan)
        bg_color = "#0e1117"         # Siyaha yakın gri
        text_color = "#fafafa"       # Beyaz
        card_bg_color = "#1c1e24"    # Kartlar için biraz daha açık
        sidebar_bg_color = "#1c1e24" # Kenar çubuğu
        accent_color = "#ff8c69"     # Ana renk
        secondary_bg_color = "#262730" # Selectbox gibi elemanlar için

    # CSS'i dinamik olarak oluştur ve enjekte et
    st.markdown(f"""
        <style>
            /* === GENEL GÖVDE VE ARKA PLAN === */
            /* Bu, ana panelin arka planını değiştirmeyi garantiler */
            [data-testid="stAppViewContainer"] > .main {{
                background-color: {bg_color};
            }}
            .main .block-container {{
                background-color: {bg_color};
                color: {text_color};
            }}

            /* === KENAR ÇUBUĞU (SIDEBAR) === */
            [data-testid="stSidebar"] {{
                background-color: {sidebar_bg_color};
            }}

            /* === METİN VE BAŞLIKLAR === */
            /* Hem ana paneldeki hem de kenar çubuğundaki tüm metinleri hedefler */
            h1, h2, h3, h4, h5, h6, p, label, .st-emotion-cache-10trblm, .st-emotion-cache-16idsys p {{
                color: {text_color};
            }}
            [data-testid="stSidebar"] * {{
                color: {text_color};
            }}

            /* === ÖZEL BİLEŞENLER === */
            /* "Sihirbazlar" selectbox'ını hedefler */
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
                background-color: {secondary_bg_color};
                border-color: {accent_color};
                color: {text_color};
            }}
            /* Selectbox içindeki metin */
            [data-testid="stSelectbox"] div[data-baseweb="select"] span {{
                 color: {text_color};
            }}

            /* Kart Stili */
            .card {{
                background: {card_bg_color};
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }}

            /* Metrik Kutuları */
            .stMetric {{
                background-color: {card_bg_color};
                border-left: 5px solid {accent_color};
                padding: 15px;
                border-radius: 8px;
            }}
            .stMetric label, .stMetric .st-emotion-cache-1wivap2, .stMetric .st-emotion-cache-1g8m51x {{
                 color: {text_color} !important; /* !important ekleyerek önceliği artırıyoruz */
            }}

            /* Butonlar */
            .stButton > button {{
                border-radius: 8px;
                border: 1px solid {accent_color};
                background-color: {accent_color};
                color: white;
            }}
            .stButton > button:hover {{
                background-color: #ff7043;
                border-color: #ff7043;
            }}
        </style>
    """, unsafe_allow_html=True)

# Google Sheets bağlantısı ve veri yükleme fonksiyonu
def load_cost_data_from_gsheets():
    if 'df_maliyet' not in st.session_state:
        try:
            # Streamlit'in Secrets yönetiminden kimlik bilgilerini al
            creds = st.secrets["gcp_service_account"]
            scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            
            # Kimlik bilgilerini yetkilendir
            sa = Credentials.from_service_account_info(creds, scopes=scopes)
            gc = gspread.authorize(sa)
            
            # Google Sheet'i aç ve veriyi DataFrame olarak oku
            # "Maliyetler" -> Google Sheet dosyanızın adı
            # "Sayfa1" -> Çalışma sayfasının adı
            workbook = gc.open("Maliyetler") 
            worksheet = workbook.worksheet("Sayfa1")
            
            df = get_as_dataframe(worksheet)
            st.session_state.df_maliyet = df
            
        except Exception as e:
            st.session_state.df_maliyet = pd.DataFrame(columns=["Model Kodu", "Barkod", "Alış Fiyatı"])
            st.sidebar.error(f"Google Sheets'ten veri okunurken hata: {e}")
            
    return st.session_state.df_maliyet

# Maliyet verilerini oturum boyunca hafızada tutmak için fonksiyon
def load_cost_data():
    # Bu fonksiyonu artık Google Sheets'e yönlendiriyoruz.
    # Eğer yerel dosyayı hala bir yedek olarak kullanmak isterseniz, bu mantığı koruyabilirsiniz.
    # Şimdilik doğrudan Google Sheets'i çağırıyoruz.
    return load_cost_data_from_gsheets()

# --------------------------------------------------------------------------------
# MOD 1: KÂRLILIK ANALİZİ
# --------------------------------------------------------------------------------
def render_karlilik_analizi():
    st.title("📊 Kârlılık Analiz Paneli")
    load_cost_data()

    siparis_excel = st.file_uploader("Pixa Sipariş Excelini Yükleyin", type=["xlsx", "xls"], key="karlilik_siparis_uploader")

    if 'df_siparis_orjinal' not in st.session_state:
        st.session_state.df_siparis_orjinal = None

    if siparis_excel:
        try:
            if st.session_state.get('uploaded_filename') != siparis_excel.name:
                df_siparis = pd.read_excel(siparis_excel, engine="calamine")
                df_siparis['Sipariş Tarihi'] = pd.to_datetime(df_siparis['Sipariş Tarihi'], errors='coerce')
                st.session_state.df_siparis_orjinal = df_siparis.dropna(subset=['Sipariş Tarihi'])
                st.session_state.uploaded_filename = siparis_excel.name
        except Exception as e:
            st.error(f"Sipariş dosyası okunurken bir hata oluştu: {e}")
            st.session_state.df_siparis_orjinal = None

    if st.session_state.df_siparis_orjinal is not None:
        df_siparis_orjinal = st.session_state.df_siparis_orjinal

        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("🔍 Filtreleme Seçenekleri")
            filt_col1, filt_col2 = st.columns([1, 2])

            with filt_col1:
                min_tarih = df_siparis_orjinal['Sipariş Tarihi'].min().date()
                maks_tarih = df_siparis_orjinal['Sipariş Tarihi'].max().date()
                secilen_baslangic, secilen_bitis = st.date_input(
                    "Tarih Aralığı Seçin", value=(min_tarih, maks_tarih),
                    min_value=min_tarih, max_value=maks_tarih, key='tarih_filtresi'
                )

            with filt_col2:
                platformlar = sorted(df_siparis_orjinal['Platform'].unique())
                secilen_platformlar = st.multiselect(
                    "Platforma Göre Filtrele", options=platformlar,
                    default=platformlar, key='platform_filtresi'
                )
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("⚙️ Analiz Parametreleri")
            col1, col2, col3 = st.columns(3)
            with col1:
                komisyon_oran = st.number_input("Ort. Komisyon (%)", min_value=0.0, value=21.5, step=0.1)
                kdv_oran = st.number_input("KDV Oranı (%)", min_value=0.0, value=10.0, step=1.0)
            with col2:
                toplam_kargo_faturasi = st.number_input("Toplam Kargo Faturası (TL)", min_value=0.0, value=0.0, step=1.0)
                kargo_maliyeti_siparis_basi = st.number_input("Sipariş Başı Kargo (TL)", min_value=0.0, value=80.0, step=0.5, disabled=(toplam_kargo_faturasi > 0))
            with col3:
                toplam_reklam_butcesi = st.number_input("Toplam Reklam Bütçesi (TL)", min_value=0.0, value=0.0, step=1.0)
                reklam_gideri_urun_basi = st.number_input("Ürün Başı Reklam (TL)", min_value=0.0, value=0.0, step=0.1, disabled=(toplam_reklam_butcesi > 0))

            if st.button("🚀 Filtrelenmiş Veriyle Analizi Başlat", key="karlilik_button"):
                df_filtrelenmis = df_siparis_orjinal[
                    (df_siparis_orjinal['Sipariş Tarihi'].dt.date >= secilen_baslangic) &
                    (df_siparis_orjinal['Sipariş Tarihi'].dt.date <= secilen_bitis) &
                    (df_siparis_orjinal['Platform'].isin(secilen_platformlar))
                ]

                if df_filtrelenmis.empty:
                    st.warning("Seçtiğiniz filtrelere uygun hiçbir sipariş bulunamadı.")
                    st.session_state.analiz_calisti = False
                else:
                    st.session_state.df_tum_siparisler = df_filtrelenmis.copy()
                    st.session_state.analiz_params = {
                        "komisyon_oran": komisyon_oran, "kdv_oran": kdv_oran,
                        "toplam_kargo_faturasi": toplam_kargo_faturasi, "kargo_maliyeti_siparis_basi": kargo_maliyeti_siparis_basi,
                        "toplam_reklam_butcesi": toplam_reklam_butcesi, "reklam_gideri_urun_basi": reklam_gideri_urun_basi,
                        "satis_fiyati_sutunu": 'Tutar'
                    }
                    st.session_state.analiz_calisti = True
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.get('analiz_calisti', False):
        run_and_display_analysis()

def run_and_display_analysis():
    try:
        df_siparis = st.session_state.df_tum_siparisler
        df_maliyet = st.session_state.df_maliyet
        params = st.session_state.analiz_params

        df_merged = pd.merge(df_siparis, df_maliyet, on="Barkod", how="left")
        df_maliyetli = df_merged[df_merged['Alış Fiyatı'].notna()].copy()
        df_maliyetsiz = df_merged[df_merged['Alış Fiyatı'].isna()].copy()

        toplam_satilan_urun = df_siparis['Miktar'].sum()
        essiz_siparis_sayisi = df_siparis['Sipariş No'].nunique()
        if params['toplam_kargo_faturasi'] > 0:
            urun_basi_kargo_maliyeti = params['toplam_kargo_faturasi'] / toplam_satilan_urun if toplam_satilan_urun > 0 else 0
        else:
            urun_basi_kargo_maliyeti = (params['kargo_maliyeti_siparis_basi'] * essiz_siparis_sayisi) / toplam_satilan_urun if toplam_satilan_urun > 0 else 0

        if params['toplam_reklam_butcesi'] > 0:
            trendyol_urun_adedi = df_siparis[df_siparis['Platform'] == 'Trendyol']['Miktar'].sum()
            urun_basi_reklam_gideri_trendyol = params['toplam_reklam_butcesi'] / trendyol_urun_adedi if trendyol_urun_adedi > 0 else 0
            df_maliyetli['Birim_Reklam_Gideri'] = df_maliyetli['Platform'].apply(lambda x: urun_basi_reklam_gideri_trendyol if x == 'Trendyol' else 0)
        else:
            df_maliyetli['Birim_Reklam_Gideri'] = params['reklam_gideri_urun_basi']

        df_grouped = df_maliyetli.groupby('Model Kodu').agg(
            Toplam_Adet=('Miktar', 'sum'),
            Toplam_Ciro_Analiz_Edilen=(params['satis_fiyati_sutunu'], lambda x: (x * df_maliyetli.loc[x.index, 'Miktar']).sum()),
            Alis_Fiyati_KDVsiz=('Alış Fiyatı', 'first'),
            Toplam_Reklam_Gideri=('Birim_Reklam_Gideri', lambda x: (x * df_maliyetli.loc[x.index, 'Miktar']).sum())
        ).reset_index()

        toplam_analiz_kari = 0
        if not df_grouped.empty:
            df_grouped['Ort_Satis_Fiyati_KDVli'] = df_grouped['Toplam_Ciro_Analiz_Edilen'] / df_grouped['Toplam_Adet']
            kdv_bolen = 1 + (params['kdv_oran'] / 100)
            kdv_carpan = params['kdv_oran'] / 100
            df_grouped['Ort_Satis_Fiyati_KDVsiz'] = df_grouped['Ort_Satis_Fiyati_KDVli'] / kdv_bolen
            df_grouped['Satis_KDV'] = df_grouped['Ort_Satis_Fiyati_KDVli'] - df_grouped['Ort_Satis_Fiyati_KDVsiz']
            df_grouped['Alis_KDV'] = df_grouped['Alis_Fiyati_KDVsiz'] * kdv_carpan
            df_grouped['Net_Odenecek_KDV'] = df_grouped['Satis_KDV'] - df_grouped['Alis_KDV']
            df_grouped['Komisyon_TL'] = df_grouped['Ort_Satis_Fiyati_KDVli'] * (params['komisyon_oran'] / 100)
            df_grouped['Birim_Kar'] = (df_grouped['Ort_Satis_Fiyati_KDVsiz'] - df_grouped['Alis_Fiyati_KDVsiz'] - df_grouped['Net_Odenecek_KDV'] - df_grouped['Komisyon_TL'] - urun_basi_kargo_maliyeti)
            df_grouped['Toplam_Kar'] = (df_grouped['Birim_Kar'] * df_grouped['Toplam_Adet']) - df_grouped['Toplam_Reklam_Gideri']
            toplam_analiz_kari = df_grouped['Toplam_Kar'].sum()

        st.session_state.toplam_analiz_kari = toplam_analiz_kari

        if not df_maliyetsiz.empty:
            st.warning(f"**DİKKAT:** Seçtiğiniz filtredeki **{len(df_maliyetsiz)}** satır ürünün maliyet bilgisi bulunamadı. Aşağıdaki 'Eksik Maliyetleri Gir' sekmesinden bu verileri tamamlayabilirsiniz.")
            tab1, tab2 = st.tabs(["Genel Analiz", "⚠️ Eksik Maliyetleri Gir"])
            with tab1:
                display_summary_and_details(df_siparis, df_grouped, toplam_analiz_kari, urun_basi_kargo_maliyeti)
            with tab2:
                render_eksik_maliyet_tab(df_maliyetsiz)
        else:
            display_summary_and_details(df_siparis, df_grouped, toplam_analiz_kari, urun_basi_kargo_maliyeti)
    except Exception as e:
        st.error(f"Analiz sırasında bir hata oluştu: {e}")

def display_summary_and_details(df_siparis, df_grouped, toplam_analiz_kari, urun_basi_kargo_maliyeti):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📦 Sipariş Özeti (Filtrelenmiş Veri)")
        sum_col1, sum_col2, sum_col3 = st.columns(3)
        sum_col1.metric("Toplam Sipariş Sayısı", f"{df_siparis['Sipariş No'].nunique()}")
        sum_col2.metric("Toplam Satılan Ürün", f"{df_siparis['Miktar'].sum()}")
        sum_col3.metric("Sipariş Başına Ürün", f"{(df_siparis['Miktar'].sum() / df_siparis['Sipariş No'].nunique()) if df_siparis['Sipariş No'].nunique() > 0 else 0:.2f}")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("💰 Genel Finansal Bakış (Filtrelenmiş Veri)")
        m_col1, m_col2 = st.columns(2)
        toplam_gercek_ciro = (df_siparis['Tutar'] * df_siparis['Miktar']).sum()
        m_col1.metric("Toplam Ciro (KDV Dahil)", f"{toplam_gercek_ciro:,.2f} TL")
        m_col2.metric("Toplam Net Kâr (Analiz Edilen)", f"{toplam_analiz_kari:,.2f} TL")

        m_col3, m_col4 = st.columns(2)
        m_col3.metric("Net Kâr Marjı", f"{(toplam_analiz_kari / toplam_gercek_ciro * 100) if toplam_gercek_ciro > 0 else 0:.2f}%")
        m_col4.metric("Hesaplanan Ürün Başı Kargo", f"{urun_basi_kargo_maliyeti:,.2f} TL")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🌐 Platform Performansı")
        df_platform = df_siparis.groupby('Platform').agg(
            Ciro=('Tutar', lambda x: (x * df_siparis.loc[x.index, 'Miktar']).sum())
        ).reset_index()

        pie_col, data_col = st.columns([2,3])
        with pie_col:
            fig = px.pie(df_platform, names='Platform', values='Ciro', title='Ciro Dağılımı',
                         color_discrete_sequence=px.colors.sequential.Peach)
            fig.update_layout(showlegend=False)
            fig.update_traces(textinfo='percent+label', textfont_size=14)
            st.plotly_chart(fig, use_container_width=True)
        with data_col:
            st.dataframe(df_platform.sort_values('Ciro', ascending=False).style.format({'Ciro': '{:,.2f} TL'}), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📋 Model Bazında Detaylı Analiz (Maliyeti Bilinenler)")
        if not df_grouped.empty:
            df_display = df_grouped[['Model Kodu', 'Toplam_Adet', 'Ort_Satis_Fiyati_KDVli', 'Alis_Fiyati_KDVsiz', 'Komisyon_TL', 'Net_Odenecek_KDV', 'Birim_Kar', 'Toplam_Kar']].copy()
            for col in df_display.columns.drop(['Model Kodu', 'Toplam_Adet']): df_display[col] = df_display[col].map('{:,.2f} TL'.format)
            st.dataframe(df_display, use_container_width=True)
        else:
            st.warning("Maliyeti bilinen ürün bulunamadı.")
        st.markdown('</div>', unsafe_allow_html=True)

def render_eksik_maliyet_tab(df_maliyetsiz):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📝 Eksik Maliyet Bilgileri")
        eksik_urunler_editor = df_maliyetsiz[['Barkod', 'Model Kodu', 'Alış Fiyatı']].drop_duplicates(subset=['Barkod']).copy()
        edited_eksikler = st.data_editor(eksik_urunler_editor, disabled=["Barkod"], key="eksik_maliyet_editor", use_container_width=True)
        if st.button("🔄 Girilen Maliyetlerle Analizi Güncelle", key="guncelle_button"):
            if edited_eksikler['Alış Fiyatı'].isna().any() or (edited_eksikler['Model Kodu'].astype(str).str.strip() == '').any():
                st.error("Lütfen tüm eksik 'Model Kodu' ve 'Alış Fiyatı' alanlarını doldurun.")
            else:
                yeni_maliyetler = edited_eksikler.dropna()
                st.session_state.df_maliyet = pd.concat([st.session_state.df_maliyet, yeni_maliyetler], ignore_index=True).drop_duplicates(subset=['Barkod'], keep='last')
                st.success("Maliyet referans listesi güncellendi! Analiz yeniden çalıştırılıyor...")
                st.session_state.analiz_calisti = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def render_maliyet_yonetimi():
    st.title("🗃️ Maliyet Veri Yönetimi")
    load_cost_data()
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("➕ Yeni Ürün Ekle")
        with st.form("yeni_urun_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            yeni_model, yeni_barkod, yeni_alis = f_col1.text_input("Yeni Ürün Model Kodu"), f_col2.text_input("Yeni Ürün Barkodu"), f_col3.number_input("Yeni Ürün Alış Fiyatı (KDV Hariç)", min_value=0.0, format="%.2f")
            if st.form_submit_button("Yeni Ürünü Ekle") and yeni_barkod and yeni_model:
                yeni_veri = pd.DataFrame([{"Model Kodu": yeni_model, "Barkod": yeni_barkod, "Alış Fiyatı": yeni_alis}])
                st.session_state.df_maliyet = pd.concat([st.session_state.df_maliyet, yeni_veri], ignore_index=True).drop_duplicates(subset=['Barkod'], keep='last')
                st.success(f"'{yeni_barkod}' barkodlu ürün eklendi.")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("✏️ Mevcut Maliyetleri Düzenle")
        edited_df = st.data_editor(st.session_state.df_maliyet, num_rows="dynamic", use_container_width=True, key="maliyet_editor")
        if st.button("💾 Değişiklikleri Kaydet ve İndir"):
            st.session_state.df_maliyet = edited_df.copy()
            st.success("Değişiklikler kaydedildi!")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.df_maliyet.to_excel(writer, index=False, sheet_name='Maliyetler')
            st.download_button(label="✅ Güncel Maliyet Excel'ini İndir", data=output.getvalue(), file_name='guncel_maliyet_referans.xlsx')
            st.warning("**ÖNEMLİ:** Değişikliklerin kalıcı olması için bu indirdiğiniz dosyayı GitHub'a `maliyet_referans.xlsx` adıyla yeniden yüklemeniz gerekir!")
        st.markdown('</div>', unsafe_allow_html=True)

def render_hedef_analizi():
    st.title("🎯 Aylık Hedef Analizi")
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        hedef_kar = st.number_input("Bu Ayki Net Kâr Hedefiniz (TL)", min_value=0, value=1000000, step=10000)
        st.markdown('</div>', unsafe_allow_html=True)
    if 'toplam_analiz_kari' not in st.session_state:
        st.info("Lütfen önce 'Kârlılık Analizi' sayfasından bir analiz yapın."); return
    gerceklesen_kar = st.session_state.toplam_analiz_kari
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📈 Hedefe Giden Yol")
        hedefe_ulasma_orani = (gerceklesen_kar / hedef_kar) if hedef_kar > 0 else 0
        st.progress(max(0.0, hedefe_ulasma_orani), text=f"Hedefin %{hedefe_ulasma_orani:.1%} kadarı tamamlandı")
        h_col1, h_col2, h_col3 = st.columns(3)
        h_col1.metric("Hedef Kâr", f"{hedef_kar:,.0f} TL")
        h_col2.metric("Gerçekleşen Kâr", f"{gerceklesen_kar:,.0f} TL", delta=f"{gerceklesen_kar - hedef_kar:,.0f} TL")
        h_col3.metric("Kalan Hedef", f"{hedef_kar - gerceklesen_kar:,.0f} TL")
        st.markdown('</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🔮 Gelecek Projeksiyonu")
        today = datetime.now()
        _, aydaki_gun_sayisi = calendar.monthrange(today.year, today.month)
        gecen_gun, kalan_gun = today.day, aydaki_gun_sayisi - today.day
        if gecen_gun > 0:
            gunluk_ortalama_kar = gerceklesen_kar / gecen_gun
            p_col1, p_col2 = st.columns(2)
            p_col1.metric("Günlük Ortalama Kâr", f"{gunluk_ortalama_kar:,.0f} TL/gün")
            p_col2.metric("Ay Sonu Tahmini Kâr", f"{gunluk_ortalama_kar * aydaki_gun_sayisi:,.0f} TL")
            if kalan_gun > 0:
                gereken_gunluk_kar = (hedef_kar - gerceklesen_kar) / kalan_gun if (hedef_kar - gerceklesen_kar) > 0 else 0
                st.metric("Hedefe Ulaşmak İçin Gereken Günlük Kâr", f"{gereken_gunluk_kar:,.0f} TL/gün")
                if gunluk_ortalama_kar > 0:
                    st.info(f"Hedefe ulaşmak için günlük kârınızı **%{((gereken_gunluk_kar / gunluk_ortalama_kar) - 1) * 100 if gereken_gunluk_kar > 0 else -100:.1f}** artırmanız gerekmektedir.")
        st.markdown('</div>', unsafe_allow_html=True)

def render_satis_fiyati_hesaplayici():
    st.title("🏷️ Satış Fiyatı Hesaplayıcı")
    left_col, right_col = st.columns([2, 3])
    with left_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⚙️ Varsayılan Maliyetler")
        if 'tekil_komisyon' not in st.session_state: st.session_state.tekil_komisyon = 21.5
        if 'tekil_kdv' not in st.session_state: st.session_state.tekil_kdv = 10.0
        if 'tekil_kargo' not in st.session_state: st.session_state.tekil_kargo = 80.0
        if 'tekil_reklam' not in st.session_state: st.session_state.tekil_reklam = 0.0
        st.session_state.tekil_komisyon = st.number_input("Komisyon Oranı (%)", min_value=0.0, value=st.session_state.tekil_komisyon, key='s_kom')
        st.session_state.tekil_kdv = st.number_input("KDV Oranı (%)", min_value=0.0, value=st.session_state.tekil_kdv, key='s_kdv')
        st.session_state.tekil_kargo = st.number_input("Kargo Gideri (TL)", min_value=0.0, value=st.session_state.tekil_kargo, key='s_kar')
        st.session_state.tekil_reklam = st.number_input("Reklam Gideri (TL)", min_value=0.0, value=st.session_state.tekil_reklam, key='s_rek')
        st.markdown('</div>', unsafe_allow_html=True)
    with right_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📦 Ürün Arama ve Simülasyon")
        df_maliyet = load_cost_data()
        arama_terimi = st.text_input("Model Kodu ile Ürün Ara", "")
        secilen_urun_detay = None
        if arama_terimi:
            sonuclar = df_maliyet[df_maliyet['Model Kodu'].str.contains(arama_terimi, case=False, na=False)]
            if not sonuclar.empty:
                secilen_model_kodu = st.selectbox("Bulunan Modeller", sonuclar['Model Kodu'].unique(), index=None, placeholder="Lütfen bir model seçin...")
                if secilen_model_kodu: secilen_urun_detay = sonuclar[sonuclar['Model Kodu'] == secilen_model_kodu].iloc[0]
        if secilen_urun_detay is not None:
            urun = secilen_urun_detay
            st.success(f"**Seçilen Ürün:** {urun['Model Kodu']} | **Alış Fiyatı (KDV Hariç):** {urun['Alış Fiyatı']:,.2f} TL")
            satis_fiyati_kdvli = st.number_input("Satış Fiyatı (KDV Dahil)", min_value=0.0, format="%.2f", key="satis_fiyati_input")
            if st.button("Hesapla", type="primary"):
                if satis_fiyati_kdvli > 0:
                    kdv_bolen, kdv_carpan = 1 + (st.session_state.tekil_kdv / 100), st.session_state.tekil_kdv / 100
                    satis_fiyati_kdvsiz = satis_fiyati_kdvli / kdv_bolen
                    net_odenecek_kdv = (satis_fiyati_kdvli - satis_fiyati_kdvsiz) - (urun['Alış Fiyatı'] * kdv_carpan)
                    komisyon_tl = satis_fiyati_kdvli * (st.session_state.tekil_komisyon / 100)
                    net_kar = (satis_fiyati_kdvsiz - urun['Alış Fiyatı'] - net_odenecek_kdv - komisyon_tl - st.session_state.tekil_kargo - st.session_state.tekil_reklam)
                    st.subheader("Sonuç"); res_col1, res_col2, res_col3 = st.columns(3)
                    res_col1.metric("Net Kâr", f"{net_kar:,.2f} TL")
                    res_col2.metric("Kâr Marjı", f"{(net_kar / satis_fiyati_kdvli * 100) if satis_fiyati_kdvli > 0 else 0:.2f}%")
                    res_col3.metric("Net Ödenecek KDV", f"{net_odenecek_kdv:,.2f} TL")
        st.markdown('</div>', unsafe_allow_html=True)

def render_toptan_fiyat_teklifi():
    st.title("📑 Toptan Fiyat Teklifi Oluşturucu")
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Fiyatlandırma Stratejisi")
        left, right = st.columns(2)
        with left: hedef_tipi = st.radio("Kârlılık Hedef Tipi:", ["% Kâr Marjı", "TL Kâr Hedefi"], horizontal=True)
        with right: hedef_deger = st.number_input("Hedef Değer", min_value=0.0, value=25.0 if hedef_tipi == "% Kâr Marjı" else 100.0, step=0.5)
        st.subheader("Genel Maliyet Parametreleri")
        if 'toptan_komisyon' not in st.session_state: st.session_state.toptan_komisyon = 21.5
        if 'toptan_kdv' not in st.session_state: st.session_state.toptan_kdv = 10.0
        t_col1, t_col2 = st.columns(2)
        st.session_state.toptan_komisyon = t_col1.number_input("Komisyon Oranı (%)", min_value=0.0, value=st.session_state.toptan_komisyon, key='t_kom')
        st.session_state.toptan_kdv = t_col2.number_input("KDV Oranı (%)", min_value=0.0, value=st.session_state.toptan_kdv, key='t_kdv')
        if st.button("Fiyat Listesini Oluştur", type="primary"):
            df_maliyet_unique = load_cost_data().drop_duplicates(subset=['Model Kodu'], keep='first').copy()
            AF, k, v = df_maliyet_unique['Alış Fiyatı'], st.session_state.toptan_komisyon / 100, st.session_state.toptan_kdv / 100
            payda = (1 / (1 + v)) - k
            if hedef_tipi == "TL Kâr Hedefi": pay = hedef_deger + AF
            else: payda -= (hedef_deger / 100) * (1 - v); pay = AF
            if payda <= 0: st.error("Bu parametrelerle pozitif bir satış fiyatı hesaplanamıyor.")
            else:
                df_maliyet_unique['Satış Fiyatı'] = pay / payda * (1+v)
                st.session_state.teklif_df = df_maliyet_unique[['Model Kodu', 'Satış Fiyatı']]
                st.success("Fiyat teklifi başarıyla oluşturuldu!")
        st.markdown('</div>', unsafe_allow_html=True)
    if 'teklif_df' in st.session_state:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Oluşturulan Fiyat Listesi")
            st.dataframe(st.session_state.teklif_df.style.format({'Satış Fiyatı': '{:,.2f} TL'}), use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: st.session_state.teklif_df.to_excel(writer, index=False, sheet_name='Fiyat_Teklifi')
            st.download_button(label="✅ Fiyat Listesini Excel Olarak İndir", data=output.getvalue(), file_name='Toptan_Fiyat_Teklifi.xlsx')
            st.markdown('</div>', unsafe_allow_html=True)

# --- KULLANICI GİRİŞİ ---
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- YENİ VE DOĞRU GİRİŞ MANTIĞI (v0.2.1 için) ---
# 'login' fonksiyonu, formun adını ve konumunu argüman olarak alır.
# Geriye kullanıcı adı, doğrulama durumu ve kullanıcı adını döndürür.
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # --- ANA UYGULAMA AKIŞI ---
    with st.sidebar:
        st.markdown(f"""<div style="text-align: center; padding-top: 20px;"><svg width="150" height="50" viewBox="0 0 150 50"><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="Brush Script MT, cursive" font-size="35" fill="#ff8c69">Stil Diva</text></svg></div>""", unsafe_allow_html=True)
        st.title(f'Hoşgeldin *{name}*')
        st.title("Yönetim Paneli")
        authenticator.logout('Çıkış Yap', 'main')
        st.markdown("---")

        # --- GÜNCELLENDİ: TEMA SEÇİM BUTONLARI ---
        st.write("Tema Seçimi:")
        col1, col2 = st.columns(2)
        with col1:
            # Sadece ikon, metin yok
            if st.button("☀️", use_container_width=True, help="Açık Mod"):
                st.session_state.theme = "light"
                st.rerun()
        with col2:
            # Sadece ikon, metin yok
            if st.button("🌙", use_container_width=True, help="Koyu Mod"):
                st.session_state.theme = "dark"
                st.rerun()
        
        st.markdown("---")
        
        # --- GÜNCELLENDİ: SİHİRBAZLAR BAŞLIĞI VE SEÇİCİ ---
        st.subheader("Sihirbazlar")
        app_mode = st.selectbox(
            "Hangi aracı kullanmak istersiniz?", 
            ["Kârlılık Analizi", "Toptan Fiyat Teklifi", "Satış Fiyatı Hesaplayıcı", "Aylık Hedef Analizi", "Maliyet Yönetimi"], 
            label_visibility="collapsed"
        )

    # CSS enjeksiyonunu, butonlar render edildikten sonra yapıyoruz
    inject_custom_css()

    page_map = {
        "Kârlılık Analizi": render_karlilik_analizi,
        "Toptan Fiyat Teklifi": render_toptan_fiyat_teklifi,
        "Satış Fiyatı Hesaplayıcı": render_satis_fiyati_hesaplayici,
        "Aylık Hedef Analizi": render_hedef_analizi,
        "Maliyet Yönetimi": render_maliyet_yonetimi
    }
    page_map[app_mode]()

elif authentication_status is False:
    st.error('Kullanıcı adı/şifre hatalı')
elif authentication_status is None:
    st.warning('Lütfen kullanıcı adı ve şifrenizi girin')
