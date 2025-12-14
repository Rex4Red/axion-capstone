import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Job, Question, Candidate, Response
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# 1. LOAD CONFIG
load_dotenv(override=True)
app = Flask(__name__)

# Gunakan Secret Key dari .env (atau default untuk lokal)
app.secret_key = os.getenv("SECRET_KEY", "rahasia_hrd_default_dev")

# --- DB CONFIGURATION (FIXED FOR PG8000) ---
# DB URI (Pastikan tetap menggunakan Link Neon Anda)
DB_URI = os.getenv("DATABASE_URL")

# Jika DB_URI None (misal test lokal tanpa .env), beri fallback string kosong atau error
if not DB_URI:
    # Fallback string (opsional, sesuaikan dengan link neon anda jika hardcode)
    DB_URI = "postgresql://neondb_owner:npg_2LkDPfsu7vKy@ep-crimson-breeze-ahdy5lee-pooler.c-3.us-east-1.aws.neon.tech/neondb" 

# 1. Ganti Driver ke pg8000
if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql+pg8000://", 1)
elif DB_URI.startswith("postgresql://"):
    DB_URI = DB_URI.replace("postgresql://", "postgresql+pg8000://", 1)

# 2. HAPUS PARAMETER SSL (PENTING!)
# pg8000 akan crash jika ada '?sslmode=...', jadi kita hapus semua query params
if "?" in DB_URI:
    DB_URI = DB_URI.split("?")[0]

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- TAMBAHKAN BAGIAN INI (SOLUSI ERROR 500 SAAT IDLE) ---
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,        # Cek koneksi sebelum dipakai (PENTING!)
    "pool_recycle": 300,          # Daur ulang koneksi setiap 5 menit (300 detik)
    "pool_size": 10,              # Jumlah koneksi standby
    "max_overflow": 20            # Toleransi kelebihan koneksi
}
# ---------------------------------------------------------

db.init_app(app)

# Konfigurasi Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- KONFIGURASI URL KANDIDAT (PENTING!) ---
# Ambil link Hugging Face dari .env, kalau tidak ada baru pakai localhost
CANDIDATE_SITE_URL = os.getenv("CANDIDATE_SITE_URL", "http://127.0.0.1:5001")

# --- FUNGSI AI GENERATOR SOAL ---
def generate_questions_from_ai(title, level, skills):
    """
    Minta Gemini buatkan 3 soal interview teknis & behavioral
    """
    # Cek API Key
    if not GOOGLE_API_KEY:
        return [
            {"q": "Jelaskan pengalaman Anda?", "a": "Pengalaman relevan."},
            {"q": "Apa motivasi Anda?", "a": "Motivasi tinggi."},
            {"q": "Kelebihan dan Kekurangan?", "a": "Self awareness."}
        ]

    try:
        # Gunakan model standar
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Bertindaklah sebagai Senior HR Recruiter.
        Saya butuh 3 (TIGA) pertanyaan interview spesifik untuk:
        - Posisi: {title}
        - Level: {level}
        - Skill: {skills}
        
        Output WAJIB berupa JSON Array yang berisi tepat 3 objek.
        Jangan gunakan markdown.
        
        Contoh Format Output:
        [
            {{"q": "Pertanyaan pertama tentang teknis...", "a": "Jawaban ideal teknis..."}},
            {{"q": "Pertanyaan kedua tentang studi kasus...", "a": "Solusi studi kasus..."}},
            {{"q": "Pertanyaan ketiga tentang soft skill...", "a": "Attitude yang baik..."}}
        ]
        """
        
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        
        # Debugging: Print hasil mentah dari AI untuk cek di terminal
        print(f"DEBUG AI RESPONSE: {clean_text}") 
        
        return json.loads(clean_text)

    except Exception as e:
        print(f"Error Generate Soal: {e}")
        # Fallback jika error, tetap berikan 3 soal default
        return [
            {"q": f"Apa tantangan terbesar sebagai {title}?", "a": "Problem solving."},
            {"q": f"Jelaskan pemahaman Anda tentang {skills}?", "a": "Penguasaan teknis."},
            {"q": "Bagaimana Anda bekerja dalam tim?", "a": "Kolaborasi."}
        ]

# --- ROUTES ---

@app.route('/')
def dashboard():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    
    # 1. Hitung Total Kandidat
    total_candidates = Candidate.query.count()

    # 2. Hitung Top Talents (Logika: Rata-rata Nilai > 75)
    candidates = Candidate.query.all()
    top_talent_count = 0
    
    for cand in candidates:
        responses = Response.query.filter_by(candidate_id=cand.id).all()
        if responses:
            # Hitung rata-rata skor kandidat ini
            avg_score = sum([r.score_relevance for r in responses]) / len(responses)
            if avg_score > 75: # Ambang batas "Pintar"
                top_talent_count += 1
    
    return render_template(
        'dashboard.html', 
        jobs=jobs, 
        candidate_url=CANDIDATE_SITE_URL,
        total_candidates=total_candidates,
        top_talent_count=top_talent_count  
    )

@app.route('/create-job', methods=['POST'])
def create_job():
    try:
        title = request.form.get('title')
        level = request.form.get('level')
        skills = request.form.get('skills')
        
        new_job = Job(title=title, level=level, skills=skills or "Custom Questions")
        db.session.add(new_job)
        db.session.commit()
        
        # Cek Input Manual
        manual_questions = request.form.getlist('manual_q[]')
        manual_answers = request.form.getlist('manual_a[]')
        
        valid_manual_data = []
        for q, a in zip(manual_questions, manual_answers):
            if q.strip():
                valid_manual_data.append({'q': q, 'a': a})
        
        if valid_manual_data:
            print(f"✍️ Menggunakan {len(valid_manual_data)} Soal Manual...")
            for item in valid_manual_data:
                q = Question(job_id=new_job.id, question_text=item['q'], ideal_answer=item['a'])
                db.session.add(q)
            flash(f'Lowongan "{title}" dibuat dengan {len(valid_manual_data)} soal manual!', 'success')
        else:
            print("🤖 Menggunakan AI Generator...")
            if not skills: skills = title
            questions_data = generate_questions_from_ai(title, level, skills)
            
            for item in questions_data:
                q = Question(job_id=new_job.id, question_text=item['q'], ideal_answer=item['a'])
                db.session.add(q)
            flash(f'Lowongan "{title}" dibuat dengan {len(questions_data)} soal AI!', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(e)
        flash(f'Error: {str(e)}', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/job/<int:job_id>/candidates')
def job_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).all()
    return render_template('candidates_list.html', job=job, candidates=candidates)

@app.route('/candidate/<int:candidate_id>/report')
def candidate_report(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get(candidate.job_id)
    
    report_data = []
    responses = Response.query.filter_by(candidate_id=candidate.id).all()
    
    for resp in responses:
        q = Question.query.get(resp.question_id)
        report_data.append({
            "question": q.question_text,
            "answer_audio": resp.audio_filename, # Bisa video/audio
            "transcript": resp.transcript,
            "score": resp.score_relevance,
            "sentiment": resp.sentiment,
            "cheat_faults": getattr(resp, 'cheat_faults', 0) # Menghindari error jika kolom belum ada
        })
        
    return render_template('report_detail.html', candidate=candidate, job=job, reports=report_data)

@app.route('/delete-job/<int:id>')
def delete_job(id):
    try:
        job = Job.query.get_or_404(id)
        candidates = Candidate.query.filter_by(job_id=id).all()
        for cand in candidates:
            Response.query.filter_by(candidate_id=cand.id).delete()
            db.session.delete(cand)
        Question.query.filter_by(job_id=id).delete()
        db.session.delete(job)
        db.session.commit()
        flash('Lowongan berhasil dihapus.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/candidates')
def all_candidates():
    # Mengambil semua kandidat dan mengurutkan dari yang terbaru
    # Kita join dengan Job agar bisa menampilkan melamar di posisi apa
    candidates = db.session.query(Candidate, Job).join(Job, Candidate.job_id == Job.id).order_by(Candidate.id.desc()).all()
    
    return render_template('all_candidates.html', candidates=candidates)

@app.route('/analytics')
def analytics():
    # 1. Data untuk Grafik Bar: Jumlah Kandidat per Lowongan
    jobs = Job.query.all()
    job_labels = [j.title for j in jobs]
    candidate_counts = []
    
    for job in jobs:
        count = Candidate.query.filter_by(job_id=job.id).count()
        candidate_counts.append(count)
    
    # 2. Data untuk Grafik Donut: Kualitas Kandidat (Berdasarkan Skor AI)
    # Kita kategorikan: High (>75), Medium (50-75), Low (<50)
    all_responses = Response.query.all()
    scores = [r.score_relevance for r in all_responses]
    
    high_tier = len([s for s in scores if s >= 75])
    mid_tier = len([s for s in scores if 50 <= s < 75])
    low_tier = len([s for s in scores if s < 50])
    
    # 3. Statistik Ringkas
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    total_interviews = len(scores)

    return render_template(
        'analytics.html',
        job_labels=json.dumps(job_labels),        # Kirim sebagai JSON untuk JS
        candidate_counts=json.dumps(candidate_counts),
        score_dist=json.dumps([high_tier, mid_tier, low_tier]),
        avg_score=avg_score,
        total_interviews=total_interviews
    )

# --- FITUR BARU: DOWNLOAD JSON ---
@app.route('/candidate/<int:candidate_id>/download/json')
def download_candidate_json(candidate_id):
    try:
        # 1. Ambil Data
        candidate = Candidate.query.get_or_404(candidate_id)
        job = Job.query.get(candidate.job_id)
        questions = Question.query.filter_by(job_id=job.id).all()
        responses = Response.query.filter_by(candidate_id=candidate.id).all()

        # 2. Hitung Statistik & Checklist
        total_score = 0
        scores_list = []
        video_checklist = []
        
        response_map = {r.question_id: r for r in responses}

        for i, q in enumerate(questions, 1):
            resp = response_map.get(q.id)
            
            # Data Checklist
            video_checklist.append({
                "positionId": i,
                "question": q.question_text,
                "isVideoExist": True if resp else False,
                "recordedVideoUrl": resp.audio_filename if resp else None
            })

            # Data Scoring
            score_val = resp.score_relevance if resp else 0
            total_score += score_val
            scores_list.append({
                "id": i,
                "score": score_val
            })

        avg_score = round(total_score / len(questions), 2) if questions else 0
        decision = "PASSED" if avg_score >= 70 else "FAILED"

        # --- BAGIAN PERBAIKAN (ANTI CRASH) ---
        # Kita gunakan getattr untuk cek apakah kolom 'applied_at' ada di database/model
        # Jika tidak ada, gunakan tanggal hari ini atau string "N/A"
        if hasattr(candidate, 'applied_at') and candidate.applied_at:
            applied_date = str(candidate.applied_at)
        else:
            # Fallback jika kolom tidak ada di database lama
            applied_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') 
        # -------------------------------------

        reviewed_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # 3. Susun JSON
        json_data = {
            "success": True,
            "data": {
                "id": candidate.id,
                "candidate": {
                    "name": candidate.name,
                    "email": candidate.email,
                    "photoUrl": f"https://ui-avatars.com/api/?name={candidate.name}&background=random"
                },
                "certification": {
                    "abbreviatedType": "AXION",
                    "normalType": f"INTERVIEW_{job.level.upper()}",
                    "submittedAt": applied_date, # Menggunakan variabel aman
                    "status": "FINISHED",
                    "projectType": job.title,
                    "examScore": avg_score,
                    "assess": { "project": False, "interviews": True }
                },
                "reviewChecklists": {
                    "project": [],
                    "interviews": video_checklist
                },
                "pastReviews": [
                    {
                        "assessorProfile": { "id": 1, "name": "Axion AI", "photoUrl": None },
                        "decision": decision,
                        "reviewedAt": reviewed_date,
                        "scoresOverview": { "interview": avg_score, "total": avg_score },
                        "reviewChecklistResult": {
                            "interviews": { "minScore": 0, "maxScore": 100, "scores": scores_list }
                        },
                        "notes": "Auto-generated report by Axion HRD System."
                    }
                ]
            }
        }

        # 4. Force Download
        response = jsonify(json_data)
        safe_name = candidate.name.replace(' ', '_')
        safe_job = job.title.replace(' ', '_')
        filename = f"Report_{safe_name}_{safe_job}.json"
        
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    except Exception as e:
        print(f"ERROR DOWNLOAD JSON: {e}")
        return jsonify({"error": str(e)}), 500
        
if __name__ == '__main__':
    app.run(debug=True, port=5000)