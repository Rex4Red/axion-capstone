import os
import time
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# 1. LOAD CONFIG
load_dotenv(override=True)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def process_interview_answer(media_url, question_text, ideal_answer):
    if not GOOGLE_API_KEY:
        print("❌ API Key Kosong.")
        return {"score": 0, "sentiment": "Error", "transcript": "API Key Missing", "feedback": "Cek .env"}

    # Gunakan format MP4 agar support Video & Audio
    temp_filename = "temp_media.mp4"
    
    try:
        # A. DOWNLOAD FILE
        print(f"📥 Downloading media...")
        response = requests.get(media_url)
        with open(temp_filename, 'wb') as f:
            f.write(response.content)

        # B. UPLOAD KE GOOGLE AI
        print("☁️ Uploading ke Google AI...")
        # Biarkan mime_type kosong agar auto-detect (Video/Audio)
        media_file = genai.upload_file(path=temp_filename) 
        
        # Tunggu processing
        while media_file.state.name == "PROCESSING":
            time.sleep(1)
            media_file = genai.get_file(media_file.name)

        # C. ANALISIS GEMINI
        print("🧠 Mengirim ke Gemini Flash Latest...")
        

        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""
        Peran: HR Recruiter yang Sangat Tegas & Teliti.
        
        Tugas:
        1. Transkrip ucapan kandidat.
        2. Lakukan CEK RELEVANSI (Wajib): Apakah topik yang dibicarakan kandidat NYAMBUNG dengan pertanyaan?
           - Pertanyaan: "{question_text}"
           - Jawaban Kandidat: (Analisis dari audio/video)
        
        ATURAN PENILAIAN TEGAS:
        - JIKA jawaban TIDAK NYAMBUNG sama sekali (misal: Ditanya Game malah jawab Coding, atau sebaliknya) -> WAJIB BERI SKOR 0 - 20.
        - JIKA jawaban nyambung tapi kurang tepat -> Skor 21 - 60.
        - JIKA jawaban tepat sesuai Kunci -> Skor 61 - 100.
        - Jangan terkecoh dengan istilah rumit atau bahasa Inggris yang lancar jika topiknya salah!
        
        Kunci Jawaban Ideal: "{ideal_answer}"
        
        Output JSON Murni:
        {{
            "transcript": "teks ucapan...",
            "score": (angka 0-100),
            "sentiment": "Positif/Netral/Negatif",
            "feedback": "Kritik pedas jika tidak nyambung. Saran jika nyambung."
        }}
        """

        response = model.generate_content(
            [prompt, media_file],
            generation_config={"response_mime_type": "application/json"}
        )
        
        result = json.loads(response.text)
        
        # Cleanup Cloud File
        try:
            genai.delete_file(media_file.name)
        except:
            pass
        
        return result

    except Exception as e:
        print(f"❌ Error Gemini: {str(e)}")
        return {
            "transcript": "Gagal memproses AI.",
            "score": 0,
            "sentiment": "Error",
            "feedback": str(e)
        }
    
    finally:
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass