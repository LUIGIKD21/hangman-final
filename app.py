import random
import os
import requests 
from flask import Flask, render_template, request, redirect, url_for, session

# --- Configuration and Data ---
app = Flask(__name__)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
# For deployment, remove this line and set SECRET_KEY in Render's dashboard.
app.secret_key = 'a_very_secret_key_for_hangman_game_123' 

MAX_LIVES = 6

# --- NEW API CONFIGURATION ---
# These values MUST be set as Environment Variables on Render!
# X_RAPIDAPI_KEY: Your unique key from RapidAPI
# X_RAPIDAPI_HOST: wordsapiv1.p.rapidapi.com
RAPIDAPI_KEY = os.environ.get('X_RAPIDAPI_KEY')
RAPIDAPI_HOST = os.environ.get('X_RAPIDAPI_HOST', 'wordsapiv1.p.rapidapi.com')

# The base endpoint for searching and fetching words.
# We will append '?' and parameters later.
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
  +---+
  |   |
      |
      |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
      |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
  |   |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
 /    |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
 / \\  |
      |
========="""
]

# --- Helper Functions ---

def get_word_from_api(genre):
    """Fetches a random word based on the genre using the WordsAPI."""
    # Note: WordsAPI uses 'topic' for genre/subject. We limit to 5-10 letters.
    # The API query uses: hasDetails=typeOf, topic=... , lettersMin=5, lettersMax=10
    
    params = {
        'random': 'true',
        'hasDetails': 'typeOf',
        'lettersMin': 5,
        'lettersMax': 10,
        'topic': genre.lower(),
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    
    # Use the base URL for random word search
    url = "https://wordsapiv1.p.rapidapi.com/words/"

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # WordsAPI returns a word directly if random=true is used
        word = data.get('word')
        if word and word.isalpha():
            return word.upper()
        
        # Fallback if the API returns an unexpected structure or non-alpha word
        return random.choice(["PYTHON", "FLASK", "DEVELOPER"]) # Safe defaults
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        # Return a safe, hardcoded word on API failure
        return random.choice(["JINJA", "RENDER", "APIFAIL"])

def get_display_word(word_to_guess, guessed_letters):
    """Creates the display string (e.g., P_T_O_N)"""
    # Defensive check: if word_to_guess is somehow None, treat it as an empty string
    if not word_to_guess:
        return ""
        
    display = ''
    for letter in word_to_guess:
        if letter in guessed_letters:
            display += letter
        else:
            display += '_'
    return ' '.join(display)

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # Retrieve state, providing safe defaults for robust operation
    # FIX 1: Provide a default empty string for word_to_guess
    word_to_guess = session.get('word_to_guess', "") 
    guessed_letters = session.get('guessed_letters', [])
    lives = session.get('lives', MAX_LIVES)
    message = session.get('message', "")
    current_genre = session.get('current_genre', GENRE_LIST[0])
    
    guessed_set = set(guessed_letters)
    is_game_over = False

    # 1. Handle New Game Initialization (GET or Genre Change POST)
    # FIX 2: Check if word_to_guess is missing (None or "") to force initialization
    if not word_to_guess or 'genre_select' in request.form:
        
        # If POST and genre is selected, update the genre
        if 'genre_select' in request.form:
            current_genre = request.form['genre_select']
        
        session['current_genre'] = current_genre
        
        # Fetch new word
        new_word = get_word_from_api(current_genre)
        
        # Reset game state
        session['word_to_guess'] = new_word
        session['guessed_letters'] = []
        session['lives'] = MAX_LIVES
        session['message'] = f"New game started! Guess the {current_genre} word."
        word_to_guess = new_word
        lives = MAX_LIVES
        guessed_set = set()
        
        # If this was a POST (genre change), redirect to a clean GET request
        if request.method == 'POST' and 'genre_select' in request.form:
            return redirect(url_for('index'))

    # 1.5. Handle Guess (POST only)
    elif request.method == 'POST' and 'letter' in request.form:
        if not word_to_guess:
            # Should not happen with the new initialization logic, but as a safeguard
            session['message'] = "Game not initialized. Please select a genre and start a new game."
            return redirect(url_for('index'))
            
        guess = request.form['letter'].upper()
        
        if len(guess) != 1 or not guess.isalpha():
            session['message'] = "Please enter a single letter (A-Z)."
            # We skip the redirect here so the user can see the message and try again
        elif guess in guessed_set:
            session['message'] = f"You already guessed **{guess}**."
        elif guess in word_to_guess:
            guessed_set.add(guess)
            session['message'] = f"Correct guess! **{guess}** is in the word."
        else:
            lives -= 1
            session['lives'] = lives
            guessed_set.add(guess)
            session['message'] = f"Incorrect guess! **{guess}** is not in the word. You lost a life."
            
        # Convert the set back to a list before saving to the session
        session['guessed_letters'] = list(guessed_set)

        # Re-fetch updated state for rendering after POST
        lives = session.get('lives')
    
    # 2. Update display word and check for Win/Loss state
    # This call is now safe because word_to_guess has a default value (or was initialized)
    display_word = get_display_word(word_to_guess, guessed_set)
    
    # Check for game end conditions only if there is a word to guess
    if word_to_guess:
        is_win = "_" not in display_word
        is_loss = lives <= 0
    else:
        is_win = False
        is_loss = False
    
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
        genres=GENRE_LIST,
        current_genre=current_genre
    )

@app.route('/restart')
def restart():
    """Clears the game state from the session and redirects to the index page."""
    # Preserve the genre so the user can play again with the same genre
    current_genre = session.get('current_genre') 
    
    # Clear game-specific session data
    session.pop('word_to_guess', None)
    session.pop('guessed_letters', None)
    session.pop('lives', None)
    session.pop('message', None)
    
    # Redirect to the main game which will start a new game with the same genre
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)