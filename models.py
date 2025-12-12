from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Inisialisasi DB kosong
db = SQLAlchemy()

# --- MODEL DATABASE ---
class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(50), nullable=False)
    skills = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relasi
    questions = db.relationship('Question', backref='job', lazy=True, cascade="all, delete-orphan")
    candidates = db.relationship('Candidate', backref='job', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    ideal_answer = db.Column(db.Text)

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    interview_date = db.Column(db.DateTime, default=datetime.utcnow)
    
# ... (Class Candidate diatasnya) ...

# Model Response (Jawaban Audio)
class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    
    audio_filename = db.Column(db.String(200)) # Kita pakai ini untuk simpan URL VIDEO
    transcript = db.Column(db.Text)
    score_relevance = db.Column(db.Float)
    sentiment = db.Column(db.String(50))
    
    # --- KOLOM BARU ---
    cheat_faults = db.Column(db.Integer, default=0) # Jumlah kali curang (pindah tab)