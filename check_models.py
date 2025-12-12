import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print(f"Menggunakan API Key: {api_key[:5]}...*****")
print("\n=== DAFTAR MODEL YANG TERSEDIA ===")

try:
    for m in genai.list_models():
        # Kita hanya cari model yang bisa generate content (bukan embedding)
        if 'generateContent' in m.supported_generation_methods:
            print(f"- Nama: {m.name}")
            print(f"  Deskripsi: {m.description[:50]}...")
            print("-" * 30)
except Exception as e:
    print(f"❌ Error: {e}")