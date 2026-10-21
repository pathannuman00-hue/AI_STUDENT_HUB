import time 
from flask import Flask, render_template_string, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
import math
import re
from collections import Counter
import os
import json
import html
import logging
from dotenv import load_dotenv
from google import genai

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



app = Flask(__name__)
app.secret_key = "super_secret_campus_key"
DB_PATH = Path(__file__).with_name("campus_hub.db")
UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# 🔑 YOUR GEMINI API KEY
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                skills TEXT NOT NULL,
                requirements TEXT DEFAULT 'Basic computer literacy and enthusiasm',
                course_plan TEXT DEFAULT '1. Introduction\n2. Hands-on Lab\n3. Final Project'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                comments TEXT NOT NULL,
                sentiment TEXT,
                score REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                filename TEXT,
                content TEXT NOT NULL,
                rating_score REAL,
                feedback_report TEXT
            )
        """)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(resumes)")
        columns = [column[1] for column in cursor.fetchall()]
        if "filename" not in columns:
            conn.execute("ALTER TABLE resumes ADD COLUMN filename TEXT")

        cursor.execute("SELECT COUNT(*) FROM activities")
        if cursor.fetchone()[0] == 0:
            sample_activities = [
                ("Python Hackathon", "Technical", "Build real-world web applications and AI bots in 24 hours.", "python programming coding backend software web apps development", "Python basics, Flask, APIs", "Phase 1: Setup Backend\nPhase 2: Build AI Integration\nPhase 3: Deploy App"),
                ("AI & Machine Learning Workshop", "Workshop", "Learn neural networks, data science, and intelligent systems.", "ai python machine learning data science technology coding smart", "Python, Linear Algebra basics", "Phase 1: Data Preprocessing\nPhase 2: Model Training\nPhase 3: Evaluation"),
                ("Inter-College Badminton Tournament", "Sports", "Racket sports competition, indoor badminton singles and doubles matches.", "badminton sports fitness racket shuttle outdoor indoor agility exercise athletics", "Good physical stamina, Racket", "Phase 1: Agility Drills\nPhase 2: Singles Matches\nPhase 3: Championship"),
                ("Culinary Arts & Cooking Masterclass", "Lifestyle", "Learn gourmet cooking, baking, dish presentation, and chef techniques.", "cooking culinary food baking chef kitchen recipe taste foodies dish", "Interest in cooking, Apron", "Phase 1: Knife Skills\nPhase 2: Baking Essentials\nPhase 3: Gourmet Plating"),
                ("Stand-up Comedy & Roasting Workshop", "Entertainment", "Master humorous storytelling, punchlines, roasting, and stage comedy.", "roasting comedy standup humor drama entertainment performance stage funny jokes", "Confidence, Sense of humor", "Phase 1: Writing Jokes\nPhase 2: Mic Technique\nPhase 3: Open Mic Showcase"),
                ("Motorsports & Road Trip Driving Club", "Adventure", "Automobile enthusiast meetup, karting, highway driving safety, and road trips.", "drive driving motorsports cars racing road trip adventure travel speed automotive", "Valid Driver License", "Phase 1: Safety Briefing\nPhase 2: Karting Practice\nPhase 3: Convoy Trip"),
                ("Mindfulness, Rest & Sleep Wellness", "Health", "Learn sleep hygiene, relaxation techniques, stress management, and mental health.", "sleeping sleep rest mindfulness relaxation health mental wellness peace balance", "Open mind, Yoga mat", "Phase 1: Sleep Tracking\nPhase 2: Meditation\nPhase 3: Lifestyle Balance"),
                ("Inter-College Cricket League", "Sports", "Annual cricket championship cup for energetic athletes and teams.", "sports cricket fitness team athletics match cup ball bat", "Cricket kit, Team spirit", "Phase 1: Net Practice\nPhase 2: Tactical Strategy\nPhase 3: League Match")
            ]
            conn.executemany("""
                INSERT INTO activities (title, category, description, skills, requirements, course_plan) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, sample_activities)

init_db()
def ai_audit_document_with_gemini(doc_type, text_content):
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key missing. Check your .env file."
        )

    if not text_content or not text_content.strip():
        raise ValueError("No readable text found in the document.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
You are an expert resume and academic document reviewer.

Document type: {doc_type}

Analyze the document text below.

If it is a resume, evaluate skills, projects, education,
experience, formatting information present in the text,
strengths, weaknesses, and practical improvements.

If it is an exam result, evaluate the marks or CGPA actually
provided. Never invent missing academic information.

Return valid JSON only, in this format:
{{
  "score": 75,
  "summary": "Brief assessment",
  "strengths": ["Strength 1", "Strength 2"],
  "weaknesses": ["Weakness 1", "Weakness 2"],
  "tips": ["Tip 1", "Tip 2", "Tip 3"]
}}

The score is an example, not a predetermined result.
For resumes, score overall document quality rather than
assuming academic marks exist.

DOCUMENT TEXT:
{text_content[:20000]}
"""

    try:
        
        
        response = None

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                break

            except Exception as e:
                error_message = str(e)

                if "503" in error_message or "UNAVAILABLE" in error_message:
                    if attempt < 2:
                        logger.warning(
                            "Gemini temporarily unavailable. "
                            "Retrying in 3 seconds (attempt %s/3).",
                            attempt + 1
                        )
                        time.sleep(3)
                    else:
                        raise
                else:
                    raise



        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        result = json.loads(response.text)

        score = float(result["score"])

        if not 0 <= score <= 100:
            raise ValueError("Invalid score returned by Gemini.")

        def safe_list(items):
            if not isinstance(items, list):
                return ""
            return "".join(
                "<li>" + html.escape(str(item)) + "</li>"
                for item in items
            )

        summary = html.escape(str(result.get("summary", "")))

        report_html = f"""
        <div>
            <h4>Assessment Summary</h4>
            <p>{summary}</p>

            <strong style="color:#198754">Strengths</strong>
            <ul>{safe_list(result.get("strengths", []))}</ul>

            <strong style="color:#dc3545">Weaknesses</strong>
            <ul>{safe_list(result.get("weaknesses", []))}</ul>

            <strong style="color:#0d6efd">Improvement Tips</strong>
            <ul>{safe_list(result.get("tips", []))}</ul>
        </div>
        """

        return round(score, 1), report_html

    except Exception:
        logger.exception("Gemini API audit failed")
        raise

def ai_recommend_activities(student_interests):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        activities = conn.execute("SELECT * FROM activities").fetchall()

    cleaned_input = re.sub(r'[,_/\-]+', ' ', student_interests.lower())
    input_tokens = [w for w in re.findall(r'\w+', cleaned_input) if len(w) > 1]
    
    synonyms = {
        "batminton": "badminton sports racket shuttle", "badminton": "badminton sports racket shuttle",
        "cooking": "culinary food baking kitchen chef", "roasting": "comedy standup humor funny jokes",
        "drive": "driving motorsports road trip adventure", "sleeping": "sleep rest relaxation wellness health"
    }
    expanded_tokens = list(input_tokens)
    for token in input_tokens:
        if token in synonyms:
            expanded_tokens.extend(synonyms[token].split())

    user_vec = Counter(expanded_tokens)

    def cosine_similarity(vec1, vec2):
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum(vec1[x] * vec2[x] for x in intersection)
        sum1 = sum(v ** 2 for v in vec1.values())
        sum2 = sum(v ** 2 for v in vec2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2) if sum1 and sum2 else 0.0
        return float(numerator) / denominator if denominator else 0.0

    scored = []
    for act in activities:
        act_text = f"{act['title']} {act['category']} {act['description']} {act['skills']}".lower()
        act_vec = Counter(re.findall(r'\w+', act_text))
        raw_score = cosine_similarity(user_vec, act_vec)
        matched_words = [token for token in input_tokens if token in act_text]
        match_ratio = len(matched_words) / max(len(input_tokens), 1)
        final_score = max(raw_score * 100, match_ratio * 75.0) + (len(matched_words) * 5.0)
        scored.append({"activity": act, "score": min(round(final_score, 1), 98.5)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

def ai_analyze_sentiment(text):
    pos_words = {"great", "awesome", "excellent", "love", "good", "amazing", "helpful", "fantastic", "exciting", "enjoyed"}
    neg_words = {"poor", "bad", "boring", "terrible", "worst", "disappointing", "useless", "confusing"}
    words = re.findall(r'\w+', text.lower())
    p = sum(1 for w in words if w in pos_words)
    n = sum(1 for w in words if w in neg_words)
    total = p + n
    if total == 0:
        return "Neutral", 50.0
    score = (p / total) * 100
    if p > n:
        return "Positive", round(score, 1)
    elif n > p:
        return "Negative", round(100 - score, 1)
    return "Neutral", 50.0

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Campus Hub</title>
    <style>
        body { background-color: #f8f9fa; font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; color: #333; }
        .navbar { background-color: #212529; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
        .navbar a { color: white; text-decoration: none; margin-left: 20px; font-weight: 500; }
        .navbar a:hover { color: #adb5bd; }
        .container { max-width: 1100px; margin: 30px auto; padding: 0 15px; }
        .card { background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); padding: 25px; margin-bottom: 20px; border: 1px solid #dee2e6; }
        .btn { background: #0d6efd; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; }
        .btn:hover { background: #0b5ed7; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #bb2d3b; }
        .btn-sm { padding: 5px 10px; font-size: 0.85rem; }
        .form-control, .form-select { width: 100%; padding: 10px; margin-top: 5px; margin-bottom: 15px; border: 1px solid #ced4da; border-radius: 5px; box-sizing: border-box; }
        .row { display: flex; gap: 20px; flex-wrap: wrap; }
        .col-md-5 { flex: 1; min-width: 300px; }
        .col-md-7 { flex: 1.4; min-width: 300px; }
        .badge { background: #198754; color: white; padding: 5px 10px; border-radius: 4px; font-size: 0.9rem; float: right; }
        .badge-primary { background: #0d6efd; }
        .alert { background: #d1e7dd; color: #0f5132; padding: 12px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #badbcc; }
        details summary { cursor: pointer; font-weight: bold; color: #0d6efd; margin-top: 10px; }
        .details-content { background: #f1f3f5; padding: 12px; border-radius: 5px; margin-top: 8px; font-size: 0.9rem; line-height: 1.5; white-space: pre-line; }
        h1, h4, h5 { margin-top: 0; }
        ul { padding-left: 20px; }
    </style>
</head>
<body>
    <div class="navbar">
        <a href="/" style="font-size: 1.2rem; margin-left: 0;">🎓 AI Campus Hub</a>
        <div>
            <a href="/">Dashboard & AI Matcher</a>
            <a href="/resume_audit">🤖 AI Auditor</a>
            <a href="/activities">Manage Activities</a>
            <a href="/ai_insights">Sentiment Analyzer</a>
        </div>
    </div>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for cat, msg in messages %}
                    <div class="alert">✨ {{ msg }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% if page == 'dashboard' %}
        <div class="card" style="text-align: center; padding: 40px;">
            <h1 style="color: #0d6efd;">AI Activity Recommendation Engine</h1>
            <p style="color: #6c757d;">Type any skills, sports, or hobbies (e.g. badminton, cooking, python) to find matching campus activities.</p>
            <form method="POST" style="display: flex; justify-content: center; gap: 10px; margin-top: 20px;">
                <input type="text" name="interests" class="form-control" placeholder="e.g. badminton, cooking, python..." value="{{ query_interests }}" style="max-width: 400px; margin-bottom: 0;" required>
                <button type="submit" class="btn" style="width: auto;">🤖 Run AI Matcher</button>
            </form>
        </div>
        {% if recommendations %}
        <h3>🎯 AI Recommendations for "{{ query_interests }}"</h3>
        <div class="row">
            {% for rec in recommendations %}
            <div class="col-md-5" style="margin-bottom: 15px;">
                <div class="card" style="height: 100%;">
                    <span class="badge">Match: {{ rec.score }}%</span>
                    <h4 style="color: #212529; margin-bottom: 5px;">{{ rec.activity.title }}</h4>
                    <small style="color: #6c757d; font-weight: bold;">Category: {{ rec.activity.category }}</small>
                    <p style="margin-top: 10px; color: #555;">{{ rec.activity.description }}</p>
                    <details>
                        <summary>📌 View Requirements & Course Plan</summary>
                        <div class="details-content">
                            <p style="margin: 0 0 8px 0;"><strong>🛠️ Required Skills & Prerequisites:</strong><br>{{ rec.activity.requirements }}</p>
                            <p style="margin: 0;"><strong>📋 Step-by-Step Course Plan:</strong><br>{{ rec.activity.course_plan }}</p>
                        </div>
                    </details>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% elif page == 'resume_audit' %}
        <div class="row">
            <div class="col-md-5">
                <div class="card">
                    <h4>🤖 Generative AI Auditor</h4>
                    <p style="font-size: 0.9rem; color: #6c757d;">Upload a PDF/text transcript or paste text below.</p>
                    <form method="POST" enctype="multipart/form-data">
                        <label>Student Name</label><input type="text" name="student_name" class="form-control" required>
                        <label>Document Type</label>
                        <select name="doc_type" class="form-select">
                            <option value="Exam Result">Exam Result / Transcript</option>
                            <option value="Resume">Resume / CV</option>
                        </select>
                        <label style="font-weight: bold; color: #0d6efd;">📁 Upload Document File (PDF/TXT)</label>
                        <input type="file" name="doc_file" class="form-control">
                        <label>OR Paste Text Content</label>
                        <textarea name="doc_content" class="form-control" rows="4" placeholder="Paste result text here..."></textarea>
                        <button type="submit" class="btn" style="width: 100%;">✨ Run Dynamic AI Audit</button>
                    </form>
                </div>
            </div>
            <div class="col-md-7">
                <h4>Audited Reports & Feedback History</h4>
                {% if latest_audit %}
                <div class="card" style="border-left: 5px solid #0d6efd; background: #fff;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h5 style="margin: 0;">{{ latest_audit.student_name }}'s {{ latest_audit.doc_type }} Report</h5>
                        <span class="badge badge-primary" style="float: none;">Score: {{ latest_audit.rating_score }} / 100</span>
                    </div>
                    {% if latest_audit.filename %}
                    <small style="color: #6c757d; display: block; margin-top: 5px;">File: <strong>{{ latest_audit.filename }}</strong></small>
                    {% endif %}
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 15px 0;">
                    <div>{{ latest_audit.feedback_report | safe }}</div>
                </div>
                {% endif %}

                <h5 style="margin-top: 25px; color: #555;">All Past Audits</h5>
                {% for res in audits %}
                <div class="card" style="padding: 15px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>{{ res.student_name }} ({{ res.doc_type }})</strong>
                            <span class="badge" style="background: #6c757d; float: none; margin-left: 10px;">Score: {{ res.rating_score }}%</span>
                        </div>
                        <a href="/delete_audit/{{ res.id }}" class="btn btn-danger btn-sm" onclick="return confirm('Are you sure you want to delete this audit?');">🗑️ Delete</a>
                    </div>
                    {% if res.filename %}
                    <small style="color: #0d6efd; margin-top: 5px; display: block;">📄 File: {{ res.filename }}</small>
                    {% endif %}
                    <details style="margin-top: 5px;">
                        <summary>🔍 Click to view saved report details</summary>
                        <div class="details-content">
                            {{ res.feedback_report | safe }}
                        </div>
                    </details>
                </div>
                {% endfor %}
            </div>
        </div>
        {% elif page == 'activities' %}
        <div class="row">
            <div class="col-md-5">
                <div class="card">
                    <h4>Add Activity</h4>
                    <form action="/add_activity" method="POST">
                        <label>Title</label><input type="text" name="title" class="form-control" required>
                        <label>Category</label><input type="text" name="category" class="form-control" required>
                        <label>Description</label><textarea name="description" class="form-control" rows="2" required></textarea>
                        <label>Skills / Keywords</label><input type="text" name="skills" class="form-control" required>
                        <label>Requirements</label><input type="text" name="requirements" class="form-control" required>
                        <label>Course Plan</label><textarea name="course_plan" class="form-control" rows="2" required></textarea>
                        <button type="submit" class="btn" style="background: #212529; width: 100%;">Save Activity</button>
                    </form>
                </div>
            </div>
            <div class="col-md-7">
                <h4>All Campus Activities</h4>
                {% for act in activities %}
                <div class="card" style="padding: 15px; margin-bottom: 10px;">
                    <h5 style="color: #0d6efd; margin-bottom: 5px;">{{ act.title }} <span class="badge" style="background: #6c757d;">{{ act.category }}</span></h5>
                    <p style="margin: 0; color: #555;">{{ act.description }}</p>
                    <details>
                        <summary>📌 View Requirements & Course Plan</summary>
                        <div class="details-content">
                            <p style="margin: 0 0 8px 0;"><strong>🛠️ Required Skills & Prerequisites:</strong><br>{{ act.requirements }}</p>
                            <p style="margin: 0;"><strong>📋 Step-by-Step Course Plan:</strong><br>{{ act.course_plan }}</p>
                        </div>
                    </details>
                </div>
                {% endfor %}
            </div>
        </div>

        {% elif page == 'ai_insights' %}
        <div class="row">
            <div class="col-md-5">
                <div class="card">
                    <h4>🧠 AI Sentiment Analyzer</h4>
                    <form method="POST">
                        <label>Student Name</label><input type="text" name="student_name" class="form-control" required>
                        <label>Feedback</label><textarea name="comments" class="form-control" rows="3" required></textarea>
                        <button type="submit" class="btn" style="background: #198754; width: 100%;">Analyze & Save</button>
                    </form>
                </div>
            </div>
            <div class="col-md-7">
                <h4>Feedback Records</h4>
            if name and content_text:    {% for fb in feedbacks %}
                <div class="card" style="padding: 15px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between;">
                        <strong>{{ fb.student_name }}</strong>
                        <span class="badge" style="background: #198754;">{{ fb.sentiment }} ({{ fb.score }}%)</span>
                    </div>
                    <p style="margin: 5px 0 0 0; color: #555;">"{{ fb.comments }}"</p>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def dashboard():
    recommendations, query_interests = [], ""
    if request.method == "POST":
        query_interests = request.form.get("interests", "")
        if query_interests:
            recommendations = ai_recommend_activities(query_interests)
    return render_template_string(TEMPLATE, page="dashboard", recommendations=recommendations, query_interests=query_interests)

@app.route("/resume_audit", methods=["GET", "POST"])
def resume_audit():
    latest_audit = None
    if request.method == "POST":
        name = request.form.get("student_name")
        doc_type = request.form.get("doc_type")
        content_text = request.form.get("doc_content", "").strip()
        uploaded_file = request.files.get("doc_file")
        filename = ""

        if uploaded_file and uploaded_file.filename != "":
            filename = uploaded_file.filename
            file_path = UPLOAD_FOLDER / filename
            uploaded_file.save(file_path)

            try:
                if filename.lower().endswith('.pdf'):
                    from pypdf import PdfReader
                    reader = PdfReader(file_path)
                    pdf_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                    if pdf_text:
                        content_text = pdf_text
                else:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_text = f.read().strip()
                        if file_text:
                            content_text = file_text
            except Exception as e:
                pass

        
            
            if name and content_text:
                try:
                    score, report_html = ai_audit_document_with_gemini(
                        doc_type, content_text
                    )

                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute(
                            """INSERT INTO resumes
                            (student_name, doc_type, filename, content,
                             rating_score, feedback_report)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                name, doc_type, filename,
                                content_text, score, report_html
                            )
                        )

                    flash(
                        f"AI audit completed successfully for "
                        f"{filename or 'text input'}!",
                        "success"
                    )

                except Exception:
                    import logging
                    logging.exception("Gemini resume audit failed")
                    flash(
                        "AI audit failed. Check the VS Code terminal "
                        "for the exact error.",
                        "error"
                    )

            elif name:
                flash(
                    "No readable text found. Please upload a text-based "
                    "PDF or TXT file, or enter document text.",
                    "error"
                )

            return redirect(url_for("resume_audit"))


    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        audits = conn.execute("SELECT * FROM resumes ORDER BY id DESC").fetchall()
        if audits:
            latest_audit = audits[0]
    return render_template_string(TEMPLATE, page="resume_audit", audits=audits, latest_audit=latest_audit)

@app.route("/delete_audit/<int:audit_id>")
def delete_audit(audit_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM resumes WHERE id = ?", (audit_id,))
    flash("Audit record deleted successfully!", "success")
    return redirect(url_for("resume_audit"))

@app.route("/activities")
def activities():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        all_acts = conn.execute("SELECT * FROM activities").fetchall()
    return render_template_string(TEMPLATE, page="activities", activities=all_acts)

@app.route("/add_activity", methods=["POST"])
def add_activity():
    if request.form.get("title"):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO activities (title, category, description, skills, requirements, course_plan) VALUES (?, ?, ?, ?, ?, ?)",
                         (request.form.get("title"), request.form.get("category"), request.form.get("description"), request.form.get("skills"), request.form.get("requirements"), request.form.get("course_plan")))
    flash("Activity added successfully!", "success")
    return redirect(url_for("activities"))

@app.route("/ai_insights", methods=["GET", "POST"])
def ai_insights():
    if request.method == "POST":
        name, comm = request.form.get("student_name"), request.form.get("comments")
        if name and comm:
            sentiment, score = ai_analyze_sentiment(comm)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT INTO feedback (student_name, comments, sentiment, score) VALUES (?, ?, ?, ?)", (name, comm, sentiment, score))
            flash("AI Feedback Processed!", "success")
            return redirect(url_for("ai_insights"))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        feedbacks = conn.execute("SELECT * FROM feedback ORDER BY id DESC").fetchall()
    return render_template_string(TEMPLATE, page="ai_insights", feedbacks=feedbacks)

if __name__ == "__main__":
    app.run(debug=True, port=5000)