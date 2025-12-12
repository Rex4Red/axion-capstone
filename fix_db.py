import os
from flask import Flask
from sqlalchemy import text
from models import db
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# PASTIKAN INI SAMA DENGAN LINK NEON DI HR_APP.PY / CANDIDATE_APP.PY
# Ganti ... dengan password/host asli Anda
DB_URI = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_2LkDPfsu7vKy@ep-crimson-breeze-ahdy5lee-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def fix_database():
    with app.app_context():
        try:
            print("🔧 Sedang memperbaiki database...")
            # Perintah SQL manual untuk tambah kolom
            sql = text("ALTER TABLE response ADD COLUMN IF NOT EXISTS cheat_faults INTEGER DEFAULT 0;")
            db.session.execute(sql)
            db.session.commit()
            print("✅ SUKSES! Kolom 'cheat_faults' berhasil ditambahkan.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Gagal: {e}")

if __name__ == '__main__':
    fix_database()