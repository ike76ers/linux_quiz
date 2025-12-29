import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
import random
import time

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="Linux Master", page_icon="🐧", layout="centered")

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
    Hız sınırına (429) takılırsa otomatik bekler ve tekrar dener.
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
    
    # KOTA DOSTU MODEL LİSTESİ (Lite modeller başta)
    models_to_try = [
        'models/gemini-2.0-flash-lite',         # Hızlı ve hafif
        'models/gemini-2.0-flash-lite-preview', 
        'models/gemini-2.0-flash',              # Standart hızlı
        'models/gemini-2.0-flash-exp'
    ]

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.7
    }
    
    error_log = []

    for model_name in models_to_try:
        # Her model için 3 kez deneme hakkı verelim (Retry Logic)
        for attempt in range(3): 
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    safety_settings=safety_settings,
                    generation_config=generation_config
                )
                
                response = model.generate_content(prompt)
                
                text_response = response.text.strip()
                if text_response.startswith("```"):
                    text_response = text_response.split("```")[1]
                    if text_response.startswith("json"):
                        text_response = text_response[4:]
                
                quiz_data = json.loads(text_response)
                return quiz_data # Başarılıysa çık

            except Exception as e:
                error_msg = str(e)
                
                # Eğer hata "429" (Hız Limiti) ise bekle
                if "429" in error_msg or "quota" in error_msg.lower():
                    wait_time = 10  # 10 saniye bekle
                    st.toast(f"⏳ Hız limitine takıldık. {wait_time} saniye bekleniyor... (Model: {model_name})")
                    time.sleep(wait_time)
                    continue # Aynı modeli tekrar dene
                
                # Başka bir hataysa kaydet ve sonraki modele geç
                print(f"Model {model_name} başarısız: {error_msg}")
                error_log.append(f"{model_name}: {error_msg}")
                break # Bu model bozuk, diğer modele geç
            
    # Hiçbiri çalışmazsa
    st.error("⚠️ Soru üretilemedi. (Tüm modeller ve denemeler başarısız oldu)")
    with st.expander("Hata Detaylarını Gör"):
        for err in error_log:
            st.write(err)
    return []

# --- 3. ARAYÜZ ---

st.title("🐧 Linux Sınavı")

# State
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
                    with st.spinner("Sorular hazırlanıyor... (Hız limiti kontrol ediliyor)"):
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

    except Exception as e:
        st.error(f"Dosya hatası: {e}")

# --- 4. GÖRSEL ALAN ---

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
