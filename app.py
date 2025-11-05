import random
import os
import requests 
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import select

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
=========
""",
    r"""
  +---+
  |   |
  O   |
      |
      |
      |
=========
""",
    r"""
  +---+
  |   |
  O   |
  |   |
      |
      |
=========
""",
    r"""
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========
""",
    r"""
  +---+
  |   |
  O   |
 /|\  |
      |
      |
=========
""",
    r"""
  +---+
  |   |
  O   |
 /|\  |
 /    |
      |
=========
""",
    r"""
  +---+
  |   |
  O   |
 /|\  |
 / \  |
      |
=========
"""
]

# --- Database Setup (Inferred) ---
# Use the DATABASE_URL environment variable provided by Render.
# SQLAlchemy requires the scheme to be 'postgresql://', but Render provides 'postgres://'.
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
else:
    # Fallback for local development if no URL is set
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hangman.db'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# --- Database Model (FIXED) ---
class User(db.Model):
    """
    User model to track high scores.
    FIX: The 'email' column, which caused the UndefinedColumn error, has been removed
    because it was likely not created in the live database schema.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    high_score = db.Column(db.Integer, default=0)
    
    # Store game history as a JSON/Dict column (or just simple string, depending on requirements)
    # Using String for simplicity since we don't know the exact history data structure
    game_history = db.Column(db.String, default='[]') 

    def __init__(self, username):
        self.username = username
        
    def __repr__(self):
        return f'<User {self.username}>'

# --- Utility Functions ---

def get_word_from_api(genre):
    """Fetches a random word from the WordsAPI based on a genre/topic."""
    
    # Note: WordsAPI doesn't have a direct 'genre' filter. 
    # We use 'topic' as a proxy and search for words related to the genre.
    topic = genre.lower()
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    
    # Use the 'has' parameter to search for words having definitions related to the topic
    params = {
        "has": "definitions",
        "random": "true",
        "limit": 1,
        # Fetching a random word ensures variety. We use the topic in the definitions.
    }
    
    # The API documentation suggests searching by a word's characteristics. 
    # For simplicity and to fit the API structure, we'll try to find a random word
    # that has a definition, and assume the random nature covers the 'genre' part 
    # if a direct 'topic' filter isn't available or robust.
    # To enforce a genre, we'd need a different API or a local word list.
    
    try:
        # Fetch a word that has definitions
        response = requests.get(EXTERNAL_WORD_API_URL, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        word = data.get('word', 'python') # Default word if API fails
        
        # Simple cleanup: ensure it's a single word and only contains letters
        if word and word.isalpha() and len(word) > 3:
            return word.upper()
        
        # If the fetched word is bad, use a fallback
        print(f"API returned unusable word: {word}. Falling back.")
        return random.choice(['PYTHON', 'FLASK', 'RENDER', 'CODE'])
        
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching word: {e}")
        # Fallback to a safe word in case of API failure
        return random.choice(['PYTHON', 'FLASK', 'RENDER', 'CODE'])


def get_display_word(word, guessed_letters):
    """Returns the word with unguessed letters replaced by underscores."""
    display = ""
    for letter in word:
        if letter in guessed_letters:
            display += letter
        else:
            display += "_"
    return " ".join(display)


def get_user_identifier():
    """Gets a unique identifier for the user from the session, creating one if necessary."""
    if 'user_identifier' not in session:
        # Use UUID to generate a unique, non-guessable ID for the user
        session['user_identifier'] = str(uuid.uuid4())
    return session['user_identifier']


def get_or_create_user():
    """
    Retrieves the user from the database based on the session ID,
    or creates a new user if one doesn't exist.
    """
    user_identifier = get_user_identifier()
    
    # Use SQLAlchemy 2.0 style select
    # This is the line (line 164 in traceback) that caused the error.
    # It now works because the 'email' column has been removed from the User model definition.
    user = db.session.execute(select(User).filter_by(username=user_identifier)).scalar_one_or_none()
    
    if user is None:
        user = User(username=user_identifier)
        db.session.add(user)
        db.session.commit()
        
    return user


# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def hangman_game():
    """Handles the main game logic, including start, guessing, and genre selection."""
    
    # Ensure the user exists in the database before proceeding
    user = get_or_create_user() 

    # 1. Handle Genre Selection (Game Restart/New Game)
    if request.method == 'POST' and 'genre_select' in request.form:
        genre = request.form['genre_select']
        word_to_guess = get_word_from_api(genre)
        
        # Initialize new game state
        session['word_to_guess'] = word_to_guess
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['message'] = f"New game started! Category: **{genre}**"
        session['current_genre'] = genre
        
        # Redirect to GET to clear POST data and prevent resubmission
        return redirect(url_for('hangman_game'))

    # If the game hasn't started, initialize with a default state or force genre selection
    if 'word_to_guess' not in session:
        session['current_genre'] = GENRE_LIST[0]
        # Auto-start with the first genre for the initial load
        word_to_guess = get_word_from_api(session['current_genre'])
        session['word_to_guess'] = word_to_guess
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['message'] = "Welcome! Choose a genre or start guessing."


    # Get current game state from session
    word_to_guess = session.get('word_to_guess').upper()
    guessed_letters = session.get('guessed_letters', [])
    lives = session.get('lives', MAX_LIVES)
    guessed_set = set(g.upper() for g in guessed_letters)
    is_game_over = False
    
    # 2. Handle Letter Guess
    if request.method == 'POST' and 'letter' in request.form:
        if lives <= 0:
            session['message'] = "The game is over! Start a new one."
            # Redirect to GET to show game over state
            return redirect(url_for('hangman_game'))

        guess = request.form['letter'].upper()
        session['message'] = "" # Clear previous message
        
        if len(guess) != 1 or not guess.isalpha():
            session['message'] = "Please enter a single letter (A-Z)."
        elif guess in guessed_set:
            session['message'] = f"You already guessed **{guess}**. Try a new letter."
        else:
            guessed_set.add(guess)
            
            if guess in word_to_guess:
                session['message'] = f"✅ Good guess! **{guess}** is in the word."
            else:
                lives -= 1
                session['lives'] = lives
                session['message'] = f"❌ Miss! **{guess}** is NOT in the word. {lives} lives left."

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
        message = f"🎉 YOU WON! The word was **{word_to_guess}**."
    elif is_loss:
        is_game_over = True
        message = f"💀 GAME OVER. The word was **{word_to_guess}**."

    # Handle game end logic (e.g., updating score)
    if is_game_over:
        # TODO: Implement score update logic here based on win/loss
        pass
        
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
        current_genre=session.get('current_genre'),
        user_id=user.username, # Display user ID for debugging/tracking
        high_score=user.high_score # Display high score
    )


@app.route('/restart', methods=['GET'])
def restart():
    """Resets the game state while keeping the current genre."""
    
    # A new word will be chosen from the current genre on the next GET request
    # but we can set up the new game logic here to ensure consistency
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
        db.create_all()
    except Exception as e:
        # Log if create_all fails (e.g., if tables already exist via a migration)
        print(f"Error during db.create_all(): {e}")

if __name__ == '__main__':
    # When running locally, you must ensure your database is set up and migrated.
    # Set the DATABASE_URL environment variable locally or use the default SQLite setup.
    app.run(debug=True)