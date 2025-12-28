import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import random

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="Linux Master", page_icon="🐧", layout="centered")

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
    """Gemini API'den soru üretir."""
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
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        quiz_data = json.loads(cleaned_text)
        return quiz_data
    except Exception as e:
        st.error(f"Yapay zeka hata verdi: {e}")
        return []

# --- 3. ARAYÜZ (UI) ---

st.title("🐧 Linux Sınavı")

# Session State Başlangıç Değerleri
if 'quiz_data' not in st.session_state:
    st.session_state['quiz_data'] = None
if 'submitted' not in st.session_state:
    st.session_state['submitted'] = False
if 'user_answers' not in st.session_state:
    st.session_state['user_answers'] = {}
# Havuz sistemi için state
if 'available_indices' not in st.session_state:
    st.session_state['available_indices'] = []
if 'all_commands' not in st.session_state:
    st.session_state['all_commands'] = []

# Dosya Yükleyici
uploaded_file = st.file_uploader("Excel Dosyası (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        # Dosya yeni yüklendiyse veya değiştiyse
        if 'uploaded_file_name' not in st.session_state or st.session_state.get('uploaded_file_name') != uploaded_file.name:
            df = pd.read_excel(uploaded_file)
            if "Command" not in df.columns:
                st.error("HATA: Excel dosyasında 'Command' sütunu bulunamadı.")
                st.stop()
            
            # Verileri kaydet
            st.session_state['df'] = df
            st.session_state['uploaded_file_name'] = uploaded_file.name
            
            # --- HAVUZU DOLDUR ---
            # Tüm komutları listeye alıyoruz
            st.session_state['all_commands'] = df['Command'].tolist()
            # Henüz sorulmamış olanların indekslerini (sıra numaralarını) listeliyoruz
            st.session_state['available_indices'] = list(range(len(df)))
            
            st.success(f"✅ Dosya yüklendi! Toplam {len(df)} komut havuza eklendi.")
            # Eski sınavı temizle
            st.session_state['quiz_data'] = None

        # İlerleme Çubuğu (Progress Bar)
        total_cmds = len(st.session_state['all_commands'])
        remaining_cmds = len(st.session_state['available_indices'])
        progress = 1.0 - (remaining_cmds / total_cmds) if total_cmds > 0 else 0
        
        st.divider()
        st.write(f"📊 **İlerleme Durumu:** {total_cmds - remaining_cmds} / {total_cmds} tamamlandı")
        st.progress(progress)

        if remaining_cmds == 0:
            st.warning("🎉 Tebrikler! Listedeki tüm komutları bitirdiniz.")
            if st.button("🔄 Listeyi Sıfırla ve Başa Dön"):
                st.session_state['available_indices'] = list(range(total_cmds))
                st.rerun() # Sayfayı yenile
        else:
            # --- SORU SEÇİMİ ---
            st.subheader("⚙️ Sınav Ayarları")
            
            # Slider max değeri, kalan soru sayısı ile sınırlı
            max_limit_input = 15
            slider_max = min(remaining_cmds, max_limit_input)
            
            num_questions = st.slider(
                "Bu turda kaç soru gelsin?", 
                min_value=1, 
                max_value=slider_max, 
                value=min(5, slider_max)
            )

            if st.button(f"🚀 {num_questions} Yeni Soru Getir"):
                with st.spinner("Sorular havuzdan çekiliyor ve hazırlanıyor..."):
                    
                    # 1. Havuzdan rastgele indeksler seç (Seçilenleri silmek üzere)
                    selected_indices = random.sample(st.session_state['available_indices'], num_questions)
                    
                    # 2. Seçilen indeksleri havuzdan SİL (Bir daha gelmesin diye)
                    for idx in selected_indices:
                        st.session_state['available_indices'].remove(idx)
                    
                    # 3. İndekslere karşılık gelen komutları bul
                    selected_commands = [st.session_state['all_commands'][i] for i in selected_indices]
                    
                    # 4. API'ye gönder
                    quiz_data = get_gemini_quiz(selected_commands)
                    
                    if quiz_data:
                        st.session_state['quiz_data'] = quiz_data
                        st.session_state['user_answers'] = {}
                        st.session_state['submitted'] = False
                        st.rerun() # Sayfayı yenile ki state otursun
                    else:
                        st.error("Soru üretilemedi. (Lütfen tekrar deneyin)")

    except Exception as e:
        st.error(f"Dosya işlenirken hata: {e}")

# --- 4. SINAV GÖSTERİMİ ---

if st.session_state.get('quiz_data'):
    st.divider()
    st.subheader("📝 Sorular")
    
    form = st.form(key='quiz_form')
    
    for i, q in enumerate(st.session_state['quiz_data']):
        st.markdown(f"#### {i+1}. {q['question']}")
        
        if q['type'] == 'multiple_choice':
            st.session_state['user_answers'][i] = form.radio(
                "Seçenekler:", 
                q['options'], 
                key=f"q_{i}", 
                label_visibility="collapsed"
            )
        elif q['type'] == 'fill_in_the_blank':
            st.session_state['user_answers'][i] = form.text_input(
                "Cevabınız:", 
                key=f"q_{i}"
            )
        st.write("")
    
    submit_button = form.form_submit_button("✅ Cevapları Kontrol Et")

    if submit_button:
        st.session_state['submitted'] = True
        score = 0
        total = len(st.session_state['quiz_data'])
        
        st.divider()
        st.markdown("### 📊 Bu Turun Sonucu")
        
        for i, q in enumerate(st.session_state['quiz_data']):
            user_ans = str(st.session_state['user_answers'].get(i, "")).strip()
            correct_ans = str(q['answer']).strip()
            
            if user_ans.lower() == correct_ans.lower():
                score += 1
                st.success(f"**Soru {i+1}:** Doğru! 👏")
            else:
                st.error(f"**Soru {i+1}:** Yanlış.")
                st.info(f"Senin cevabın: {user_ans} | Doğru cevap: **{correct_ans}**")
        
        st.metric("Puan", f"{score} / {total}")
        
        if score == total:
            st.balloons()