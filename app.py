import random
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy # NEW: Database ORM import

# --- Configuration and Database Setup ---

app = Flask(__name__)

# 1. SECRET KEY: IMPORTANT for session security. Use environment variable first.
app.secret_key = os.environ.get('SECRET_KEY', 'a_secure_default_key_for_local_testing') 

MAX_LIVES = 6

# 2. DATABASE CONFIGURATION (PostgreSQL-Ready)
# Render provides the DB connection string via the DATABASE_URL environment variable.
db_url = os.environ.get('DATABASE_URL')

# Check and fix for SQLAlchemy compatibility if URL starts with 'postgres://' 
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Use PostgreSQL URL if available, otherwise fall back to SQLite for local development
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///local_fallback.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app) # Initialize the SQLAlchemy object

# --- Database Model (Data Structure) ---
class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), unique=True, nullable=False)
    genre = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Word {self.word} | Genre {self.genre}>'


# Simplified ASCII art for the Hangman stages (0 to 6 misses)
HANGMAN_STAGES = [
    """
       -----
       |   |
           |
           |
           |
           |
    ---------
    """,
    """
       -----
       |   |
       O   |
           |
           |
           |
    ---------
    """,
    """
       -----
       |   |
       O   |
       |   |
           |
           |
    ---------
    """,
    """
       -----
       |   |
       O   |
      /|   |
           |
           |
    ---------
    """,
    """
       -----
       |   |
       O   |
      /|\\  |
           |
           |
    ---------
    """,
    """
       -----
       |   |
       O   |
      /|\\  |
      /    |
           |
    ---------
    """,
    """
       -----
       |   |
       O   |
      /|\\  |
      / \\  |
           |
    ---------
    """
]

# --- Game Logic Functions ---

def get_genre_list():
    """Fetches unique, sorted genres dynamically from the database."""
    # Queries the Word table for distinct genre values
    genres = db.session.query(Word.genre).distinct().all()
    # Flattens the list of tuples and sorts them
    return sorted([g[0] for g in genres])

def initialize_game(genre=None):
    """Initializes or resets the game state in the session, fetching a word from the DB."""
    
    # Needs app context to interact with the database
    with app.app_context():
        GENRE_LIST = get_genre_list() # Get genres from DB

        # 1. Determine the genre to use
        if genre and genre in GENRE_LIST:
            target_genre = genre
        elif GENRE_LIST:
            # Default to a random genre if starting fresh
            target_genre = random.choice(GENRE_LIST)
        else:
            # Handle case where database is empty
            session['message'] = "Error: Database contains no words! Cannot start game."
            session['word'] = 'ERROR'
            return 

        # 2. Query the database for a random word in the selected genre
        word_records = Word.query.filter_by(genre=target_genre).all()
        if not word_records:
            session['message'] = f"Error: No words found for genre '{target_genre}'."
            session['word'] = 'ERROR'
            return 

        # Select a random word object and get its text
        selected_word_text = random.choice(word_records).word
    
    # 3. Update Session State
    session['word'] = selected_word_text.upper()
    session['guessed_letters'] = [] 
    session['lives'] = MAX_LIVES
    session['message'] = f"New Game! Genre: **{target_genre}**. Guess a letter to start!"
    session['genre'] = target_genre


def get_display_word(secret_word, guessed_letters_set):
    """Returns the word with unguessed letters as underscores."""
    display = ""
    for letter in secret_word:
        if letter in guessed_letters_set:
            display += letter + " "
        else:
            display += "_ "
    return display.strip()

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def hangman_game():
    
    # Ensure database is accessible for initial context
    with app.app_context():
        # Check if the user is trying to START a new game with a genre selection
        if request.method == 'POST' and 'genre_select' in request.form:
            selected_genre = request.form['genre_select']
            initialize_game(genre=selected_genre)
            return redirect(url_for('hangman_game'))

        # Initialize game if not already in session (first load)
        if 'word' not in session:
            initialize_game()

        word_to_guess = session.get('word')
        lives = session.get('lives')
        
        # Retrieve the list from the session, and immediately convert it to a set for efficient logic
        guessed_set = set(session.get('guessed_letters', []))
        
        is_game_over = False

        # 1. Handle Letter Guess (POST)
        if request.method == 'POST' and 'letter' in request.form:
            guess = request.form.get('letter', '').strip().upper()
            session['message'] = "" # Clear previous message

            if len(guess) == 1 and guess.isalpha():
                if guess in guessed_set:
                    session['message'] = f"You already guessed '{guess}'. Try a new letter."
                else:
                    guessed_set.add(guess)
                    
                    if guess not in word_to_guess:
                        session['lives'] -= 1
                        session['message'] = f"'{guess}' is NOT in the word. Lives left: {session['lives']}."
                    else:
                        session['message'] = f"Good guess! '{guess}' is in the word."
            else:
                session['message'] = "Invalid input. Please enter a single letter (A-Z)."

            # Convert the set back to a list before saving to the session
            session['guessed_letters'] = list(guessed_set)

            # Re-fetch updated state for rendering after POST
            lives = session.get('lives')
        
        # 2. Update display word and check for Win/Loss state
        display_word = get_display_word(word_to_guess, guessed_set)
        is_win = "_" not in display_word
        is_loss = lives <= 0
        
        message = session.get('message', "")
        
        if is_win:
            is_game_over = True
            message = f"🎉 YOU WON! The word was **{word_to_guess}**."
        elif is_loss:
            is_game_over = True
            message = f"💀 GAME OVER. The word was **{word_to_guess}**."

        # 3. Render the template with the current state
        lives_index = MAX_LIVES - lives
        
        return render_template(
            'index.html',
            display_word=display_word,
            lives=lives,
            message=message,
            guessed_letters=sorted(list(guessed_set)), 
            is_game_over=is_game_over,
            hangman_art=HANGMAN_STAGES[lives_index],
            max_lives=MAX_LIVES,
            genres=get_genre_list(), # Dynamically fetched from DB
            current_genre=session.get('genre')
        )

@app.route('/restart')
def restart():
    """Route to restart the game, defaulting to the current genre."""
    # Needs app context to interact with the database
    with app.app_context():
        initialize_game(genre=session.get('genre'))
    return redirect(url_for('hangman_game'))

# --- Execution ---

if __name__ == '__main__':
    # When running locally, you must first run 'python init_db.py' to seed the fallback DB
    app.run(debug=True)