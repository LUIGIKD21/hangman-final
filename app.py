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

# EXTERNAL API ENDPOINT - Using a reliable, free random word API
# Note: This API does NOT support filtering by genre. It returns ONE random English word.
EXTERNAL_WORD_API_URL = "https://random-word-api.herokuapp.com/word?number=1"

# Hardcoded GENRE LIST: Keeping this for the UI, but the API fetch ignores the genre selection.
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

def fetch_word_from_api(genre=None): # Genre parameter is now IGNORED
    """Fetches a random word (ignoring genre) from the external API."""
    try:
        # Simple API call that just requests one random word
        response = requests.get(EXTERNAL_WORD_API_URL, timeout=10)
        response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
        
        data = response.json()
        
        # This API returns a list, e.g., ["randomword"]
        if data and isinstance(data, list) and data[0].isalpha():
            return data[0].upper()
        else:
            print(f"API Error: Received unexpected data format: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"API Connection Error: {e}")
        return None


def initialize_game(genre=None):
    """Initializes or resets the game state in the session, fetching a word from the API."""
    
    # 1. Determine the genre to use (still needs to be set for the UI/restart button)
    if genre and genre in GENRE_LIST:
        target_genre = genre
    elif GENRE_LIST:
        target_genre = random.choice(GENRE_LIST)
    else:
        session['message'] = "Error: No genres available! Cannot start game."
        return 

    # 2. Fetch word from the external API (NOTE: fetch_word_from_api ignores the genre!)
    selected_word = fetch_word_from_api()
    
    if not selected_word:
        session['message'] = f"Error: Could not fetch a word from the external service. Using fallback."
        # Fallback word if API fails
        selected_word = "FALLBACK" 
        
    # 3. Update Session State
    session['word'] = selected_word
    session['guessed_letters'] = [] 
    session['lives'] = MAX_LIVES
    session['message'] = f"New Game! Genre: **{target_genre}** (Word is random). Guess a letter to start!"
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
        genres=GENRE_LIST, # Uses the hardcoded list
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