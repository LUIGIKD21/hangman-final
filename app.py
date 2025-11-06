import random
import os
import requests 
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

# --- Configuration and Data ---
app = Flask(__name__)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
# For deployment, remove this line and set SECRET_KEY in Render's dashboard.
app.secret_key = 'a_very_secret_key_for_hangman_game_123' 

MAX_LIVES = 6

# --- DATABASE CONFIGURATION ---
# The DATABASE_URL environment variable will be set by Render for the PostgreSQL service.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Store plain text for now
    wins = db.Column(db.Integer, default=0, nullable=False) # NEW: Win count
    losses = db.Column(db.Integer, default=0, nullable=False) # NEW: Loss count

    def __repr__(self):
        return f'<User {self.username}>'

# Ensure tables are created when the app runs locally
# NOTE: If you are running this locally and had an old 'users.db', 
# you may need to delete it or use a migration tool to add the new columns.
with app.app_context():
    db.create_all()


# --- API CONFIGURATION ---
# REMOVED: RAPIDAPI_KEY and RAPIDAPI_HOST since the new API doesn't need a key.
# We are switching to the Random Word API, which is often more reliable for simple words.
EXTERNAL_WORD_API_URL = "https://random-word-api.herokuapp.com/word?number=1" 

# Hardcoded GENRE LIST: These are now primarily for display and local fallback.
GENRE_LIST = [
    "Food", 
    "Sports", 
    "Science",
    "Geography"
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


# --- Utility Functions ---

def fetch_word_from_api(genre, max_retries=3):
    """
    Fetches a single random word from the Random Word API.
    The 'genre' is used only for selecting a specific fallback word if the API fails.
    """
    
    # Fallback words, now organized by genre for context if the API fails
    fallback_words = {
        "Food": ["CHEESE", "SUSHI", "LEMON", "CARROT"],
        "Sports": ["SOCCER", "BASKETBALL", "FOOTBALL", "TENNIS", "HOCKEY"],
        "Science": ["PROTON", "ORBIT", "GENETICS", "ASTRONOMY"],
        "Geography": ["CANADA", "RIVER", "MOUNTAIN", "DESERT"]
    }
    
    # Select a relevant fallback word if all else fails
    fallback_word = random.choice(fallback_words.get(genre, ["PYTHON"]))

    for attempt in range(max_retries):
        try:
            # We are requesting 1 random word
            response = requests.get(EXTERNAL_WORD_API_URL, timeout=5)
            response.raise_for_status() 
            data = response.json()
            
            # The Random Word API returns a list containing one word, e.g., ['apple']
            if data and isinstance(data, list) and len(data) > 0:
                word_candidate = data[0]
                
                # Check if the word is valid (alphabetic and not empty)
                if word_candidate and word_candidate.isalpha():
                    return word_candidate.upper()
                
                print(f"Attempt {attempt + 1}: API returned invalid word '{word_candidate}'. Retrying...")
                continue
            
            # If the API returns an unexpected structure, break and use fallback
            break
            
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1}: Error fetching word from API: {e}. Retrying...")
            continue

    # Final Fallback if all retries fail
    print(f"All {max_retries} API attempts failed. Falling back to {fallback_word}.")
    return fallback_word


def get_display_word(word, guessed_letters):
    """Returns the word with unguessed letters replaced by underscores."""
    display = ""
    for letter in word:
        if letter in guessed_letters:
            display += letter + " "
        else:
            display += "_ "
    return display.strip()


def initialize_game(genre):
    """Initializes a new game session."""
    word = fetch_word_from_api(genre)
    session['word'] = word
    session['guessed_letters'] = []
    session['lives'] = MAX_LIVES
    session['message'] = "Start guessing letters!"
    session['genre'] = genre
    session['is_game_over'] = False
    
    if not word.isalpha():
        # Safety check if the fallback word itself was invalid (unlikely)
        return initialize_game(genre) 
    
    print(f"New game started with word: {word}") 
    return word

# --- Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'GET':
        return render_template('register.html')
    
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return render_template('register.html', error="Both username and password are required.")
    
    user_exists = User.query.filter_by(username=username).first()
    if user_exists:
        return render_template('register.html', error="Username already exists. Please choose another.")

    # New user starts with 0 wins and 0 losses (handled by model defaults)
    new_user = User(username=username, password=password)
    try:
        db.session.add(new_user)
        db.session.commit()
        print(f"New user registered: {username}")
        session['message'] = f"Account created for {username}. Please log in."
        return redirect(url_for('login')) 
    except Exception as e:
        db.session.rollback()
        print(f"Database error during registration: {e}")
        return render_template('register.html', error="An error occurred during registration.")


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'GET':
        if session.get('username'):
             return redirect(url_for('index'))
        
        message = session.pop('message', None) 
        return render_template('login.html', message=message)

    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return render_template('login.html', error="Both username and password are required.")

    user = User.query.filter_by(username=username).first()
    
    if user and user.password == password:
        session['username'] = username
        session['message'] = f"Welcome, {username}! Start playing."
        return redirect(url_for('index')) 
    else:
        return render_template('login.html', error="Invalid username or password.")


@app.route('/logout')
def logout():
    """Handles user logout."""
    session.pop('username', None)
    session['message'] = "You have been logged out."
    return redirect(url_for('index'))


# --- Game Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main game logic and rendering."""
    # 1. Check for current session state
    word_to_guess = session.get('word')
    guessed_letters = session.get('guessed_letters', [])
    
    # Ensure lives always has a default integer value (MAX_LIVES) if not in session, 
    lives = session.get('lives', MAX_LIVES) 
    
    current_genre = session.get('genre', GENRE_LIST[0])
    is_game_over = session.get('is_game_over', False)
    username = session.get('username', None)

    guessed_set = set(guessed_letters)
    
    # If no word in session (new game or session reset), initialize
    if not word_to_guess:
        word_to_guess = initialize_game(current_genre)
        # When a new game is initialized, pull the fresh state from the session
        guessed_set = set()
        is_game_over = False
        lives = MAX_LIVES # Update local variable after initialization

    # 1.1 Handle Genre Change (POST from genre-form)
    if request.method == 'POST' and 'genre_select' in request.form:
        new_genre = request.form['genre_select']
        word_to_guess = initialize_game(new_genre)
        guessed_set = set()
        is_game_over = False
        lives = MAX_LIVES # Update local variable

    # 1.2 Handle Letter Guess (POST from guess form)
    elif request.method == 'POST' and 'letter' in request.form and not is_game_over:
        letter = request.form['letter'].upper()
        session['message'] = "" # Clear previous message

        if len(letter) == 1 and letter.isalpha():
            if letter in guessed_set:
                session['message'] = f"You already guessed **{letter}**."
            else:
                guessed_set.add(letter)
                if letter not in word_to_guess:
                    session['lives'] = lives - 1
                    session['message'] = f"Wrong guess! **{letter}** is not in the word."
                else:
                    session['message'] = f"Correct! **{letter}** is in the word."
        else:
            session['message'] = "Invalid input. Please enter a single letter (A-Z)."

        # Convert the set back to a list before saving to the session
        session['guessed_letters'] = list(guessed_set)

        # Re-fetch updated lives state after POST, ensuring a default is provided.
        lives = session.get('lives', MAX_LIVES)
    
    # 2. Update display word and check for Win/Loss state
    display_word = get_display_word(word_to_guess, guessed_set)
    is_win = "_" not in display_word
    is_loss = lives <= 0
    
    message = session.get('message', "")
    
    # Track if the game just ended this turn
    game_just_ended = False

    if is_win and not is_game_over:
        game_just_ended = True
        is_game_over = True
        session['is_game_over'] = True
        message = f"🎉 YOU WON! The word was **{word_to_guess}**."
    elif is_loss and not is_game_over:
        game_just_ended = True
        is_game_over = True
        session['is_game_over'] = True
        message = f"💀 GAME OVER. The word was **{word_to_guess}**."

    # 2.1 NEW: Update Win/Loss Record if game just ended
    if game_just_ended and username:
        user = User.query.filter_by(username=username).first()
        if user:
            if is_win:
                user.wins += 1
            elif is_loss:
                user.losses += 1
            db.session.commit()
            print(f"Record updated for {username}: Wins={user.wins}, Losses={user.losses}")

    # 3. NEW: Fetch current user record for display
    user_record = {'wins': 0, 'losses': 0}
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            user_record['wins'] = user.wins
            user_record['losses'] = user.losses
            
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
        username=username,
        user_record=user_record # NEW variable passed to template
    )

@app.route('/restart')
def restart():
    """Clears the session and redirects to start a new game."""
    current_genre = session.get('genre', GENRE_LIST[0])
    username = session.get('username')
    
    session.pop('word', None)
    session.pop('guessed_letters', None)
    session.pop('lives', None)
    session.pop('is_game_over', None)
    
    if current_genre:
        session['genre'] = current_genre
    if username:
        session['username'] = username

    return redirect(url_for('index'))

if __name__ == '__main__':
    # Removed API key check since the new API doesn't require one
    app.run(debug=True)