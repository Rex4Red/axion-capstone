import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Job, Question, Candidate, Response
from dotenv import load_dotenv
import google.generativeai as genai

# 1. LOAD CONFIG
load_dotenv(override=True)
app = Flask(__name__)
app.secret_key = 'rahasia_hrd'

# Konfigurasi Database Neon
DB_URI = "postgresql://neondb_owner:npg_2LkDPfsu7vKy@ep-crimson-breeze-ahdy5lee-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Konfigurasi Gemini (Untuk bikin soal)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# URL Website Kandidat (Port 5001)
CANDIDATE_SITE_URL = "http://127.0.0.1:5001" 

# --- FUNGSI AI GENERATOR SOAL ---
def generate_questions_from_ai(title, level, skills):
    """
    Minta Gemini buatkan 3 soal interview teknis & behavioral
    """
    if not GOOGLE_API_KEY:
        # Fallback jika API Key belum ada
        return [
            {"q": "Jelaskan pengalaman Anda yang paling relevan?", "a": "Kandidat menjelaskan pengalaman kerja."},
            {"q": "Apa kelebihan dan kekurangan Anda?", "a": "Self-awareness yang baik."},
            {"q": "Mengapa Anda tertarik dengan posisi ini?", "a": "Motivasi yang kuat."}
        ]

    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        
        prompt = f"""
        Bertindaklah sebagai Senior HR Recruiter.
        Saya butuh 3 pertanyaan interview untuk posisi:
        - Judul: {title}
        - Level: {level}
        - Skill Wajib: {skills}
        
        Berikan Output HANYA JSON Array murni (tanpa markdown). 
        Format:
        [
            {{"q": "Pertanyaan 1...", "a": "Poin jawaban ideal..."}},
            {{"q": "Pertanyaan 2...", "a": "Poin jawaban ideal..."}},
            {{"q": "Pertanyaan 3...", "a": "Poin jawaban ideal..."}}
        ]
        """
        
        response = model.generate_content(prompt)
        # Bersihkan markdown jika Gemini iseng nambahin ```json
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

    except Exception as e:
        print(f"Error Generate Soal: {e}")
        return [{"q": f"Ceritakan pengalaman Anda di bidang {title}?", "a": "Relevansi pengalaman."}]

# --- ROUTES ---

@app.route('/')
def dashboard():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('dashboard.html', jobs=jobs, candidate_url=CANDIDATE_SITE_URL)

@app.route('/create-job', methods=['POST'])
def create_job():
    try:
        title = request.form.get('title')
        level = request.form.get('level')
        skills = request.form.get('skills') # Bisa kosong jika pilih manual
        
        # 1. Simpan Job Baru dulu
        new_job = Job(title=title, level=level, skills=skills or "Custom Questions")
        db.session.add(new_job)
        db.session.commit()
        
        # 2. CEK INPUT MANUAL
        # request.form.getlist mengambil semua input dengan nama yang sama (array)
        manual_questions = request.form.getlist('manual_q[]')
        manual_answers = request.form.getlist('manual_a[]')
        
        # Filter: Pastikan pertanyaan tidak kosong (strip whitespace)
        valid_manual_data = []
        for q, a in zip(manual_questions, manual_answers):
            if q.strip(): # Jika pertanyaan ada isinya
                valid_manual_data.append({'q': q, 'a': a})
        
        if valid_manual_data:
            # --- JALUR MANUAL ---
            print(f"✍️ Menggunakan {len(valid_manual_data)} Soal Manual...")
            for item in valid_manual_data:
                q = Question(
                    job_id=new_job.id, 
                    question_text=item['q'], 
                    ideal_answer=item['a']
                )
                db.session.add(q)
            
            flash(f'Lowongan "{title}" dibuat dengan {len(valid_manual_data)} soal manual!', 'success')
            
        else:
            # --- JALUR AI (AUTO) ---
            print("🤖 Menggunakan AI Generator...")
            # Pastikan skills terisi kalau mau pakai AI
            if not skills:
                skills = title # Fallback jika skill kosong
                
            questions_data = generate_questions_from_ai(title, level, skills)
            
            for item in questions_data:
                q = Question(
                    job_id=new_job.id, 
                    question_text=item['q'], 
                    ideal_answer=item['a']
                )
                db.session.add(q)
            
            flash(f'Lowongan "{title}" dibuat dengan {len(questions_data)} soal AI!', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(e)
        flash(f'Error: {str(e)}', 'danger')
        
    return redirect(url_for('dashboard'))
# Route List Kandidat
@app.route('/job/<int:job_id>/candidates')
def job_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).all()
    return render_template('candidates_list.html', job=job, candidates=candidates)

# Route Detail Report
@app.route('/candidate/<int:candidate_id>/report')
def candidate_report(candidate_id):
    from models import Response # Import di dalam fungsi untuk hindari circular import
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get(candidate.job_id)
    
    report_data = []
    responses = Response.query.filter_by(candidate_id=candidate.id).all()
    
    for resp in responses:
        q = Question.query.get(resp.question_id)
        report_data.append({
            "question": q.question_text,
            "answer_audio": resp.audio_filename,
            "transcript": resp.transcript,
            "score": resp.score_relevance,
            "sentiment": resp.sentiment
        })
        
    return render_template('report_detail.html', candidate=candidate, job=job, reports=report_data)

@app.route('/delete-job/<int:id>')
def delete_job(id):
    try:
        job = Job.query.get_or_404(id)

        # 1. Cari semua kandidat yang melamar di job ini
        candidates = Candidate.query.filter_by(job_id=id).all()

        for cand in candidates:
            # 2. Hapus semua JAWABAN (Response) milik kandidat ini
            Response.query.filter_by(candidate_id=cand.id).delete()
            
            # 3. Hapus KANDIDAT itu sendiri
            db.session.delete(cand)

        # 4. Hapus semua PERTANYAAN (Question) terkait job ini
        Question.query.filter_by(job_id=id).delete()

        # 5. Terakhir, Hapus JOB itu sendiri
        db.session.delete(job)
        
        db.session.commit()
        flash('Lowongan dan semua data kandidat berhasil dihapus.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)