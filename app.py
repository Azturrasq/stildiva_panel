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

# ==============================================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================================

def get_google_creds():
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sa = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(sa)
    except (KeyError, FileNotFoundError):
        if os.path.exists("secrets.json"):
            sa = Credentials.from_service_account_file("secrets.json", scopes=scopes)
            return gspread.authorize(sa)
        else:
            st.error("KRİTİK HATA: Kimlik bilgisi dosyası ('secrets.json' veya Cloud secrets) bulunamadı.")
            st.stop()

@st.cache_data(ttl=600)
def load_cost_data_from_gsheets(_gc):
    try:
        workbook = _gc.open("maliyet_referans")
        worksheet = workbook.worksheet("Sayfa1")
        df = get_as_dataframe(worksheet, evaluate_formulas=True)
        df['Barkod'] = df['Barkod'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df['Model Kodu'] = df['Model Kodu'].astype(str).str.strip()
        df['Alış Fiyatı'] = pd.to_numeric(df['Alış Fiyatı'], errors='coerce')
        return df.dropna(subset=['Alış Fiyatı'])
    except Exception as e:
        st.error(f"Google Sheets'ten maliyet verisi okunurken hata: {e}")
        return pd.DataFrame()

def load_cost_data():
    if 'gc' not in st.session_state:
        st.session_state.gc = get_google_creds()
    st.session_state.df_maliyet = load_cost_data_from_gsheets(st.session_state.gc)

# --- HATA DÜZELTME: EKSİK OLAN KÂR HESAPLAMA FONKSİYONU ---
def kar_hesapla(satis_fiyati_kdvli, alis_fiyati_kdvsiz, komisyon_orani, kdv_orani, kargo_gideri, reklam_gideri):
    """Tek bir ürün için kâr hesaplaması yapar."""
    kdv_bolen = 1 + (kdv_orani / 100)
    kdv_carpan = kdv_orani / 100
    
    satis_fiyati_kdvsiz = satis_fiyati_kdvli / kdv_bolen
    satis_kdv_tutari = satis_fiyati_kdvli - satis_fiyati_kdvsiz
    alis_kdv_tutari = alis_fiyati_kdvsiz * kdv_carpan
    net_odenecek_kdv = satis_kdv_tutari - alis_kdv_tutari
    komisyon_tutari = satis_fiyati_kdvli * (komisyon_orani / 100)
    
    toplam_maliyet = alis_fiyati_kdvsiz + kargo_gideri + reklam_gideri + komisyon_tutari + net_odenecek_kdv
    net_kar = satis_fiyati_kdvsiz - toplam_maliyet
    kar_marji = (net_kar / satis_fiyati_kdvsiz) * 100 if satis_fiyati_kdvsiz > 0 else 0
    
    return {
        'net_kar': net_kar, 
        'kar_marji': kar_marji, 
        'toplam_maliyet': toplam_maliyet
    }

# ==============================================================================
# SAYFA RENDER FONKSİYONLARI
# ==============================================================================

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

        # --- YENİ: Boş DataFrame kontrolü ---
        # Eğer yüklenen Excel'de geçerli tarih içeren hiçbir satır yoksa,
        # df_siparis_orjinal boş olur ve hata verir. Bunu burada engelliyoruz.
        if df_siparis_orjinal.empty:
            st.error("Yüklenen Excel dosyasında geçerli 'Sipariş Tarihi' içeren hiçbir sipariş bulunamadı. Lütfen dosyanızı kontrol edin.")
            return # Fonksiyonun geri kalanını çalıştırmayı durdur

        # Filtreleme Kartı
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🔍 Filtreleme Seçenekleri")
        filt_col1, filt_col2 = st.columns([1, 2])

        with filt_col1:
            min_tarih = df_siparis_orjinal['Sipariş Tarihi'].min().date()
            maks_tarih = df_siparis_orjinal['Sipariş Tarihi'].max().date()
            
            secilen_tarih_araligi = st.date_input(
                "Tarih Aralığı Seçin", value=(min_tarih, maks_tarih),
                min_value=min_tarih, max_value=maks_tarih, key='tarih_filtresi'
            )
            
            if len(secilen_tarih_araligi) != 2:
                st.warning("Lütfen bir başlangıç ve bitiş tarihi seçin.")
                st.stop()
            
            secilen_baslangic, secilen_bitis = secilen_tarih_araligi

        with filt_col2:
            platformlar = sorted(df_siparis_orjinal['Platform'].unique())
            secilen_platformlar = st.multiselect(
                "Platforma Göre Filtrele", options=platformlar,
                default=platformlar, key='platform_filtresi'
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Analiz Parametreleri Kartı
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

        # --- KESİN ÇÖZÜM: Kapsamlı Barkod Temizliği ---
        # Farklı kaynaklardan gelen (Excel ve Google Sheets) barkod formatlarını
        # birleştirmeden önce standart hale getiriyoruz.
        
        # 1. Sipariş DataFrame'ini (Excel'den gelen) temizle
        df_siparis['Barkod'] = df_siparis['Barkod'].astype(str) # Önce metne çevir
        df_siparis['Barkod'] = df_siparis['Barkod'].str.replace(r'\.0$', '', regex=True) # Sonundaki ".0" uzantısını kaldır
        df_siparis['Barkod'] = df_siparis['Barkod'].str.strip() # Olası boşlukları temizle

        # 2. Maliyet DataFrame'ini (Google Sheets'ten gelen) temizle
        df_maliyet['Barkod'] = df_maliyet['Barkod'].astype(str)
        df_maliyet['Barkod'] = df_maliyet['Barkod'].str.replace(r'\.0$', '', regex=True)
        df_maliyet['Barkod'] = df_maliyet['Barkod'].str.strip()

        # Artık formatları eşit olan tabloları birleştir
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
    load_cost_data() # Veriyi yükle

    # --- YENİ ÜRÜN EKLEME KARTI ---
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("➕ Yeni Ürün Ekle")
        with st.form("yeni_urun_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            yeni_model = f_col1.text_input("Yeni Ürün Model Kodu")
            yeni_barkod = f_col2.text_input("Yeni Ürün Barkodu")
            yeni_alis = f_col3.number_input("Yeni Ürün Alış Fiyatı (KDV Hariç)", min_value=0.0, format="%.2f")
            
            if st.form_submit_button("Yeni Ürünü Ekle") and yeni_barkod and yeni_model:
                yeni_veri = pd.DataFrame([{"Model Kodu": yeni_model, "Barkod": yeni_barkod, "Alış Fiyatı": yeni_alis}])
                # Önce session state'i güncelle
                st.session_state.df_maliyet = pd.concat([st.session_state.df_maliyet, yeni_veri], ignore_index=True).drop_duplicates(subset=['Barkod'], keep='last')
                st.success(f"'{yeni_barkod}' barkodlu ürün eklendi. Değişikliklerin kalıcı olması için aşağıdaki butona tıklayarak Google Sheets'e kaydedin.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- MEVCUT MALİYETLERİ DÜZENLEME KARTI (GÜNCELLENDİ) ---
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("✏️ Mevcut Maliyetleri Düzenle")
        
        # Data editor ile düzenleme yap
        edited_df = st.data_editor(
            st.session_state.df_maliyet, 
            num_rows="dynamic", 
            use_container_width=True, 
            key="maliyet_editor"
        )

        # Buton artık Google Sheets'e kaydedecek
        if st.button("💾 Değişiklikleri Google Sheets'e Kaydet"):
            try:
                # --- GÜNCELLENDİ: Tüm karmaşık blok yerine tek fonksiyon çağrısı ---
                gc = get_google_creds()
                
                # Doğru dosyayı ve sayfayı aç
                workbook = gc.open("maliyet_referans")
                worksheet = workbook.worksheet("Sayfa1")
                
                # Değiştirilmiş DataFrame'i Google Sheets'e yaz
                set_with_dataframe(worksheet, edited_df)
                
                # Lokal state'i de güncelle
                st.session_state.df_maliyet = edited_df.copy()
                
                st.success("Değişiklikler başarıyla Google Sheets'e kaydedildi!")
                st.balloons() # Başarıyı kutla!

            except Exception as e:
                st.error(f"Google Sheets'e yazılırken bir hata oluştu: {e}")
        
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

# --- ESKİ SATIŞ FİYATI HESAPLAYICI FONKSİYONU SİLİNDİ ---


# --- SİLİNEN VE BOZUK OLAN TOPTAN FİYAT TEKLİFİ FONKSİYONU BURAYA DOĞRU ŞEKİLDE EKLENİYOR ---
def render_toptan_fiyat_teklifi():
    st.title("📑 Toplu Fiyat Listesi Oluşturucu")
    st.info("Bu araç, Google Sheets'teki tüm ürünleriniz için belirlediğiniz hedeflere göre toplu bir satış fiyatı listesi oluşturur.")

    # 1. Maliyet verilerini yükle
    load_cost_data()
    df_maliyet = st.session_state.df_maliyet.copy()

    if df_maliyet.empty:
        st.error("Maliyet verileri yüklenemedi. Lütfen Google Sheets bağlantınızı veya 'Maliyet Yönetimi' sayfasını kontrol edin.")
        return

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        st.subheader("Satış Parametreleri (Tüm Ürünlere Uygulanacak)")
        col1, col2 = st.columns(2)

        with col1:
            komisyon_orani = st.number_input("Komisyon Oranı (%)", min_value=0.0, value=21.5, step=0.1, key="toptan_komisyon")
            urun_kdv_orani = st.number_input("Ürün Satış KDV Oranı (%)", min_value=0.0, value=10.0, step=1.0, key="toptan_kdv")

        with col2:
            hedef_tipi = st.selectbox("Hedef Türü", ["% Kâr Marjı", "Net Kâr Tutarı (TL)"], key="toptan_hedef_tipi")
            if hedef_tipi == "% Kâr Marjı":
                hedef_deger = st.number_input("Hedef Kâr Marjı (%)", min_value=0.0, max_value=99.9, value=25.0, step=0.5, key="toptan_hedef_deger_marj")
            else:
                hedef_deger = st.number_input("Hedef Net Kâr (TL)", min_value=0.0, value=100.0, step=1.0, key="toptan_hedef_deger_tutar")

        if st.button("Fiyat Listesini Oluştur", type="primary", use_container_width=True):
            # --- DÜZELTME: Sadece benzersiz model kodları ile çalış ---
            df_hesaplama = df_maliyet.drop_duplicates(subset=['Model Kodu']).copy()

            kdv_carpan = urun_kdv_orani / 100
            kdv_bolen = 1 + kdv_carpan
            
            alis_fiyati_kdvsiz = df_hesaplama['Alış Fiyatı']
            alis_kdv_tutari = alis_fiyati_kdvsiz * kdv_carpan
            
            if hedef_tipi == "% Kâr Marjı":
                hedef_kar_marji = hedef_deger / 100
                pay = alis_fiyati_kdvsiz - alis_kdv_tutari
                payda = 1 - hedef_kar_marji - (kdv_bolen * (komisyon_orani/100)) - kdv_carpan
            else: # Hedef Net Kâr (TL)
                hedef_net_kar = hedef_deger
                pay = alis_fiyati_kdvsiz - alis_kdv_tutari + hedef_net_kar
                payda = 1 - (kdv_bolen * (komisyon_orani / 100)) - kdv_carpan

            if payda <= 0:
                st.error("Bu hedefe ulaşılamıyor. Lütfen komisyon veya kâr hedefini düşürün.")
            else:
                satis_fiyati_kdvsiz = pay / payda
                satis_fiyati_kdvli = satis_fiyati_kdvsiz * kdv_bolen
                
                # --- DÜZELTME: İstenen sütunlarla yeni bir sonuç DataFrame'i oluştur ---
                df_sonuc = pd.DataFrame({
                    'Model Kodu': df_hesaplama['Model Kodu'],
                    'Alış Fiyatı (KDV Hariç)': df_hesaplama['Alış Fiyatı'],
                    'Satış Fiyatı (KDV Hariç)': satis_fiyati_kdvsiz,
                    'Satış Fiyatı (KDV Dahil)': satis_fiyati_kdvli
                })

                kar_sonuclari = df_sonuc.apply(
                    lambda row: kar_hesapla(
                        row['Satış Fiyatı (KDV Dahil)'], 
                        row['Alış Fiyatı (KDV Hariç)'], 
                        komisyon_orani, urun_kdv_orani, 0, 0
                    ), axis=1, result_type='expand'
                )
                kar_sonuclari.columns = ['Net Kar', 'Kar Marjı', 'Toplam Maliyet']
                
                df_sonuc = pd.concat([df_sonuc, kar_sonuclari[['Net Kar', 'Kar Marjı']]], axis=1)

                st.subheader("Oluşturulan Fiyat Listesi")
                st.dataframe(
                    df_sonuc.style.format({
                        'Alış Fiyatı (KDV Hariç)': '{:,.2f} TL',
                        'Satış Fiyatı (KDV Hariç)': '{:,.2f} TL',
                        'Satış Fiyatı (KDV Dahil)': '{:,.2f} TL',
                        'Net Kar': '{:,.2f} TL',
                        'Kar Marjı': '{:.2f}%'
                    }),
                    use_container_width=True
                )
        st.markdown('</div>', unsafe_allow_html=True)

# --- YENİ VE EXCEL İLE UYUMLU SİHİRBAZ FONKSİYONU ---
def render_yeni_urun_sihirbazi():
    st.title("🧙‍♂️ Yeni Ürün Satış Fiyatı Sihirbazı")

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        with st.form("yeni_urun_sihirbazi_formu"):
            st.subheader("📊 Maliyet Girdileri")
            
            urun_kdv_orani = st.number_input("Ürünün KDV Oranı (%)", min_value=0.0, value=10.0, step=1.0, key="sihirbaz_kdv")
            komisyon_orani = st.number_input("Platform Komisyon Oranı (%)", min_value=0.0, value=21.5, step=0.1, key="sihirbaz_komisyon")
            alis_fiyati_input = st.number_input("Ürün Alış Fiyatı (TL)", min_value=0.0, value=270.0, step=0.01, key="sihirbaz_alis")
            kdv_durumu = st.radio("Alış Fiyatı KDV Durumu", ["KDV Dahil", "KDV Hariç"], index=1, horizontal=True, key="sihirbaz_kdv_durum")
            kargo_gideri = st.number_input("Kargo Gideri (TL)", min_value=0.0, value=80.0, step=0.5, key="sihirbaz_kargo")
            reklam_gideri = st.number_input("Birim Reklam Gideri (TL)", min_value=0.0, value=30.0, step=0.1, key="sihirbaz_reklam")
            
            st.markdown("---")

            # --- DÜZELTME: Mantıksal akış için hedef belirleme bölümü aşağı taşındı ---
            st.subheader("🎯 Fiyat ve Hedef Belirleme")
            hesaplama_tipi = st.radio(
                "Hesaplama Yönü Seçin",
                ["Hedefe Göre Satış Fiyatı Bul", "Satış Fiyatına Göre Kâr Hesapla"],
                index=1,
                key="sihirbaz_hesaplama_tipi"
            )

            # Dinamik olarak gösterilen girdi alanları
            if hesaplama_tipi == "Hedefe Göre Satış Fiyatı Bul":
                hedef_tipi = st.selectbox("Hedef Türü", ["% Kâr Marjı", "Net Kâr Tutarı (TL)"], key="sihirbaz_hedef_tipi")
                if hedef_tipi == "% Kâr Marjı":
                    hedef_deger = st.number_input("Hedef Kâr Marjı (%)", min_value=0.0, max_value=99.9, value=25.0, step=0.5, key="sihirbaz_hedef_marj")
                else:
                    hedef_deger = st.number_input("Hedef Net Kâr (TL)", min_value=0.0, value=100.0, step=1.0, key="sihirbaz_hedef_tutar")
            else: # Satış Fiyatına Göre Kâr Hesapla
                satis_fiyati_input = st.number_input("Satış Fiyatı (KDV Dahil)", min_value=0.01, value=899.95, step=0.01, key="sihirbaz_satis_fiyati")
            
            submitted = st.form_submit_button("🔮 Sihirbazı Çalıştır", type="primary", use_container_width=True)

        if submitted:
            # --- HESAPLAMA MANTIĞI ---
            kdv_carpan = urun_kdv_orani / 100
            kdv_bolen = 1 + kdv_carpan

            if kdv_durumu == "KDV Dahil":
                alis_fiyati_kdvsiz = alis_fiyati_input / kdv_bolen
            else:
                alis_fiyati_kdvsiz = alis_fiyati_input
            
            if hesaplama_tipi == "Hedefe Göre Satış Fiyatı Bul":
                sabit_giderler = alis_fiyati_kdvsiz + kargo_gideri + reklam_gideri
                alis_kdv_tutari = alis_fiyati_kdvsiz * kdv_carpan

                if hedef_tipi == "% Kâr Marjı":
                    hedef_kar_marji = hedef_deger / 100
                    pay = sabit_giderler - alis_kdv_tutari
                    payda = 1 - hedef_kar_marji - (kdv_bolen * (komisyon_orani / 100)) - kdv_carpan
                else: # Hedef Net Kâr (TL)
                    hedef_net_kar = hedef_deger
                    pay = sabit_giderler - alis_kdv_tutari + hedef_net_kar
                    payda = 1 - (kdv_bolen * (komisyon_orani / 100)) - kdv_carpan

                if payda <= 0:
                    st.error("Bu hedefe ulaşılamıyor. Lütfen komisyon veya kâr hedefini düşürün.")
                    satis_fiyati_kdvli = 0
                else:
                    satis_fiyati_kdvsiz = pay / payda
                    satis_fiyati_kdvli = satis_fiyati_kdvsiz * kdv_bolen
            
            else: # Satış Fiyatına Göre Kâr Hesapla
                satis_fiyati_kdvli = satis_fiyati_input

            sonuclar = kar_hesapla(satis_fiyati_kdvli, alis_fiyati_kdvsiz, komisyon_orani, urun_kdv_orani, kargo_gideri, reklam_gideri)
            net_kar = sonuclar['net_kar']
            kar_marji = sonuclar['kar_marji']

            st.subheader("Sonuç")
            if net_kar > 0:
                st.success("Bu satıştan kâr ediyorsunuz.")
            else:
                st.error("Bu satıştan zarar ediyorsunuz.")
            
            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric("Satış Fiyatı (KDV Dahil)", f"{satis_fiyati_kdvli:,.2f} TL")
            res_col2.metric("Net Kâr / Zarar", f"{net_kar:,.2f} TL")
            res_col3.metric("Kâr Marjı", f"{kar_marji:.2f}%")

        st.markdown('</div>', unsafe_allow_html=True)

# --- KULLANICI GİRİŞİ ---
# config.yaml dosyasını oku (Streamlit Cloud'da kök dizinde olmalı)
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Kimlik doğrulayıcıyı oluştur
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- GÜNCELLENDİ: Yeni Kimlik Doğrulama Akışı ---
# 1. Giriş formunu çiz. Bu fonksiyon artık bir şey döndürmüyor.
authenticator.login(location='main')

# 2. Giriş durumunu st.session_state üzerinden kontrol et.
if st.session_state["authentication_status"]:
    # --- ANA UYGULAMA AKIŞI ---
    with st.sidebar:
        # Logo ve diğer bileşenler buraya gelecek
        try:
            st.image("logo.png", width=200)
        except Exception as e:
            st.warning("logo.png dosyası bulunamadı.")

        # Hoşgeldin mesajı ve çıkış butonu
        st.write(f'Hoşgeldin *{st.session_state["name"]}*')
        authenticator.logout('Çıkış Yap', 'main')
        st.markdown("---")

        # Sihirbazlar bölümü
        st.subheader("Sihirbazlar")
        app_mode = st.selectbox(
            "Hangi aracı kullanmak istersiniz?",
            ["🧙‍♂️ Yeni Ürün Sihirbazı", "Toptan Fiyat Teklifi", "Kârlılık Analizi", "Aylık Hedef Analizi", "Maliyet Yönetimi"],
            label_visibility="collapsed"
        )

    # --- HATA DÜZELTME: Olmayan CSS fonksiyonu çağrısı kaldırıldı ---
    page_map = {
        "Kârlılık Analizi": render_karlilik_analizi,
        "Toptan Fiyat Teklifi": render_toptan_fiyat_teklifi,
        "Aylık Hedef Analizi": render_hedef_analizi,
        "Maliyet Yönetimi": render_maliyet_yonetimi,
        "🧙‍♂️ Yeni Ürün Sihirbazı": render_yeni_urun_sihirbazi
    }
    page_map[app_mode]()

elif st.session_state["authentication_status"] is False:
    st.error('Kullanıcı adı/şifre yanlış')
elif st.session_state["authentication_status"] is None:
    st.warning('Lütfen kullanıcı adı ve şifrenizi girin')

# Yeni Ürün Sihirbazı modülü - ana menüye eklenecek
def yeni_urun_sihirbazi():
    st.header("🧙‍♂️ Yeni Ürün Sihirbazı")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Maliyet Bilgileri")
        
        # KDV Oranı
        kdv_orani = st.number_input("KDV Oranı (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.1)
        
        # Kargo Gideri
        kargo_gideri = st.number_input("Kargo Gideri (TL)", min_value=0.0, value=80.0, step=0.5)
        
        # Reklam Gideri
        reklam_gideri = st.number_input("Reklam Gideri (TL)", min_value=0.0, value=0.0, step=0.1)
    
    with col2:
        st.subheader("📦 Ürün Bilgileri")
        
        # Model Kodu
        model_kodu = st.text_input("Model Kodu")
        
        # Barkod
        barkod = st.text_input("Barkod")
        
        # Alış Fiyatı
        alis_fiyati = st.number_input("Alış Fiyatı (KDV Hariç)", min_value=0.0, step=0.01)
    
    # Ürün bilgileri girildikten sonra maliyet hesaplama
    if st.button("💰 Maliyeti Hesapla"):
        if not model_kodu or not barkod:
            st.error("Model Kodu ve Barkod alanları boş bırakılamaz.")
        else:
            # KDV Dahil Alış Fiyatı
            kdv_dahil_alis_fiyati = alis_fiyati * (1 + kdv_orani / 100)
            
            # Sonuçları göster
            st.subheader("📈 Hesaplanan Maliyet")
            st.write(f"**Model Kodu:** {model_kodu}")
            st.write(f"**Barkod:** {barkod}")
            st.write(f"**KDV Dahil Alış Fiyatı:** {kdv_dahil_alis_fiyati:.2f} TL")
            st.write(f"**Kargo Gideri:** {kargo_gideri:.2f} TL")
            st.write(f"**Reklam Gideri:** {reklam_gideri:.2f} TL")
            
            # Toplam maliyet
            toplam_maliyet = alis_fiyati + kargo_gideri + reklam_gideri
            st.write(f"**Toplam Maliyet:** {toplam_maliyet:.2f} TL")
            
            # Kâr marjı hesaplama
            kar_marji = 100 * (toplam_maliyet - alis_fiyati) / toplam_maliyet
            st.write(f"**Kâr Marjı:** {kar_marji:.2f}%")
            
            # Kâr hesaplama
            net_kar = toplam_maliyet - alis_fiyati
            st.write(f"**Net Kâr:** {net_kar:.2f} TL")
            
            # Komisyon
            komisyon = st.session_state.get('tekil_komisyon', 21.5)
            komisyon_tutari = alis_fiyati * (komisyon / 100)
            st.write(f"**Komisyon (%{komisyon}):** {komisyon_tutari:.2f} TL")
            
            # Nihai Kâr
            nihai_kar = net_kar - komisyon_tutari
            st.write(f"**Nihai Kâr:** {nihai_kar:.2f} TL")
            
            # Ürün kaydetme seçenekleri
            if st.button("✅ Ürünü Kaydet"):
                # Mevcut maliyet verileriyle birleştir
                yeni_urun = pd.DataFrame([{
                    "Model Kodu": model_kodu,
                    "Barkod": barkod,
                    "Alış Fiyatı": alis_fiyati,
                    "KDV Oranı": kdv_orani,
                    "Kargo Gideri": kargo_gideri,
                    "Reklam Gideri": reklam_gideri
                }])
                
                # Güncel maliyet verileriyle birleştir
                st.session_state.df_maliyet = pd.concat([st.session_state.df_maliyet, yeni_urun], ignore_index=True).drop_duplicates(subset=['Barkod'], keep='last')
                
                # Google Sheets'e kaydet
                try:
                    gc = get_google_creds()
                    workbook = gc.open("maliyet_referans")
                    worksheet = workbook.worksheet("Sayfa1")
                    set_with_dataframe(worksheet, st.session_state.df_maliyet, reindex=True)
                    st.success("Yeni ürün başarıyla kaydedildi ve Google Sheets'e aktarıldı.")
                except Exception as e:
                    st.error(f"Google Sheets'e kaydedilirken hata oluştu: {e}")
