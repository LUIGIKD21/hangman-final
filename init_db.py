import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# --- Configuration (Must mirror app.py for DB setup) ---

app = Flask(__name__)

# This script only needs the DATABASE_URL environment variable to run.
db_url = os.environ.get('DATABASE_URL')
# For local testing, you could set this to the fallback, but for deployment, it must be set.
if not db_url:
    print("WARNING: DATABASE_URL environment variable not found. Using local fallback.")
    db_url = 'sqlite:///local_fallback.db'

# Check and fix for SQLAlchemy compatibility (common issue with Render's default URL format)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Model (Must mirror the class in app.py) ---
class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), unique=True, nullable=False)
    genre = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Word {self.word} | Genre {self.genre}>'

# --- Initial Word Data (Your original list) ---
INITIAL_WORD_DATA = [
    ("Technology", "PYTHON"), ("Technology", "FLASK"), ("Technology", "JAVASCRIPT"), 
    ("Technology", "DATABASE"), ("Technology", "ALGORITHM"), ("Technology", "SERVER"),
    ("Animals", "ELEPHANT"), ("Animals", "GIRAFFE"), ("Animals", "TIGER"), 
    ("Animals", "PENGUIN"), ("Animals", "KANGAROO"), ("Animals", "SQUIRREL"),
    ("Sports", "BASKETBALL"), ("Sports", "FOOTBALL"), ("Sports", "SOCCER"), 
    ("Sports", "HOCKEY"), ("Sports", "TENNIS"), ("Sports", "VOLLEYBALL"), 
    ("Sports", "MARATHON"), ("Sports", "TOUCHDOWN")
]

# --- Database Seeding Logic ---
def seed_database():
    """Creates tables and inserts initial data if the Word table is empty."""
    with app.app_context():
        # Create all tables defined in the models
        db.create_all()
        
        # Check if any words exist to prevent inserting duplicates on every build
        if Word.query.count() == 0:
            print("--- Seeding database ---")
            for genre, word_text in INITIAL_WORD_DATA:
                new_word = Word(word=word_text, genre=genre)
                db.session.add(new_word)
            
            db.session.commit()
            print(f"Successfully added {len(INITIAL_WORD_DATA)} words.")
        else:
            print("Database already seeded. Skipping word insertion.")

if __name__ == '__main__':
    seed_database()