# Axion HRD - AI-Powered Recruitment Platform

![Axion HRD](static/AxionLogo.png)

## 1. Deskripsi Singkat Proyek

**Axion HRD** adalah platform manajemen rekrutmen berbasis web yang mengintegrasikan kecerdasan buatan (Artificial Intelligence) untuk mengefisiensikan proses wawancara kerja. Aplikasi ini dirancang untuk membantu tim HRD dalam menyaring kandidat secara otomatis dan objektif.

Fitur utama aplikasi ini meliputi:
* **HR Dashboard:** Manajemen lowongan pekerjaan dan pemantauan status pelamar dengan antarmuka *Dark Glass* yang modern.
* **AI Interviewer:** Kandidat merekam jawaban video mereka, yang kemudian dianalisis oleh AI untuk relevansi jawaban, sentimen, dan transkripsi otomatis.
* **Analytics:** Visualisasi data performa rekrutmen menggunakan grafik interaktif (Chart.js) untuk melihat distribusi dan kualitas kandidat.
* **Responsif:** Tampilan yang optimal baik di Desktop maupun Mobile.

---

## 2. Petunjuk Setup Environment

Ikuti langkah-langkah berikut untuk menyiapkan lingkungan kerja (environment) di komputer lokal Anda sebelum menjalankan aplikasi.

### Prasyarat
Pastikan Anda telah menginstal:
* [Python](https://www.python.org/) (Versi 3.10 ke atas disarankan)
* [Git](https://git-scm.com/)

### Langkah Instalasi

1.  **Clone Repository**
    Unduh kode sumber proyek ke komputer Anda:
    ```bash
    git clone [https://huggingface.co/spaces/Rex4Red/Axion-HRD](https://huggingface.co/spaces/Rex4Red/Axion-HRD)
    cd Axion-HRD
    ```

2.  **Buat Virtual Environment (Disarankan)**
    Supaya library tidak bentrok dengan sistem utama:
    ```bash
    # Untuk Windows
    python -m venv venv
    venv\Scripts\activate

    # Untuk Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    Instal semua library yang dibutuhkan yang terdaftar di `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment Variables (.env)**
    Buat file baru bernama `.env` di dalam folder root proyek, lalu isi dengan konfigurasi berikut (sesuaikan dengan kredensial Anda):

    ```env
    # Konfigurasi Database (PostgreSQL / Neon DB)
    DATABASE_URL=postgresql://user:password@host/dbname

    # Kunci Rahasia Aplikasi Flask
    SECRET_KEY=kunci_rahasia_anda_disini

    # Cloudinary (Untuk penyimpanan video interview)
    CLOUD_NAME=nama_cloud_anda
    API_KEY=api_key_cloudinary_anda
    API_SECRET=api_secret_cloudinary_anda

    # Google Gemini AI (Untuk analisis jawaban)
    GOOGLE_API_KEY=api_key_gemini_anda
    ```

---

## 3. Tautan Model ML (Machine Learning)

Aplikasi ini menggunakan **Generative AI** melalui API, sehingga tidak memerlukan pengunduhan file model fisik (seperti `.h5`, `.pkl`, atau `.pt`) ke penyimpanan lokal.

* **Model yang digunakan:** Google Gemini 1.5 Flash.
* **Cara Akses:** Model diakses secara cloud melalui library `google-generativeai`.
* **Implementasi:** Logika integrasi AI terdapat pada file `ai_engine.py`.

Aplikasi mengirimkan transkrip/video ke API Gemini, dan model mengembalikan analisis berupa:
1.  Skor Relevansi (0-100)
2.  Analisis Sentimen (Positif/Netral/Negatif)
3.  Ringkasan Jawaban

---

## 4. Cara Menjalankan Aplikasi

Setelah proses setup selesai, Anda dapat menjalankan aplikasi dengan cara berikut:

### Menjalankan di Lokal (Development)

1.  Pastikan virtual environment sudah aktif.
2.  Jalankan perintah berikut di terminal:
    ```bash
    python hr_app.py
    ```
    *(Catatan: Jika file utama Anda bernama `app.py`, ganti perintah di atas menjadi `python app.py`)*

3.  Buka browser dan akses alamat:
    ```
    [http://127.0.0.1:7860](http://127.0.0.1:7860)
    ```

### Menjalankan dengan Docker (Deployment)

Jika Anda ingin menjalankan aplikasi menggunakan Docker (seperti di Hugging Face Spaces):

1.  Build image Docker:
    ```bash
    docker build -t axion-hrd .
    ```
2.  Jalankan container:
    ```bash
    docker run -p 7860:7860 axion-hrd
    ```

---

## Teknologi yang Digunakan

* **Backend:** Python, Flask, SQLAlchemy (PostgreSQL/pg8000)
* **Frontend:** HTML5, CSS3, Bootstrap 5, JavaScript (Chart.js)
* **AI Service:** Google Gemini AI API
* **Media Storage:** Cloudinary
* **Deployment:** Docker / Hugging Face Spaces

---

**Dibuat oleh:** Tim Capstone A25-CS383 
