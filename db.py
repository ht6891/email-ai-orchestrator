import sqlite3

def init_db():
    conn = sqlite3.connect("email_analysis.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            sender TEXT,
            subject TEXT,
            original_body TEXT,
            cleaned_body TEXT,
            summary TEXT,
            sentiment_label TEXT,
            sentiment_score REAL,
            reply TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_email(email_data):
    conn = sqlite3.connect("email_analysis.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO email_analysis 
        (email_id, sender, subject, original_body, cleaned_body, summary, sentiment_label, sentiment_score, reply) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        email_data["email_id"],
        email_data["sender"],
        email_data["subject"],
        email_data["original_body"],
        email_data["cleaned_body"],
        email_data["summary"],
        email_data["sentiment_label"],
        email_data["sentiment_score"],
        email_data["reply"]
    ))
    conn.commit()
    conn.close()
