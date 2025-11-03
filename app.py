import random
import os
from flask import Flask, render_template, request, redirect, url_for, session

# --- Configuration and Data ---
app = Flask(__name__)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
# For deployment, remove this line and set SECRET_KEY in Render's dashboard.
app.secret_key = 'a_very_secret_key_for_hangman_game_123' 

MAX_LIVES = 6

# 1. NEW: Word Data Structure with Genres (Database)
WORD_GENRES = {
    "Technology": [
        "PYTHON", "FLASK", "JAVASCRIPT", "DATABASE", "ALGORITHM", "SERVER", 
        "SESSION", "API", "CLOUD", "SOFTWARE"
    ],
    "Animals": [
        "ELEPHANT", "GIRAFFE", "TIGER", "PENGUIN", "KANGAROO", 
        "BUTTERFLY", "DOLPHIN", "CHIMPANZEE", "SQUIRREL", "ZEBRA"
    ],
    "Sports": [
        "BASKETBALL", "FOOTBALL", "SOCCER", "HOCKEY", "TENNIS", 
        "GOLFER", "SWIMMING", "MARATHON", "TOUCHDOWN", "VOLLEYBALL"
    ]
}

# List of genres for the dropdown
GENRE_LIST = sorted(list(WORD_GENRES.keys()))


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

def initialize_game(genre=None):
    """Initializes or resets the game state in the session."""
    
    # Select genre: use the provided genre, or default to the first one if none is provided
    if genre and genre in WORD_GENRES:
        word_list = WORD_GENRES[genre]
    else:
        # Default to a random genre if starting fresh
        genre = random.choice(GENRE_LIST)
        word_list = WORD_GENRES[genre]
        
    session['word'] = random.choice(word_list).upper()
    session['guessed_letters'] = [] 
    session['lives'] = MAX_LIVES
    session['message'] = f"New Game! Genre: **{genre}**. Guess a letter to start!"
    session['genre'] = genre

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
    
    # 2. Check if the user is trying to START a new game with a genre selection
    if request.method == 'POST' and 'genre_select' in request.form:
        selected_genre = request.form['genre_select']
        initialize_game(genre=selected_genre)
        return redirect(url_for('hangman_game')) # Redirect after POST to clear form data

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
    # You must have Flask installed: pip install Flask
    app.run(debug=True)