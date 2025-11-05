import random
import os
import requests 
from flask import Flask, render_template, request, redirect, url_for, session, current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, OperationalError
import logging # Use for better logging/debugging

# --- Configuration and Data ---
app = Flask(__name__)
# Set up logging for better debugging
app.logger.setLevel(logging.INFO)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_key_for_hangman_game_123') 

MAX_LIVES = 6

# --- NEW API CONFIGURATION ---
RAPIDAPI_KEY = os.environ.get('X_RAPIDAPI_KEY')
RAPIDAPI_HOST = os.environ.get('X_RAPIDAPI_HOST', 'wordsapiv1.p.rapidapi.com')
EXTERNAL_WORD_API_URL = "https://wordsapiv1.p.rapidapi.com/words/"

# Hardcoded GENRE LIST
GENRE_LIST = [
    "Animals", 
    "Sports", 
    "Technology"
]

# --- Database Configuration ---
# Use the DATABASE_URL environment variable (standard for Render Postgres) or default to SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hangman.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Relationship for stats (one-to-one or one-to-zero)
    stats = db.relationship('GameStats', backref='player', lazy=True, uselist=False)

    def __repr__(self):
        return f"<User id={self.id}>"

class GameStats(db.Model):
    __tablename__ = 'game_stats'
    id = db.Column(db.Integer, primary_key=True)
    # The ForeignKey relationship that was failing
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<GameStats user_id={self.user_id}, wins={self.wins}, losses={self.losses}>"

# --- Database Initialization ---
# This ensures tables are created when the app starts
with app.app_context():
    try:
        db.create_all()
        app.logger.info("Database tables created successfully.")
    except OperationalError as e:
        # Catch errors if running against a remote DB without initial setup
        app.logger.warning(f"Could not create tables (may already exist or permission issue): {e}")


# --- User and Stats Utilities ---

def get_or_create_user():
    """
    Ensures a User exists for the current session, creating one if necessary.
    Returns the User object.
    """
    user_id = session.get('user_id')
    user = None
    
    if user_id:
        user = User.query.get(user_id)

    if user is None:
        # Create a new anonymous user if one isn't found in the session or DB
        user = User()
        db.session.add(user)
        try:
            db.session.commit()
            session['user_id'] = user.id
            current_app.logger.info(f"Created new anonymous user with ID: {user.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create new user: {e}")
            return None
            
    return user

def get_user_stats(user_id):
    """
    Retrieves the GameStats for a given user ID.
    Returns (wins, losses) tuple or (0, 0) if no stats found.
    """
    if user_id is None:
        return 0, 0
        
    stats = GameStats.query.filter_by(user_id=user_id).first()
    if stats:
        return stats.wins, stats.losses
    return 0, 0


def update_user_stats(user_id, is_win):
    """
    Updates the user's win/loss record.
    If a GameStats record does not exist for the user, it creates one.
    """
    if user_id is None:
        current_app.logger.warning("Attempted to update stats without a user_id.")
        return

    # Find the GameStats record for this user (or create it if it doesn't exist)
    game_stats = GameStats.query.filter_by(user_id=user_id).first()
    
    if game_stats is None:
        # Create a new game stats record for this user, which *now* has a verified User.id
        game_stats = GameStats(user_id=user_id, wins=0, losses=0)
        db.session.add(game_stats)
        
    # Update stats
    if is_win:
        game_stats.wins += 1
    else:
        game_stats.losses += 1

    try:
        db.session.commit()
        current_app.logger.info(f"User {user_id} stats updated: W:{game_stats.wins}, L:{game_stats.losses}")
    except IntegrityError:
        # Rollback if an error still occurs (e.g., race condition or late-deleted User)
        db.session.rollback()
        current_app.logger.error(f"Integrity Error during stat update for user {user_id}. Rolling back.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"General error during stat update for user {user_id}: {e}")

# Simplified ASCII art for the Hangman stages (0 to 6 misses)
HANGMAN_STAGES = [
    # 0 lives left (Loss)
    """
      +---+
      |   |
      O   |
     /|\\  |
     / \\  |
          |
    ========
    """,
    # 1 life left
    """
      +---+
      |   |
      O   |
     /|\\  |
     /    |
          |
    ========
    """,
    # 2 lives left
    """
      +---+
      |   |
      O   |
     /|\\  |
          |
          |
    ========
    """,
    # 3 lives left
    """
      +---+
      |   |
      O   |
     /|   |
          |
          |
    ========
    """,
    # 4 lives left
    """
      +---+
      |   |
      O   |
      |   |
          |
          |
    ========
    """,
    # 5 lives left
    """
      +---+
      |   |
      O   |
          |
          |
          |
    ========
    """,
    # 6 lives left (Start)
    """
      +---+
      |   |
          |
          |
          |
          |
    ========
    """
]

# --- Game Logic Helpers ---

def get_word_from_api(genre=None):
    """Fetches a random word from the external API based on genre."""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
    params = {
        "letterPattern": "^[a-z]{5,10}$", # 5 to 10 letters, only lowercase A-Z
        "limit": 1 # Only need one word
    }
    
    # Use topic parameter for filtering if a genre is specified and it's not the generic "Technology" that failed
    if genre and genre in GENRE_LIST:
        params["topic"] = genre.lower()
    
    # The API endpoint for random word is '/words/random'
    url = EXTERNAL_WORD_API_URL.replace("/words/", "/words/random")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status() # Raise exception for bad status codes
        
        data = response.json()
        
        # Check for word in the response structure
        word = data.get('word', None)
        
        if word:
            return word.lower()
            
    except requests.exceptions.HTTPError as errh:
        current_app.logger.error(f"HTTP Error fetching word: {errh}")
    except requests.exceptions.ConnectionError as errc:
        current_app.logger.error(f"Connection Error fetching word: {errc}")
    except requests.exceptions.Timeout as errt:
        current_app.logger.error(f"Timeout Error fetching word: {errt}")
    except requests.exceptions.RequestException as err:
        current_app.logger.error(f"Request Error fetching word: {err}")
    except Exception as e:
        current_app.logger.error(f"General error: {e}")

    # Fallback to a hardcoded list if API fails or no word is returned
    current_app.logger.info(f"API returned no word for topic '{genre}'. Falling back to general random word.")
    fallback_words = ["flask", "python", "render", "deploy", "coding", "hangman", "secret"]
    return random.choice(fallback_words)

def get_display_word(word, guessed_letters):
    """Returns the word with unguessed letters masked by underscores."""
    display = ""
    for letter in word:
        if letter in guessed_letters:
            display += letter
        else:
            display += "_"
    return " ".join(display)

# --- Routes ---

@app.route('/restart', methods=['GET'])
def restart():
    """Clear session variables to start a new game."""
    session.pop('word_to_guess', None)
    session.pop('guessed_letters', None)
    session.pop('lives', None)
    session.pop('message', None)
    return redirect(url_for('hangman_game'))

@app.route('/', methods=['GET', 'POST'])
def hangman_game():
    
    # 1. Handle New Game Request (Genre selection)
    if request.method == 'POST' and 'genre_select' in request.form:
        genre = request.form.get('genre_select')
        word = get_word_from_api(genre)
        
        session['word_to_guess'] = word
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['message'] = f"New game started! Word is from **{genre}**."
        session['current_genre'] = genre
        
        # Redirect to GET to prevent form resubmission on refresh
        return redirect(url_for('hangman_game'))
        
    # --- State Initialization/Retrieval ---
    
    word_to_guess = session.get('word_to_guess')
    guessed_letters = session.get('guessed_letters')
    lives = session.get('lives')
    current_genre = session.get('current_genre', GENRE_LIST[0])
    
    # If no game is running, set initial state
    if not word_to_guess:
        word_to_guess = get_word_from_api(current_genre)
        session['word_to_guess'] = word_to_guess
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['message'] = "Welcome to Hangman! Guess a letter."
        lives = MAX_LIVES # Re-fetch lives after setting default
    
    # Always convert list of guessed letters back to a set for efficient lookups
    guessed_set = set(guessed_letters)
    is_game_over = False

    # 2. Handle Letter Guess (POST request)
    if request.method == 'POST' and 'letter' in request.form and not is_game_over:
        guess = request.form['letter'].lower().strip()
        session['message'] = "" # Clear previous messages
        
        # Validation
        if not guess.isalpha() or len(guess) != 1:
            session['message'] = "Please enter a single letter (A-Z)."
        elif guess in guessed_set:
            session['message'] = f"You already guessed **{guess.upper()}**."
        else:
            guessed_set.add(guess)
            
            if guess in word_to_guess:
                session['message'] = f"**{guess.upper()}** is correct!"
            else:
                session['lives'] -= 1
                session['message'] = f"**{guess.upper()}** is wrong. You lost a life!"

        # Convert the set back to a list before saving to the session
        session['guessed_letters'] = list(guessed_set)

        # Re-fetch updated state for rendering after POST
        lives = session.get('lives')
    
    # 3. Update display word and check for Win/Loss state
    display_word = get_display_word(word_to_guess, guessed_set)
    is_win = "_" not in display_word
    is_loss = lives <= 0
    
    message = session.get('message', "")
    
    if is_win:
        is_game_over = True
        message = f"🎉 YOU WON! The word was **{word_to_guess.upper()}**."
        
        # --- FIX: CALL STATS UPDATE ---
        user = get_or_create_user() # Ensure user exists
        if user: update_user_stats(user.id, True)

    elif is_loss:
        is_game_over = True
        message = f"💀 GAME OVER. The word was **{word_to_guess.upper()}**."

        # --- FIX: CALL STATS UPDATE ---
        user = get_or_create_user() # Ensure user exists
        if user: update_user_stats(user.id, False)

    
    # 4. Final Data Preparation
    
    # Ensure user is ready to fetch stats
    user = get_or_create_user()
    user_id = user.id if user else None
    
    user_wins, user_losses = get_user_stats(user_id)
    
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
        user_wins=user_wins,
        user_losses=user_losses
    )

if __name__ == '__main__':
    # For local testing, ensure the DB is initialized
    with app.app_context():
        db.create_all()
    app.run(debug=True)