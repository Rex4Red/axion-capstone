import os
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, jsonify
from models import db, Job, Candidate, Question, Response # Pastikan import Response & Question
from werkzeug.utils import secure_filename
from ai_engine import process_interview_answer

app = Flask(__name__)
app.secret_key = 'rahasia_kandidat'

cloudinary.config( 
  cloud_name = "dki3iburr", 
  api_key = "539567615736385", 
  api_secret = "U-U3SQkzoeLjdX-3FJTqT-rPRYc",
  secure = True
)

# Konfigurasi Upload Folder (PENTING untuk simpan audio sementara)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# DB URI (Pastikan tetap menggunakan Link Neon Anda)
DB_URI = "postgresql://neondb_owner:npg_2LkDPfsu7vKy@ep-crimson-breeze-ahdy5lee-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# --- ROUTES ---

@app.route('/')
def home():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('career_home.html', jobs=jobs)

@app.route('/interview/<int:job_id>')
def interview_landing(job_id):
    job = Job.query.get_or_404(job_id)
    return render_template('interview_landing.html', job=job)

# PROSES 1: DAFTAR & REDIRECT KE ROOM
@app.route('/start-interview/<int:job_id>', methods=['POST'])
def start_interview(job_id):
    name = request.form.get('name')
    email = request.form.get('email')
    
    # 1. Simpan Kandidat
    new_candidate = Candidate(job_id=job_id, name=name, email=email)
    db.session.add(new_candidate)
    db.session.commit()
    
    # 2. Redirect ke Ruang Interview membawa ID Kandidat
    return redirect(url_for('interview_room', candidate_id=new_candidate.id))

# PROSES 2: HALAMAN RUANG INTERVIEW
@app.route('/room/<int:candidate_id>')
def interview_room(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get(candidate.job_id)
    
    # Ambil semua pertanyaan untuk job ini
    questions = Question.query.filter_by(job_id=job.id).all()
    
    return render_template('interview_room.html', candidate=candidate, job=job, questions=questions)

# PROSES 3: API TERIMA AUDIO (Dipanggil via AJAX/JS)
@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    # 1. Cek apakah ada file video (bisa dari webcam blob atau file upload)
    if 'video' not in request.files:
        return jsonify({'status': 'error', 'msg': 'No video file'}), 400
    
    file = request.files['video']
    candidate_id = request.form.get('candidate_id')
    question_id = request.form.get('question_id')
    cheat_count = request.form.get('cheat_count', 0) # Ambil data curang
    
    if file:
        print(f"📹 Menerima video.. Cheat Count: {cheat_count}")
        
        # 2. Upload Video ke Cloudinary
        upload_result = cloudinary.uploader.upload(
            file, 
            resource_type = "video", # Tetap video
            folder = "axion_videos",
            public_id = f"cand_{candidate_id}_q_{question_id}_vid"
        )
        video_url = upload_result['secure_url']

        # 3. Proses AI (Kirim Video URL)
        question = Question.query.get(question_id)
        ai_result = process_interview_answer(
            video_url, 
            question.question_text, 
            question.ideal_answer
        )

        # 4. Simpan ke DB
        new_response = Response(
            candidate_id=candidate_id,
            question_id=question_id,
            audio_filename=video_url, # Kolom ini sekarang isinya URL Video
            transcript=ai_result['transcript'],
            score_relevance=ai_result['score'],
            sentiment=ai_result['sentiment'],
            cheat_faults=int(cheat_count) # Simpan jumlah curang
        )
        
        db.session.add(new_response)
        db.session.commit()
        
        return jsonify({'status': 'success', 'filename': video_url})

    return jsonify({'status': 'error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)