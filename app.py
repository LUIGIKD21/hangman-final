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

# The endpoint used to find words related to a topic (the genre)
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

def fetch_word_from_api(genre):
    """
    Fetches a random word related to the genre from WordsAPI.
    Requires X_RAPIDAPI_KEY and X_RAPIDAPI_HOST environment variables.
    """
    # Fallback if API keys are not configured in the environment
    if not RAPIDAPI_KEY:
        print("Configuration Error: X_RAPIDAPI_KEY is missing. Using fallback word.")
        # Choose a basic fallback based on genre
        if genre == "Animals":
            return "WOLF"
        elif genre == "Sports":
            return "GOAL"
        elif genre == "Technology":
            return "CODE"
        else:
            return "FALLBACK"

    # API Headers for Authentication
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }

    # Parameters to search for a random word related to the genre (topic)
    # 'rel_jja' looks for adjectives or nouns related to the topic
    params = {
        'lettersMax': 10, # Keep words short enough for Hangman
        'hasDetails': 'frequency',
        'random': 'true',
        'rel_jja': genre 
    }

    try:
        # 1. Request a random word related to the genre
        response = requests.get(EXTERNAL_WORD_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status() # Raises an exception for 4xx or 5xx status codes
        
        data = response.json()
        
        # 2. WordsAPI returns the word directly in the 'word' field.
        if data and 'word' in data and data['word'].isalpha():
            return data['word'].upper()
        else:
            print(f"API Error: Received unexpected data or no word found for genre '{genre}'.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"API Connection Error: {e}")
        return None


def initialize_game(genre=None):
    """Initializes or resets the game state in the session, fetching a genre-specific word."""
    
    # 1. Determine the genre to use
    if genre and genre in GENRE_LIST:
        target_genre = genre
    elif GENRE_LIST:
        # Default to a random genre if starting fresh
        target_genre = random.choice(GENRE_LIST)
    else:
        session['message'] = "Error: No genres available! Cannot start game."
        return 

    # 2. Fetch word from the external API
    # The genre is now passed to the API call!
    selected_word = fetch_word_from_api(target_genre)
    
    if not selected_word:
        session['message'] = f"Error: Could not fetch a word from the API for '{target_genre}'. Using hardcoded fallback."
        # Final fallback word if API call failed
        selected_word = "API_FAIL" 
        
    # 3. Update Session State
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

# --- Flask Routes ---

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
        current_genre=session.get('genre')
    )

@app.route('/restart')
def restart():
    """Route to restart the game, defaulting to the current genre."""
    initialize_game(genre=session.get('genre'))
    return redirect(url_for('hangman_game'))

# --- Execution ---

if __name__ == '__main__':
    app.run(debug=True)
