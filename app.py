import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
import random
import time

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="Linux Master", page_icon="🐧", layout="centered")

# CSS: Görünüm İyileştirmeleri
st.markdown("""
    <style>
    .stRadio label { font-size: 18px !important; }
    div[data-testid="stVerticalBlock"] > div { margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# API Anahtarı
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except FileNotFoundError:
    st.error("⚠️ API Anahtarı Bulunamadı! Lütfen Secrets ayarlarını kontrol edin.")
    st.stop()
except Exception as e:
    st.error(f"Bir hata oluştu: {e}")
    st.stop()

# --- 2. FONKSİYONLAR ---

def get_gemini_quiz(selected_commands):
    """
    Gemini API'den soru üretir.
    - Güvenlik filtreleri gevşetildi (Linux komutları için).
    - JSON formatı zorlandı.
    """
    commands_text = ", ".join(selected_commands)

    prompt = f"""
    You are an expert Linux Instructor. 
    I will provide a list of Linux commands.
    
    Your task:
    1. Identify what each command does based on your own knowledge.
    2. Create a quiz with exactly {len(selected_commands)} questions.
    3. Mix "multiple_choice" and "fill_in_the_blank" types.
    
    The Commands are: [{commands_text}]
    
    Rules:
    - For "multiple_choice", provide 4 options.
    - For "fill_in_the_blank", describe the action and ask for the specific command.
    - The content must be in TURKISH language.
    - RETURN ONLY VALID JSON.
    
    JSON Structure Example:
    [
        {{
            "id": 1,
            "type": "multiple_choice",
            "question": "'ls -la' komutu ne işe yarar?",
            "options": ["Seçenek A", "Seçenek B", "Seçenek C", "Seçenek D"],
            "answer": "Doğru olan seçenek metni"
        }}
    ]
    """
    
    # Sizin hesabınızda aktif olan modeller (Öncelik sırasına göre)
    models_to_try = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-exp',
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest'
    ]

    # Güvenlik Ayarları: Linux komutlarının engellenmemesi için 'BLOCK_NONE' yapıyoruz.
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # JSON Modu Konfigürasyonu
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.7
    }
    
    last_error = ""

    for model_name in models_to_try:
        try:
            # Model ismini tamir et (Başına models/ ekleyerek veya eklemeyerek dene)
            full_model_name = model_name if "models/" in model_name else f"models/{model_name}"
            
            model = genai.GenerativeModel(
                model_name=full_model_name,
                safety_settings=safety_settings,
                generation_config=generation_config
            )
            
            response = model.generate_content(prompt)
            
            # Yanıtı temizle ve JSON'a çevir
            text_response = response.text.strip()
            # Bazen başında ```json yazar, onları temizleyelim
            if text_response.startswith("```"):
                text_response = text_response.split("```")[1]
                if text_response.startswith("json"):
                    text_response = text_response[4:]
            
            quiz_data = json.loads(text_response)
            return quiz_data

        except Exception as e:
            last_error = str(e)
            # Hata detayını terminale yaz (debug için)
            print(f"Model {model_name} başarısız oldu: {e}")
            continue
            
    st.error(f"⚠️ Soru üretilemedi. Hata Detayı: {last_error}")
    st.info("İpucu: Eğer '429' hatası görüyorsanız kotanız dolmuştur. 'FinishReason.SAFETY' görüyorsanız komutlar zararlı algılanmıştır.")
    return []

# --- 3. ARAYÜZ VE STATE YÖNETİMİ ---

st.title("🐧 Linux Sınavı")

# State Tanımları
if 'quiz_data' not in st.session_state: st.session_state['quiz_data'] = None
if 'submitted' not in st.session_state: st.session_state['submitted'] = False
if 'user_answers' not in st.session_state: st.session_state['user_answers'] = {}
if 'available_indices' not in st.session_state: st.session_state['available_indices'] = []
if 'all_commands' not in st.session_state: st.session_state['all_commands'] = []

uploaded_file = st.file_uploader("Excel Dosyası (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        if 'uploaded_file_name' not in st.session_state or st.session_state.get('uploaded_file_name') != uploaded_file.name:
            df = pd.read_excel(uploaded_file)
            if "Command" not in df.columns:
                st.error("HATA: Excel dosyasında 'Command' sütunu bulunamadı.")
                st.stop()
            
            st.session_state['df'] = df
            st.session_state['uploaded_file_name'] = uploaded_file.name
            st.session_state['all_commands'] = df['Command'].tolist()
            st.session_state['available_indices'] = list(range(len(df)))
            
            st.success(f"✅ Dosya yüklendi! {len(df)} komut havuza eklendi.")
            st.session_state['quiz_data'] = None

        total_cmds = len(st.session_state['all_commands'])
        remaining_cmds = len(st.session_state['available_indices'])
        progress = 1.0 - (remaining_cmds / total_cmds) if total_cmds > 0 else 0
        
        st.divider()
        st.write(f"📊 **İlerleme:** {total_cmds - remaining_cmds} / {total_cmds}")
        st.progress(progress)

        if remaining_cmds == 0:
            st.success("🎉 Tebrikler! Tüm sorular bitti.")
            if st.button("🔄 Başa Dön"):
                st.session_state['available_indices'] = list(range(total_cmds))
                st.rerun()
        else:
            if st.session_state['quiz_data'] is None:
                st.subheader("⚙️ Sınav Ayarları")
                max_limit_input = 15
                slider_max = min(remaining_cmds, max_limit_input)
                num_questions = st.slider("Soru Sayısı:", 1, slider_max, min(5, slider_max))

                if st.button(f"🚀 {num_questions} Soru Getir"):
                    with st.spinner("Sorular hazırlanıyor... (Linux komutları işleniyor)"):
                        selected_indices = random.sample(st.session_state['available_indices'], num_questions)
                        selected_commands = [st.session_state['all_commands'][i] for i in selected_indices]
                        
                        quiz_data = get_gemini_quiz(selected_commands)
                        
                        if quiz_data:
                            for idx in selected_indices:
                                st.session_state['available_indices'].remove(idx)
                            st.session_state['quiz_data'] = quiz_data
                            st.session_state['user_answers'] = {}
                            st.session_state['submitted'] = False
                            st.rerun()
                        # Hata mesajı artık fonksiyonun içinden geliyor

    except Exception as e:
        st.error(f"Dosya hatası: {e}")

# --- 4. GÖRSEL OLARAK İYİLEŞTİRİLMİŞ SINAV ALANI ---

if st.session_state.get('quiz_data'):
    st.divider()
    st.subheader("📝 Sorular")
    
    with st.form(key='quiz_form'):
        
        for i, q in enumerate(st.session_state['quiz_data']):
            with st.container(border=True):
                st.info(f"**Soru {i+1}:** {q['question']}")
                
                if q['type'] == 'multiple_choice':
                    st.session_state['user_answers'][i] = st.radio(
                        "Cevabınız:", 
                        q['options'], 
                        key=f"q_{i}", 
                        index=None
                    )
                elif q['type'] == 'fill_in_the_blank':
                    st.session_state['user_answers'][i] = st.text_input(
                        "Cevabınızı buraya yazın:", 
                        key=f"q_{i}"
                    )
        
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button("✅ Cevapları Kontrol Et", use_container_width=True)

    if submit_button:
        st.session_state['submitted'] = True
        score = 0
        total = len(st.session_state['quiz_data'])
        
        st.markdown("### 📊 Sonuçlar")
        
        for i, q in enumerate(st.session_state['quiz_data']):
            user_ans = str(st.session_state['user_answers'].get(i, "")).strip()
            correct_ans = str(q['answer']).strip()
            
            with st.container(border=True):
                st.markdown(f"**Soru {i+1}:** {q['question']}")
                
                if user_ans.lower() == correct_ans.lower():
                    score += 1
                    st.success(f"✅ Doğru! (Cevabın: {user_ans})")
                else:
                    st.error(f"❌ Yanlış.")
                    st.write(f"Senin cevabın: **{user_ans if user_ans else '(Boş)'}**")
                    st.warning(f"Doğru cevap: **{correct_ans}**")
        
        st.divider()
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.metric("TOPLAM PUAN", f"{score} / {total}", delta=f"%{(score/total)*100:.0f} Başarı")
            
        if score == total:
             st.balloons()
        
        if st.button("Sonraki Tura Geç ➡️"):
            st.session_state['quiz_data'] = None
            st.session_state['submitted'] = False
            st.rerun()
