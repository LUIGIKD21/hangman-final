import random
import os
import requests 
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- Configuration and Data ---
app = Flask(__name__)

# Secret key for sessions (MUST be set as an ENV var on Render for production!)
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_default_key_123') 

MAX_LIVES = 6

# --- API CONFIGURATION ---
RAPIDAPI_KEY = os.environ.get('X_RAPIDAPI_KEY')
RAPIDAPI_HOST = os.environ.get('X_RAPIDAPI_HOST', 'wordsapiv1.p.rapidapi.com')
EXTERNAL_WORD_API_URL = "https://wordsapiv1.p.rapidapi.com/words/"

# --- NEW: DATABASE CONFIGURATION ---
# Get the database URL from Render's environment variables
db_url = os.environ.get('DATABASE_URL')
# SQLAlchemy requires 'postgresql' scheme instead of 'postgres' for Render/Heroku compatibility
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///local_development.db' # Fallback for local testing
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- NEW: DATABASE MODELS ---
# Defines the tables for users and their game scores
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    # Relationship to access all games played by this user
    games = db.relationship('Game', backref='player', lazy='dynamic') 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    tries = db.Column(db.Integer, nullable=False) # Number of guesses used (MAX_LIVES - lives_remaining)
    won = db.Column(db.Boolean, nullable=False)
    # Foreign key links this game back to the User table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


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

# --- Game Logic Functions (unchanged from your API version) ---

def fetch_word_from_api(genre):
    """
    Fetches a random word related to the genre from WordsAPI.
    """
    if not RAPIDAPI_KEY:
        print("Configuration Error: X_RAPIDAPI_KEY is missing. Using fallback word.")
        if genre == "Animals":
            return "WOLF"
        elif genre == "Sports":
            return "GOAL"
        elif genre == "Technology":
            return "CODE"
        else:
            return "FALLBACK"

    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }

    params = {
        'random': 'true', 
        'rel_jja': genre, 
        'lettersMax': 10, 
        'hasDetails': 'frequency',
    }

    try:
        response = requests.get(EXTERNAL_WORD_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status() 
        
        data = response.json()
        
        if data and 'word' in data and data['word'].isalpha():
            return data['word'].upper()
        else:
            print(f"API Error: Received unexpected data or no word found for genre '{genre}'. Raw response: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"API Connection Error: {e}")
        return None


def initialize_game(genre=None):
    """Initializes or resets the game state in the session, fetching a genre-specific word."""
    
    if genre and genre in GENRE_LIST:
        target_genre = genre
    elif GENRE_LIST:
        target_genre = random.choice(GENRE_LIST)
    else:
        session['message'] = "Error: No genres available! Cannot start game."
        return 

    selected_word = fetch_word_from_api(target_genre)
    
    if not selected_word:
        session['message'] = f"Error: Could not fetch a word from the API for '{target_genre}'. Using hardcoded fallback."
        selected_word = "API_FAIL" 
        
    session['word'] = selected_word
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

# --- Flask Routes (New Auth Routes) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('hangman_game'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', error="Username already taken! Please choose another.")
            
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        return redirect(url_for('hangman_game'))
        
    return render_template('register.html', error=None) 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('hangman_game'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('hangman_game'))
        else:
            return render_template('login.html', error="Invalid username or password.")
            
    return render_template('login.html', error=None) 

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('hangman_game'))

# --- Flask Routes (Main Game) ---

@app.route('/', methods=['GET', 'POST'])
def hangman_game():
    
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

    # --- NEW: SAVE GAME RESULT ---
    # Only save if the user is logged in AND the game just finished
    if is_game_over and 'user_id' in session:
        user_id = session['user_id']
        tries_used = MAX_LIVES - lives
        
        # Simple check to prevent double-save on refresh after game over
        last_game = Game.query.filter_by(user_id=user_id).order_by(Game.id.desc()).first()
        
        if not last_game or last_game.word != word_to_guess or last_game.won != is_win:
            new_game = Game(
                word=word_to_guess,
                tries=tries_used,
                won=is_win,
                user_id=user_id
            )
            db.session.add(new_game)
            db.session.commit()
            print(f"Saved game result for User {user_id}: Won={is_win}, Tries={tries_used}")
            
    # --- END SAVE GAME RESULT ---


    # 3. Fetch user stats for display (if logged in)
    user_stats = {}
    is_logged_in = 'user_id' in session
    if is_logged_in:
        user = User.query.get(session['user_id'])
        # Handle case where user might have been deleted (shouldn't happen, but good practice)
        if user:
            total_games = user.games.count()
            wins = user.games.filter_by(won=True).count()
            user_stats = {
                'username': user.username,
                'total_games': total_games,
                'wins': wins,
                'losses': total_games - wins,
                'win_rate': f"{(wins / total_games * 100):.1f}%" if total_games > 0 else "0%"
            }
        else:
             session.pop('user_id', None) # Log out if user ID is invalid
             is_logged_in = False


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
        current_genre=session.get('genre'),
        # Pass new variables to the template
        is_logged_in=is_logged_in, 
        user_stats=user_stats
    )

@app.route('/restart')
def restart():
    """Route to restart the game, defaulting to the current genre."""
    initialize_game(genre=session.get('genre'))
    return redirect(url_for('hangman_game'))

# --- Execution & Table Creation ---

# This command ensures all database tables are created when the app starts.
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)