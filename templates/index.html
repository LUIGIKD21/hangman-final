<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Hangman - Genre Edition</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Roboto+Mono&display=swap');

        body {
            font-family: 'Inter', sans-serif;
            background-color: #f7f7f7;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 500px;
            text-align: center;
        }

        h1 {
            color: #1a73e8;
            margin-top: 0;
            font-size: 2em;
        }
        
        /* Auth Links and User Info */
        .auth-bar {
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        .auth-bar a {
            color: #1a73e8;
            text-decoration: none;
            margin: 0 10px;
            font-weight: 500;
        }

        /* Controls (Forms/Buttons) */
        .controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap; /* Allows wrapping on mobile */
        }
        
        input[type="text"], select { 
            padding: 10px; 
            font-size: 1em; 
            border: 1px solid #ccc; 
            border-radius: 6px; 
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: border-color 0.3s;
        }
        input[type="text"]:focus, select:focus {
            border-color: #1a73e8;
            outline: none;
        }
        
        .guess-input {
            width: 50px; /* Small fixed width for single letter */
            text-align: center;
        }

        button, .button {
            padding: 10px 15px;
            font-size: 1em;
            font-weight: bold;
            color: #fff;
            background-color: #4CAF50; /* Green for main action */
            border: none;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none; /* For the 'a' tags styled as buttons */
            display: inline-block;
            transition: background-color 0.3s, transform 0.1s;
        }
        
        button:hover, .button:hover {
            background-color: #45a049;
            transform: translateY(-1px);
        }
        
        /* Hangman Display */
        .hangman-display { 
            background: #2c3e50; 
            color: #00ff00; 
            padding: 15px; 
            border-radius: 8px; 
            overflow: auto; 
            display: inline-block; 
            text-align: left; 
            font-family: 'Roboto Mono', monospace;
            font-size: 1.1em;
            margin: 20px 0;
            white-space: pre; /* Essential for ASCII art */
        }

        h2 { 
            font-size: 3em; 
            letter-spacing: 15px; 
            margin: 20px 0; 
            color: #e74c3c; 
            word-break: break-all; /* Ensures long words fit */
        }

        /* Messages and State Info */
        #message { 
            margin-top: 20px; 
            font-weight: bold; 
            min-height: 20px; 
            font-size: 1.2em;
        }
        .win { color: #27ae60; }
        .loss { color: #c0392b; }

        .game-info {
            padding: 10px 0;
            border-top: 1px solid #eee;
            border-bottom: 1px solid #eee;
            margin-bottom: 20px;
        }
        .game-info p { 
            margin: 5px 0; 
            font-size: 0.9em;
        }

        .guessed-letters {
            margin-top: 20px;
            padding: 10px;
            background-color: #ecf0f1;
            border-radius: 6px;
        }
        .guessed-letters span {
            font-weight: bold;
            color: #2980b9;
        }

        /* Game Over Controls */
        .game-over-controls {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 20px;
        }
        .game-over-controls .secondary {
            background-color: #3498db; /* Blue for 'Change Genre' */
        }
        .game-over-controls .secondary:hover {
            background-color: #2980b9;
        }

    </style>
</head>
<body>
    <div class="container">
        <h1>API Hangman</h1>
        
        <div class="game-info">
            <p>Current Genre: **{{ current_genre }}**</p>
            <p>Lives Remaining: **{{ lives }}/{{ max_lives }}**</p>
        </div>

        <!-- Genre Selection Form: Visible for starting a new game -->
        <form method="POST" action="/" class="controls">
            <label for="genre_select">Choose a Genre:</label>
            <select name="genre_select" id="genre_select">
                {% for genre in genres %}
                    <option value="{{ genre }}" {% if genre == current_genre %}selected{% endif %}>
                        {{ genre }}
                    </option>
                {% endfor %}
            </select>
            <button type="submit">Start New Game</button>
        </form>

        <pre class="hangman-display">{{ hangman_art }}</pre>

        <h2>{{ display_word }}</h2>
        
        <p id="message" class="{{ 'win' if 'WON' in message else ('loss' if 'OVER' in message else '') }}">{{ message | safe }}</p>

        {% if not is_game_over %}
            <!-- Guess Form: Visible only while the game is active -->
            <form method="POST" action="/" class="controls">
                <label for="letter">Guess Letter:</label>
                <input type="text" id="letter" name="letter" maxlength="1" pattern="[a-zA-Z]" required autofocus class="guess-input">
                <button type="submit">Guess</button>
            </form>
        {% else %}
            <!-- Game Over Controls (Fixed) -->
            <div class="game-over-controls">
                <a href="{{ url_for('restart') }}" class="button">Play Again (Same Genre)</a>
                <!-- This line was causing the error, now correctly pointing to the 'index' route -->
                <a href="{{ url_for('index') }}" class="button secondary">Change Genre</a>
            </div>
        {% endif %}

        <div class="guessed-letters">
            Guessed: <span>{{ guessed_letters | join(', ') if guessed_letters else 'None' }}</span>
        </div>
    </div>
</body>
</html>