import random
import os
import requests 
import uuid
import hashlib # Added for password hashing
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import select, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

# --- Configuration and Data ---
app = Flask(__name__)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
# For deployment, remove this line and set SECRET_KEY in Render's dashboard.
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_key_for_hangman_game_123') 

MAX_LIVES = 6

# --- API Configuration ---
# These values MUST be set as Environment Variables on Render!
RAPIDAPI_KEY = os.environ.get('X_RAPIDAPI_KEY')
RAPIDAPI_HOST = os.environ.get('X_RAPIDAPI_HOST', 'wordsapiv1.p.rapidapi.com')

# The base endpoint for searching and fetching words.
EXTERNAL_WORD_API_URL = "https://wordsapiv1.p.rapidapi.com/words/"


# Hardcoded GENRE LIST: These will be used to query the API.
GENRE_LIST = [
    "Animals", 
    "Sports", 
    "Technology"
]


# Simplified ASCII art for the Hangman stages (0 to 6 misses)
# FIX: Using raw strings (r"""...""") to prevent SyntaxWarnings for unescaped backslashes
HANGMAN_STAGES = [
r"""
 +---+
 |   |
     |
     |
     |
     |
=======""", 
r"""
 +---+
 |   |
 O   |
     |
     |
     |
=======""",
r"""
 +---+
 |   |
 O   |
 |   |
     |
     |
=======""",
r"""
 +---+
 |   |
 O   |
/|   |
     |
     |
=======""",
r"""
 +---+
 |   |
 O   |
/|\  |
     |
     |
=======""",
r"""
 +---+
 |   |
 O   |
/|\  |
/    |
     |
=======""",
r"""
 +---+
 |   |
 O   |
/|\  |
/ \  |
     |
======="""
]

# --- Database Setup (PostgreSQL/SQLAlchemy) ---
# Use the environment variable, or fall back to a local SQLite database for development
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hangman.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# --- Security Utilities (Mock Hashing) ---
# In a real-world application, you would use flask_bcrypt or werkzeug.security
# to securely hash passwords. This is a simplified, non-cryptographically-secure 
# version for demonstration purposes in this environment.
def set_password(password):
    """Simple password hashing simulation using SHA256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_password(password_hash, password):
    """Simple password checking simulation."""
    return password_hash == set_password(password)


# --- Database Models ---

# User Model Definition
class User(db.Model):
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    high_score: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self):
        return f'<User {self.username}>'


# --- API Functions ---

def get_word_from_api(genre, min_length=5, max_length=10):
    """
    Fetches a random word from the Words API based on a genre/topic.
    A longer word list improves reliability.
    """
    if not RAPIDAPI_KEY:
        print("Warning: RAPIDAPI_KEY is not set. Using fallback word list.")
        # Fallback word list if API key is missing
        fallback_words = {
            "Animals": ["elephant", "giraffe", "dolphin", "kangaroo", "cheetah"],
            "Sports": ["basketball", "football", "tennis", "swimming", "volleyball"],
            "Technology": ["computer", "keyboard", "internet", "software", "network"]
        }
        word = random.choice(fallback_words.get(genre, fallback_words["Animals"]))
        return word.lower()

    # The API endpoint is based on fetching a word that has the genre tag as a topic
    url = EXTERNAL_WORD_API_URL
    
    querystring = {
        "topics": genre.lower(),
        "lettersMin": str(min_length),
        "lettersMax": str(max_length),
        "limit": "1" # Limit to 1 word for simplicity
    }

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=5)
        response.raise_for_status() # Raise exception for bad status codes
        
        data = response.json()
        
        # The API structure for this endpoint is complex, but generally, 
        # it returns a word that matches the criteria. We must select a word from the list
        if data and 'results' in data and data['results']:
            # The API response format may vary, we expect 'word' to be a key in the results
            word_list = [item['word'] for item in data['results'] if 'word' in item]
            if word_list:
                # To be safe, let's filter for single words and choose one
                word = random.choice([w for w in word_list if ' ' not in w])
                return word.lower()
        
        # If API fails to provide a word, use a random one from the fallback list
        print(f"API failed to provide word for {genre}. Using fallback.")
        return random.choice(["hangman", "python", "flask", "coding", "render"]).lower()

    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}. Using fallback.")
        return random.choice(["elephant", "internet", "tennis", "application"]).lower()

# --- Auth Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Simple validation
        if not username or not password:
            return render_template('register.html', error='Username and password are required.')

        try:
            # Check if user already exists
            user_stmt = select(User).where(User.username == username)
            if db.session.scalar(user_stmt):
                return render_template('register.html', error='Username already taken. Please choose another.')

            # Create new user
            new_user = User(
                username=username,
                password_hash=set_password(password) # Store hashed password
            )
            db.session.add(new_user)
            db.session.commit()

            # Log in the user automatically after successful registration
            session['user_id'] = new_user.username
            session['is_authenticated'] = True
            
            # Start a new game and redirect to the game page
            return redirect(url_for('restart')) 

        except Exception as e:
            db.session.rollback()
            print(f"Registration Error: {e}")
            return render_template('register.html', error='An error occurred during registration.')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            user_stmt = select(User).where(User.username == username)
            user = db.session.scalar(user_stmt)

            if user and check_password(user.password_hash, password):
                session['user_id'] = user.username
                session['is_authenticated'] = True
                
                # Redirect to game or a specific user area
                return redirect(url_for('hangman_game'))
            else:
                return render_template('login.html', error='Invalid username or password.')

        except Exception as e:
            print(f"Login Error: {e}")
            return render_template('login.html', error='An error occurred during login.')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_authenticated', None)
    # Reset game state for good measure
    session.pop('word_to_guess', None)
    session.pop('guessed_letters', None)
    session.pop('lives', None)
    session.pop('message', None)
    return redirect(url_for('hangman_game'))

# --- Game Logic ---

def get_game_state(user):
    """Retrieves all necessary game variables from session and calculates display state."""
    
    # Initialize game state if not present (First load or new genre selected)
    if 'word_to_guess' not in session:
        current_genre = session.get('current_genre', GENRE_LIST[0])
        word_to_guess = get_word_from_api(current_genre)
        
        session['word_to_guess'] = word_to_guess
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['current_genre'] = current_genre
        session['message'] = f"Let's play Hangman! Category: **{current_genre}**"
    
    word_to_guess = session['word_to_guess']
    guessed_letters = session['guessed_letters']
    lives = session['lives']
    message = session['message']
    
    display_word = "".join([letter if letter in guessed_letters else '_' for letter in word_to_guess])
    
    # Check for win/loss
    win = '_' not in display_word
    lives_index = MAX_LIVES - lives
    is_game_over = win or (lives_index >= MAX_LIVES) # Corrected game over condition
    
    if win and "WON" not in message:
        session['message'] = f"CONGRATULATIONS! You WON! The word was '{word_to_guess.upper()}'."
        
        # --- High Score Logic ---
        if user:
            # Score = (Word Length * 10) + (Lives Remaining * 5)
            current_score = (len(word_to_guess) * 10) + (lives * 5)
            try:
                if current_score > user.high_score:
                    user.high_score = current_score
                    db.session.commit()
                    session['message'] += f" New High Score: {current_score}!"
                else:
                    session['message'] += f" Score: {current_score}."
            except Exception as e:
                print(f"Database error during score update: {e}")
                db.session.rollback()
        # --- End High Score Logic ---

    elif lives_index >= MAX_LIVES and "OVER" not in message:
        session['message'] = f"GAME OVER! The word was '{word_to_guess.upper()}'."
    
    # Re-fetch the high score just in case it was updated (or to get the initial one)
    high_score = user.high_score if user else 0

    return {
        'word_to_guess': word_to_guess,
        'guessed_letters': sorted(guessed_letters),
        'lives': lives,
        'display_word': display_word,
        'hangman_art': HANGMAN_STAGES[lives_index],
        'is_game_over': is_game_over,
        'message': session['message'],
        'lives_index': lives_index,
        'high_score': high_score
    }


@app.route('/', methods=['GET', 'POST'])
def hangman_game():
    
    # 1. Fetch User Data
    current_user = None
    if session.get('is_authenticated') and session.get('user_id'):
        user_stmt = select(User).where(User.username == session['user_id'])
        current_user = db.session.scalar(user_stmt)
    
    # 2. Handle POST Request (New Game or Guess)
    if request.method == 'POST':
        
        # A. Start New Game with Genre Selection
        if 'genre_select' in request.form:
            selected_genre = request.form['genre_select']
            
            # Reset game state and set new word/genre
            session['current_genre'] = selected_genre
            session['word_to_guess'] = get_word_from_api(selected_genre)
            session['guessed_letters'] = []
            session['lives'] = MAX_LIVES
            session['message'] = f"New game started! Category: **{selected_genre}**"
            
            return redirect(url_for('hangman_game'))

        # B. Handle Letter Guess
        elif 'letter' in request.form:
            game_state = get_game_state(current_user)
            if game_state['is_game_over']:
                return redirect(url_for('hangman_game')) # Prevent guessing after game over

            guess = request.form['letter'].lower()
            word_to_guess = session['word_to_guess']
            guessed_letters = session['guessed_letters']
            lives = session['lives']
            
            if guess in guessed_letters:
                session['message'] = f"You already guessed '{guess.upper()}'."
            elif guess.isalpha() and len(guess) == 1:
                guessed_letters.append(guess)
                session['guessed_letters'] = guessed_letters # Update session list
                
                if guess in word_to_guess:
                    session['message'] = f"Correct guess: '{guess.upper()}' is in the word!"
                else:
                    lives -= 1
                    session['lives'] = lives
                    session['message'] = f"Incorrect guess: '{guess.upper()}' is not in the word. {lives} lives remaining."
            else:
                session['message'] = "Invalid input. Please guess a single letter."

            # Update game state after the guess to check for win/loss
            game_state = get_game_state(current_user) # Recalculate and check for high score update if won

            return redirect(url_for('hangman_game'))

    # 3. Handle GET Request (Initial Load or Redirection)
    
    # Recalculate state, check for game end, and update high score if necessary
    game_state = get_game_state(current_user) 
    lives_index = game_state['lives_index']
    
    return render_template(
        'index.html',
        display_word=game_state['display_word'],
        guessed_letters=game_state['guessed_letters'],
        message=game_state['message'],
        is_game_over=game_state['is_game_over'],
        hangman_art=HANGMAN_STAGES[lives_index],
        max_lives=MAX_LIVES,
        genres=GENRE_LIST,
        current_genre=session.get('current_genre'),
        user_id=session.get('user_id'), # Pass username/ID
        high_score=game_state['high_score'] # Pass high score
    )


@app.route('/restart', methods=['GET'])
def restart():
    """Resets the game state while keeping the current genre."""
    
    current_genre = session.get('current_genre', GENRE_LIST[0])
    word_to_guess = get_word_from_api(current_genre)

    session['word_to_guess'] = word_to_guess
    session['guessed_letters'] = []
    session['lives'] = MAX_LIVES
    session['message'] = f"New game started! Category: **{current_genre}**"
    
    return redirect(url_for('hangman_game'))


# To allow `flask db init/migrate/upgrade` to work:
with app.app_context():
    # Attempt to create tables only if they don't exist
    try:
        # Check if the tables exist before calling create_all
        # This prevents issues with subsequent runs in some environments
        # For simplicity, we just try/catch create_all as this environment handles migrations well.
        db.create_all()
    except Exception as e:
        # Log if create_all fails (e.g., if tables already exist via a migration)
        print(f"Database table creation check failed (likely tables already exist): {e}")

if __name__ == '__main__':
    # In a production deployment (like Render), gunicorn is used, not app.run()
    # This block is for local development only
    app.run(debug=True, port=os.environ.get("PORT", 5000))