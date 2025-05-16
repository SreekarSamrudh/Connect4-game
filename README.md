# Connect 4 - Multiplayer LAN Game with Pygame GUI

This project is a classic Connect 4 game implemented in Python, allowing two players to compete over a Local Area Network (LAN). It features a graphical user interface (GUI) built with Pygame for an interactive gameplay experience. The client and server communicate using a JSON-based protocol over TCP/IP sockets.

Key features include two-player LAN gameplay, real-time board updates, win/draw detection, a rematch option, and session scorekeeping.

![image](https://github.com/user-attachments/assets/f993de4a-d4ce-4108-8ba0-5b7afc10562c)

![image](https://github.com/user-attachments/assets/00989dad-5d9d-418c-a26f-099e7c825070)

## Technologies Used

* Python 3.x
* Pygame (for the graphical client)
* Standard Python Libraries:
    * `socket` (for TCP/IP networking)
    * `threading` (for concurrent client handling on the server)
    * `json` (for client-server message formatting)
    * `time`, `sys`

## Requirements & Installation

1.  **Python 3:**
    * Ensure you have Python 3 installed (version 3.7 or newer is recommended).
    * You can download it from [python.org](https://www.python.org/).
    * During installation on Windows, make sure to check the box "Add Python to PATH."

2.  **Pygame:**
    * This is required for the graphical client (`connect4_client_pygame.py`).
    * Open your terminal or command prompt and install Pygame using pip:
        ```bash
        pip install pygame
        ```
        (If you have multiple Python versions, you might need `pip3 install pygame` or `python -m pip install pygame`).

3.  **(Optional) Project Files:**
    * If you are cloning this from a GitHub repository:
        ```bash
        git clone [https://github.com/YourUsername/YourRepositoryName.git](https://github.com/YourUsername/YourRepositoryName.git)
        cd YourRepositoryName
        ```
    * Otherwise, ensure `connect4_server_lan.py` and `connect4_client_pygame.py` are in your project directory.

4.  **(Optional but Recommended) Virtual Environment:**
    If you prefer to use a virtual environment to manage dependencies:
    ```bash
    # Navigate to your project directory
    python -m venv cnenv  # Or any name you like for the environment

    # Activate it:
    # Windows:
    cnenv\Scripts\activate
    # macOS/Linux:
    source cnenv/bin/activate

    # Then install Pygame within the activated environment:
    pip install pygame
    ```
    If you have a `requirements.txt` file, you can install all dependencies with `pip install -r requirements.txt` after activating the environment.

## How to Run

This game requires one server instance and two client instances to play over a LAN.

**1. Start the Server:**
   * On the computer that will host the game (the "Server Laptop"):
       1.  Open a terminal/command prompt.
       2.  Navigate to the project directory.
       3.  Run the server script:
           ```bash
           python connect4_server_lan.py
           ```
       4.  The server will print: `Server started on all interfaces at port 5555` (or your configured port).
       5.  **Note the Server's LAN IP Address:** Clients will need this to connect.
           * **Windows:** `ipconfig` in Command Prompt (look for IPv4 Address).
           * **macOS/Linux:** `hostname -I` or `ip addr show` in Terminal.
       6.  **Firewall:** Ensure the server machine's firewall allows incoming TCP connections on port `5555`. You might be prompted by your OS firewall to allow "Python" or the script; choose "Allow access" (especially for Private networks). If not prompted, you may need to add an inbound rule manually.

**2. Start the Clients (Two Players):**
   * On each of the two client computers (can be the same as the server for testing, or different machines on the same LAN):
       1.  Open a terminal/command prompt.
       2.  Navigate to the project directory.
       3.  Run the client script:
           ```bash
           python connect4_client_pygame.py
           ```
       4.  When prompted `Enter Server IP ... :`, type the **LAN IP Address of the server machine** and press Enter.
       5.  The Pygame window should open. Repeat for the second client.
   * Once both clients connect, the game will begin!

**3. Gameplay:**
   * Use your mouse to click on the column where you want to drop your piece.
   * The game will display whose turn it is, current scores, and game status.
   * After a game ends, "Play Again?" and "Quit" buttons will appear.

---

This `README.md` provides a good overview and the essential instructions for someone to get your project up and running. Remember to create the actual `requirements.txt` file from your virtual environment as we discussed earlier (`pip freeze > requirements.txt`) if you want to include specific package versions.
