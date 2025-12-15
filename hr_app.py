import os
import json
from datetime import datetime
from functools import wraps  # <--- WAJIB: Untuk decorator login
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session # <--- WAJIB: Ada session
from models import db, Job, Question, Candidate, Response
from dotenv import load_dotenv
import google.generativeai as genai

# 1. LOAD CONFIG
load_dotenv(override=True)
app = Flask(__name__)

# Gunakan Secret Key dari .env (atau default untuk lokal)
app.secret_key = os.getenv("SECRET_KEY", "rahasia_hrd_default_dev")

# --- KONFIGURASI LOGIN ADMIN ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "A25-CS383")

# --- KONFIGURASI DATABASE (PERBAIKAN DRIVER PG8000) ---
DB_URI = os.getenv("DATABASE_URL")

if not DB_URI:
    # Fallback string (opsional)
    DB_URI = "postgresql://neondb_owner:npg_2LkDPfsu7vKy@ep-crimson-breeze-ahdy5lee-pooler.c-3.us-east-1.aws.neon.tech/neondb" 

# 1. Ganti Driver ke pg8000
if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql+pg8000://", 1)
elif DB_URI.startswith("postgresql://"):
    DB_URI = DB_URI.replace("postgresql://", "postgresql+pg8000://", 1)

# 2. HAPUS PARAMETER SSL (PENTING!)
if "?" in DB_URI:
    DB_URI = DB_URI.split("?")[0]

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SOLUSI ERROR 500 SAAT IDLE ---
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,        # Cek koneksi sebelum dipakai
    "pool_recycle": 300,          # Daur ulang koneksi setiap 5 menit
    "pool_size": 10,
    "max_overflow": 20
}

db.init_app(app)

# Konfigurasi Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- KONFIGURASI URL KANDIDAT ---
CANDIDATE_SITE_URL = os.getenv("CANDIDATE_SITE_URL", "http://127.0.0.1:5001")

# --- DECORATOR: PENJAGA PINTU (LOGIN REQUIRED) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'is_logged_in' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- FUNGSI AI GENERATOR SOAL ---
def generate_questions_from_ai(title, level, skills):
    if not GOOGLE_API_KEY:
        return [
            {"q": "Jelaskan pengalaman Anda?", "a": "Pengalaman relevan."},
            {"q": "Apa motivasi Anda?", "a": "Motivasi tinggi."},
            {"q": "Kelebihan dan Kekurangan?", "a": "Self awareness."}
        ]

    try:
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
            {{"q": "Pertanyaan teknis...", "a": "Jawaban teknis..."}},
            {{"q": "Pertanyaan studi kasus...", "a": "Solusi..."}},
            {{"q": "Pertanyaan soft skill...", "a": "Attitude..."}}
        ]
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        print(f"DEBUG AI RESPONSE: {clean_text}") 
        return json.loads(clean_text)

    except Exception as e:
        print(f"Error Generate Soal: {e}")
        return [
            {"q": f"Apa tantangan terbesar sebagai {title}?", "a": "Problem solving."},
            {"q": f"Jelaskan pemahaman Anda tentang {skills}?", "a": "Penguasaan teknis."},
            {"q": "Bagaimana Anda bekerja dalam tim?", "a": "Kolaborasi."}
        ]

# --- ROUTES ---

# 1. ROUTE LOGIN & LOGOUT
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        if user == ADMIN_USERNAME and pwd == ADMIN_PASSWORD:
            session['is_logged_in'] = True
            session['user'] = user
            flash('Login berhasil! Selamat datang.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau Password salah!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))


# 2. ROUTE UTAMA (DILINDUNGI @login_required)

@app.route('/')
@login_required  # <--- Pasang Gembok
def dashboard():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    total_candidates = Candidate.query.count()

    candidates = Candidate.query.all()
    top_talent_count = 0
    
    for cand in candidates:
        responses = Response.query.filter_by(candidate_id=cand.id).all()
        if responses:
            avg_score = sum([r.score_relevance for r in responses]) / len(responses)
            if avg_score > 75:
                top_talent_count += 1
    
    return render_template(
        'dashboard.html', 
        jobs=jobs, 
        candidate_url=CANDIDATE_SITE_URL,
        total_candidates=total_candidates,
        top_talent_count=top_talent_count
    )

@app.route('/create-job', methods=['POST'])
@login_required  # <--- Pasang Gembok
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
@login_required  # <--- Pasang Gembok
def job_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).all()
    return render_template('candidates_list.html', job=job, candidates=candidates)

@app.route('/candidate/<int:candidate_id>/report')
@login_required  # <--- Pasang Gembok
def candidate_report(candidate_id):
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
            "sentiment": resp.sentiment,
            "cheat_faults": getattr(resp, 'cheat_faults', 0)
        })
        
    return render_template('report_detail.html', candidate=candidate, job=job, reports=report_data)

@app.route('/delete-job/<int:id>')
@login_required  # <--- Pasang Gembok
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
@login_required  # <--- Pasang Gembok
def all_candidates():
    candidates = db.session.query(Candidate, Job).join(Job, Candidate.job_id == Job.id).order_by(Candidate.id.desc()).all()
    return render_template('all_candidates.html', candidates=candidates)

@app.route('/analytics')
@login_required  # <--- Pasang Gembok
def analytics():
    jobs = Job.query.all()
    job_labels = [j.title for j in jobs]
    candidate_counts = []
    
    for job in jobs:
        count = Candidate.query.filter_by(job_id=job.id).count()
        candidate_counts.append(count)
    
    all_responses = Response.query.all()
    scores = [r.score_relevance for r in all_responses]
    
    high_tier = len([s for s in scores if s >= 75])
    mid_tier = len([s for s in scores if 50 <= s < 75])
    low_tier = len([s for s in scores if s < 50])
    
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    total_interviews = len(scores)

    return render_template(
        'analytics.html',
        job_labels=json.dumps(job_labels),
        candidate_counts=json.dumps(candidate_counts),
        score_dist=json.dumps([high_tier, mid_tier, low_tier]),
        avg_score=avg_score,
        total_interviews=total_interviews
    )

@app.route('/candidate/<int:candidate_id>/download/json')
@login_required  # <--- Pasang Gembok
def download_candidate_json(candidate_id):
    try:
        candidate = Candidate.query.get_or_404(candidate_id)
        job = Job.query.get(candidate.job_id)
        questions = Question.query.filter_by(job_id=job.id).all()
        responses = Response.query.filter_by(candidate_id=candidate.id).all()

        total_score = 0
        scores_list = []
        video_checklist = []
        
        response_map = {r.question_id: r for r in responses}

        for i, q in enumerate(questions, 1):
            resp = response_map.get(q.id)
            video_checklist.append({
                "positionId": i,
                "question": q.question_text,
                "isVideoExist": True if resp else False,
                "recordedVideoUrl": resp.audio_filename if resp else None
            })
            score_val = resp.score_relevance if resp else 0
            total_score += score_val
            scores_list.append({ "id": i, "score": score_val })

        avg_score = round(total_score / len(questions), 2) if questions else 0
        decision = "PASSED" if avg_score >= 70 else "FAILED"

        # Anti-Crash untuk applied_at
        if hasattr(candidate, 'applied_at') and candidate.applied_at:
            applied_date = str(candidate.applied_at)
        else:
            applied_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') 
        
        reviewed_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

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
                    "submittedAt": applied_date,
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