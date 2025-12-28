import streamlit as st
import google.generativeai as genai

st.title("🕵️ Hata Tespit Ekranı")

# 1. Secrets Kontrolü
st.write("1. Secrets kontrol ediliyor...")
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.success(f"✅ Anahtar bulundu! İlk 5 harf: {api_key[:5]}...")
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ Secrets Okuma Hatası: {e}")
    st.warning("Lütfen Secrets kısmında 'GOOGLE_API_KEY = \"sifreniz\"' yazdığından emin olun.")
    st.stop()

# 2. Google Bağlantı Kontrolü
st.write("2. Google sunucularına bağlanılıyor...")
try:
    # Basit bir model listeleme isteği
    models = list(genai.list_models())
    st.success(f"✅ Bağlantı Başarılı! Google {len(models)} adet model listeledi.")
    
    # Modelleri ekrana yaz
    st.write("Bulunan Modeller:")
    for m in models:
        st.text(m.name)
        
except Exception as e:
    st.error("❌ Google API Hatası!")
    st.code(str(e)) # Gerçek hata mesajını ekrana basar
    st.info("Eğer hata '400' veya 'INVALID_ARGUMENT' ise API Key yanlıştır/kopyalanırken bozulmuştur.")
