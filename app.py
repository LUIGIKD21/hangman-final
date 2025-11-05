import random
import os
import requests 
import sys
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- Configuration and Data ---
app = Flask(__name__)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
# For deployment, remove this line and set SECRET_KEY in Render's dashboard.
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_key_for_hangman_game_123') 

MAX_LIVES = 6

# --- Database Configuration ---
# Get DATABASE_URL from environment variables
db_url = os.environ.get('DATABASE_URL')

if not db_url:
    print("FATAL ERROR: DATABASE_URL environment variable not found.", file=sys.stderr)
    # Use a local SQLite database for local fallback testing only
    db_url = 'sqlite:///hangman_data.db' 

# Fix for SQLAlchemy compatibility with Render's postgres URL format
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- NEW API CONFIGURATION ---
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
HANGMAN_STAGES = [
    """
       -----
       |   |
           |
           |
           |
           -
    """, # 0 misses (6 lives)
    """
       -----
       |   |
       O   |
           |
           |
           -
    """, # 1 miss (5 lives)
    """
       -----
       |   |
       O   |
       |   |
           |
           -
    """, # 2 misses (4 lives)
    """
       -----
       |   |
       O   |
      /|   |
           |
           -
    """, # 3 misses (3 lives)
    """
       -----
       |   |
       O   |
      /|\\  |
           |
           -
    """, # 4 misses (2 lives)
    """
       -----
       |   |
       O   |
      /|\\  |
      /    |
           -
    """, # 5 misses (1 life)
    """
       -----
       |   |
       O   |
      /|\\  |
      / \\  |
           -
    """ # 6 misses (0 lives) - GAME OVER
]

# --- Database Models (User and Game) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # INCREASED from 128 to 256 characters to accommodate long scrypt password hashes
    password_hash = db.Column(db.String(256), nullable=False) 
    
    # Relationship to Game statistics
    game_stats = db.relationship('Game', backref='player', uselist=False, lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)

    def total_games(self):
        return self.wins + self.losses

    def win_rate(self):
        total = self.total_games()
        return f"{(self.wins / total) * 100:.2f}%" if total > 0 else "0.00%"

# --- Helper Functions ---

def get_display_word(word, guessed_letters):
    """Returns the word with unguessed letters replaced by underscores."""
    return ' '.join([letter if letter in guessed_letters else '_' for letter in word])

def initialize_game_session(genre="Technology"):
    """Resets the session state for a new game."""
    session['word'] = None # Forces a new word fetch
    session['guessed_letters'] = []
    session['lives'] = MAX_LIVES
    session['is_game_over'] = False
    session['message'] = "Guess a letter to start!"
    session['genre'] = genre

def fetch_random_word_by_genre(genre):
    """
    Fetches a random word related to the specified genre using WordsAPI.
    
    CRITICAL FIX: Uses the 'topic' parameter for filtering.
    """
    # Fallback to an easy word if API key is missing
    if not RAPIDAPI_KEY or not RAPIDAPI_HOST:
        print("API Keys missing. Falling back to local data.", file=sys.stderr)
        return random.choice(["PROGRAMMER", "FLASK", "DEVELOPER"])

    headers = {
        'x-rapidapi-host': RAPIDAPI_HOST,
        'x-rapidapi-key': RAPIDAPI_KEY
    }
    
    # 1. Attempt to search by topic
    params = {
        'random': 'true',
        'limit': 1,
        'topic': genre.lower() # Filter by the selected genre
    }
    
    try:
        response = requests.get(EXTERNAL_WORD_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status() # Raises HTTPError for bad status codes
        data = response.json()
        
        # WordsAPI returns a list of words under the 'words' key
        if data and 'words' in data and len(data['words']) > 0:
            word = data['words'][0].upper()
            return word
        
        # 2. Fallback: If topic search returns no words, try a general random word
        print(f"API returned no word for topic '{genre}'. Falling back to general random word.", file=sys.stderr)
        params_general = {'random': 'true', 'limit': 1}
        response = requests.get(EXTERNAL_WORD_API_URL, headers=headers, params=params_general, timeout=10)
        response.raise_for_status()
        data_general = response.json()
        
        if data_general and 'words' in data_general and len(data_general['words']) > 0:
             return data_general['words'][0].upper()

        # 3. Final Fallback: Use a hardcoded word
        return random.choice(["DEFAULT", "GENERIC", "HANGMAN"])


    except requests.exceptions.RequestException as err:
        print(f"API Request Error: {err}", file=sys.stderr)
        return random.choice(["APIERROR", "NETWORK"])
    except Exception as e:
        print(f"General error during API call: {e}", file=sys.stderr)
        return random.choice(["EXCEPTION", "FAILURE"])


def update_user_stats(user_id, is_win):
    """Updates the user's game statistics in the database."""
    with app.app_context():
        game_stats = Game.query.filter_by(user_id=user_id).first()
        if not game_stats:
            game_stats = Game(user_id=user_id, wins=0, losses=0)
            db.session.add(game_stats)
        
        if is_win:
            game_stats.wins += 1
        else:
            game_stats.losses += 1
            
        db.session.commit()

def get_user_stats_data(user_id):
    """Fetches user stats and formats them for the template."""
    with app.app_context():
        user = User.query.get(user_id)
        if user and user.game_stats:
            stats = user.game_stats
            return {
                'username': user.username,
                'wins': stats.wins,
                'losses': stats.losses,
                'total_games': stats.total_games(),
                'win_rate': stats.win_rate()
            }
        return {'username': 'Guest', 'wins': 0, 'losses': 0, 'total_games': 0, 'win_rate': '0.00%'}

# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def hangman_game():
    user_id = session.get('user_id')
    user_stats = get_user_stats_data(user_id)
    is_logged_in = user_id is not None
    
    # 1. Handle POST Requests (New Game or Guess)
    if request.method == 'POST':
        # Check if the request is to start a NEW GAME (via genre select form)
        if 'genre_select' in request.form:
            selected_genre = request.form['genre_select']
            initialize_game_session(genre=selected_genre)
            # The game state is now reset, so continue to fetch/render
        
        # Check if the request is a LETTER GUESS
        elif 'letter' in request.form and not session.get('is_game_over', False):
            guess = request.form['letter'].upper()
            
            word_to_guess = session.get('word')
            guessed_set = set(session.get('guessed_letters', []))
            lives = session.get('lives')
            
            if not guess.isalpha() or len(guess) != 1:
                session['message'] = "🚨 Invalid input. Please enter a single letter (A-Z)."
            elif guess in guessed_set:
                session['message'] = f"✅ You already guessed **{guess}**."
            elif guess in word_to_guess:
                guessed_set.add(guess)
                session['message'] = f"🎉 Good guess! **{guess}** is in the word."
            else:
                guessed_set.add(guess)
                session['lives'] -= 1
                session['message'] = f"❌ Wrong guess. **{guess}** is not in the word."
            
            # Convert the set back to a list before saving to the session
            session['guessed_letters'] = list(guessed_set)

    # 2. Ensure Session State Exists (First load or new user)
    if 'word' not in session:
        # Get the word based on the stored genre (defaulting to Technology if not set)
        current_genre = session.get('genre', 'Technology')
        word_to_guess = fetch_random_word_by_genre(current_genre)
        
        # Initialize full game state
        session['word'] = word_to_guess
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['is_game_over'] = False
        session['message'] = "Guess a letter to start!"
    
    # Re-fetch current state
    word_to_guess = session.get('word').upper()
    guessed_set = set(session.get('guessed_letters', []))
    lives = session.get('lives')
    is_game_over = session.get('is_game_over')
    current_genre = session.get('genre')
    message = session.get('message', "")
    
    # 3. Update display word and check for Win/Loss state
    display_word = get_display_word(word_to_guess, guessed_set)
    is_win = "_" not in display_word
    is_loss = lives <= 0
    
    if not is_game_over:
        if is_win:
            is_game_over = True
            session['is_game_over'] = True
            session['message'] = f"🎉 YOU WON! The word was **{word_to_guess}**."
            if user_id: update_user_stats(user_id, True)
        elif is_loss:
            is_game_over = True
            session['is_game_over'] = True
            session['message'] = f"💀 GAME OVER. The word was **{word_to_guess}**."
            if user_id: update_user_stats(user_id, False)

    # If the game is over, use the final message from the session
    if is_game_over:
        message = session.get('message')
    
    # 4. Render the template with the current state
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
        genres=GENRE_LIST,
        current_genre=current_genre,
        is_logged_in=is_logged_in,
        user_stats=user_stats
    )

@app.route('/restart', methods=['GET'])
def restart():
    """Starts a new game, keeping the current genre."""
    current_genre = session.get('genre', 'Technology')
    initialize_game_session(genre=current_genre)
    return redirect(url_for('hangman_game'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            error = "Username already taken. Please choose another."
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            
            # Create associated game stats entry immediately
            new_stats = Game(player=new_user) 
            
            db.session.add_all([new_user, new_stats])
            
            try:
                db.session.commit()
                # Log the user in immediately after registration
                session['user_id'] = new_user.id
                # Initialize their game to start fresh
                initialize_game_session(genre=session.get('genre', 'Technology'))
                return redirect(url_for('hangman_game'))
            except Exception as e:
                db.session.rollback()
                print(f"Database error during registration: {e}", file=sys.stderr)
                error = "An unexpected error occurred. Please try again."

    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            # Log successful login
            print(f"User {username} logged in successfully.")
            return redirect(url_for('hangman_game'))
        else:
            error = "Invalid username or password."
            # Log failed login attempt
            print(f"Failed login attempt for username: {username}", file=sys.stderr)

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    # Re-initialize game session to clear user-specific data
    initialize_game_session(genre=session.get('genre', 'Technology'))
    return redirect(url_for('hangman_game'))

# --- Main Run Block (For local testing only) ---
# NOTE: The Render server will use gunicorn and ignore this block.
if __name__ == '__main__':
    with app.app_context():
        # This will create tables if they don't exist
        db.create_all()
    app.run(debug=True)