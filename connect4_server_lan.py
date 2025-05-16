import socket
import threading
import json
import time

# Connect4Game class remains the same as the last version I provided
class Connect4Game:
    def __init__(self):
        self.board = [[' ' for _ in range(7)] for _ in range(6)]
        self.current_player_symbol = "X"
        self.game_over = False
        self.winner = None
        self.is_draw = False

    def get_board_string(self):
        board_str = "\n"
        for _r_idx, row in enumerate(self.board): # Renamed r_idx to _r_idx as it's not used
            board_str += "| " + " | ".join(row) + " |\n"
        board_str += "+---" * 7 + "+\n"
        board_str += "| " + " | ".join(map(str, range(7))) + " |\n"
        return board_str

    def is_valid_move(self, col):
        if not (0 <= col < 7): return False
        return self.board[0][col] == ' '

    def make_move(self, col):
        if not self.is_valid_move(col): return False
        for row in reversed(self.board):
            if row[col] == ' ':
                row[col] = self.current_player_symbol
                return True
        return False

    def check_winner(self):
        for r in range(6):
            for c in range(7):
                if self.board[r][c] == ' ': continue
                if c <= 3 and all(self.board[r][c+i] == self.board[r][c] for i in range(4)): self.winner = self.board[r][c]; return True
                if r <= 2 and all(self.board[r+i][c] == self.board[r][c] for i in range(4)): self.winner = self.board[r][c]; return True
                if r <= 2 and c <= 3 and all(self.board[r+i][c+i] == self.board[r][c] for i in range(4)): self.winner = self.board[r][c]; return True
                if r <= 2 and c >= 3 and all(self.board[r+i][c-i] == self.board[r][c] for i in range(4)): self.winner = self.board[r][c]; return True
        return False

    def is_board_full(self):
        if all(self.board[0][c] != ' ' for c in range(7)):
            if not self.winner: # Only a draw if no winner yet
                self.is_draw = True
            return True
        return False

    def switch_player(self):
        self.current_player_symbol = "O" if self.current_player_symbol == "X" else "X"

    def reset_game(self, starting_player="X"):
        self.board = [[' ' for _ in range(7)] for _ in range(6)]
        self.current_player_symbol = starting_player
        self.game_over = False
        self.winner = None
        self.is_draw = False
        print(f"Game object reset. Game over: {self.game_over}, Starting player: {self.current_player_symbol}")


class Connect4Server:
    def __init__(self, port=5555):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.host_ip = '0.0.0.0'
        self.port = port
        try:
            self.server_socket.bind((self.host_ip, self.port))
        except socket.error as e:
            print(f"Error binding: {e}"); exit()
        self.server_socket.listen(2)
        print(f"Server started on all interfaces, port {self.port}")

        self.clients = [] # List of active client sockets
        self.client_data = {} # socket -> {"symbol": 'X', "rematch_requested": False, "opponent_socket": opponent_sock}
        
        self.game = Connect4Game()
        self.game_lock = threading.Lock() # Protects shared resources: clients, client_data, game, game_active, current_turn_client, session_scores, current_session_starting_player
        
        self.game_active = False # True when 2 players are in an active game or deciding rematch
        self.current_turn_client = None
        self.client_threads = {} # socket -> thread object
        
        # Session specific, reset when new pair of players start their first game
        self.session_scores = {'X': 0, 'O': 0}
        self.current_session_starting_player = "X"


    def send_json(self, client_socket, data):
        try:
            if client_socket.fileno() == -1: # Check if socket is already closed
                print(f"Attempted to send on a closed socket for symbol {self.client_data.get(client_socket, {}).get('symbol', 'Unknown')}")
                self.handle_disconnection(client_socket) # Ensure cleanup if not already done
                return
            message = json.dumps(data) + '\n'
            client_socket.sendall(message.encode('utf-8'))
        except (socket.error, BrokenPipeError, OSError) as e: # Added OSError for fileno() issues after close
            print(f"Error sending JSON: {e}")
            # Don't call handle_disconnection from here if it could cause recursion.
            # The receiving thread or main logic should detect and call handle_disconnection.
            # For now, just print and let the caller handle it.
            # self.handle_disconnection(client_socket) # Potentially problematic if called recursively or on already handled socket


    def broadcast_json(self, data, exclude_socket=None):
        # Iterate over a copy of client sockets for safe removal during iteration if needed
        for client_sock in list(self.clients): 
            if client_sock != exclude_socket:
                self.send_json(client_sock, data)
    
    def get_opponent_socket(self, client_socket):
        # Assumes lock is held if self.client_data is modified concurrently
        client_info = self.client_data.get(client_socket)
        if client_info:
            return client_info.get("opponent_socket")
        return None


    def handle_disconnection(self, client_socket):
        # This function MUST be called with self.game_lock already acquired
        # to prevent race conditions on shared lists/dicts.

        if client_socket not in self.client_data and client_socket not in self.clients:
            print(f"Disconnection for an already removed or unknown client.")
            return

        disconnected_player_data = self.client_data.pop(client_socket, {})
        disconnected_player_symbol = disconnected_player_data.get("symbol", "Unknown")
        
        print(f"Handling disconnection for Player {disconnected_player_symbol}...")
        print(f"Clients before removal: {[cd.get('symbol') for cd in self.client_data.values()]}")


        if client_socket in self.clients:
            self.clients.remove(client_socket)
        
        thread_to_remove = self.client_threads.pop(client_socket, None)
        if thread_to_remove:
            print(f"Removed thread reference for Player {disconnected_player_symbol}.")

        try:
            client_socket.close()
            print(f"Socket closed for Player {disconnected_player_symbol}.")
        except (socket.error, OSError):
            print(f"Error closing socket for {disconnected_player_symbol}, might be already closed.")
            pass

        opponent_socket = disconnected_player_data.get("opponent_socket")
        if opponent_socket and opponent_socket in self.client_data:
            print(f"Updating opponent ({self.client_data[opponent_socket].get('symbol')}) of {disconnected_player_symbol}'s disconnection.")
            self.client_data[opponent_socket]["opponent_socket"] = None # Mark opponent as having no paired opponent

        # If a game was active OR if players were deciding a rematch
        if self.game_active or (self.game.game_over and len(self.clients) == 1):
            print(f"Game session was active or pending rematch for Player {disconnected_player_symbol}.")
            self.game.game_over = True # Ensure game is marked over
            self.game_active = False  # Session with this pair is no longer fully active

            if opponent_socket and opponent_socket in self.clients: # Check if opponent_socket is still valid
                self.send_json(opponent_socket, {
                    "type": "opponent_disconnected",
                    "payload": {"message": f"Player {disconnected_player_symbol} has disconnected. Session over."}
                })
                print(f"Notified Player {self.client_data.get(opponent_socket, {}).get('symbol')} about {disconnected_player_symbol}'s disconnection.")
        
        print(f"Clients after removal of {disconnected_player_symbol}: {len(self.clients)} left - {[cd.get('symbol') for cd in self.client_data.values()]}")

        # If NO clients are left, this was the end of a session. Reset everything for a new pair.
        if not self.clients:
            print("All clients from the session have disconnected. Performing full server reset for new session.")
            self.game.reset_game(starting_player="X")    # Resets board, turn, game_over=False etc.
            self.session_scores = {'X': 0, 'O': 0}       # Reset scores
            self.current_session_starting_player = "X"   # Reset starter for next session
            self.client_data.clear()                      # Clear all client specific data
            self.game_active = False                      # Ensure game is not marked active
            self.current_turn_client = None               # No current turn
            print("Server fully reset and ready for a completely new pair of players.")
        elif len(self.clients) == 1:
            # One client remains. They might be waiting for an opponent, or their opponent just left.
            # Ensure game_active is false, as a 2-player game cannot continue.
            self.game_active = False
            self.current_turn_client = None # No active turn if only one player
            remaining_client_symbol = self.client_data.get(self.clients[0], {}).get('symbol')
            print(f"One client ({remaining_client_symbol}) remains. Game is not active. Waiting for another player.")
            # The remaining client might receive an "opponent_disconnected" message if they were in a game.
            # If they were waiting for a game to start, they continue waiting.

    def handle_client(self, client_socket, player_symbol):
        # ... (Welcome message - same as before)
        self.send_json(client_socket, {
            "type": "welcome",
            "payload": {"symbol": player_symbol, "message": f"Welcome! You are Player {player_symbol}."}
        })
        
        try:
            while client_socket in self.clients: # Main loop for this client's connection
                # Wait for game to be active or for messages if game already started/ended
                with self.game_lock:
                    is_active_now = self.game_active
                    is_game_over_now = self.game.game_over
                    is_my_turn_now = (self.current_turn_client == client_socket)

                # If game is active and not over, and it's my turn, prompt is handled by server before this loop iteration
                # This loop is primarily for receiving messages.
                
                buffer = ""
                # Set a timeout so that the loop can check `client_socket in self.clients` condition periodically
                client_socket.settimeout(1.0) 
                try:
                    chunk = client_socket.recv(1024).decode('utf-8')
                    if not chunk: raise ConnectionResetError("Client closed connection (recv returned empty)")
                    buffer += chunk
                    # Process all full JSON messages in the buffer
                    while '\n' in buffer:
                        message_str, buffer = buffer.split('\n', 1)
                        data = json.loads(message_str)
                        self.process_client_message(client_socket, player_symbol, data)
                except socket.timeout:
                    # Timeout allows the outer `while client_socket in self.clients:` to be re-checked
                    # Also check if game is over and we should be prompting for rematch implicitly
                    with self.game_lock:
                        if self.game.game_over and self.game_active: # Game ended, client needs to know to show rematch
                            # This state might imply a message was missed or client needs a nudge
                            pass # Rematch decision is client-initiated by message
                    continue 
                client_socket.settimeout(None) # Reset timeout for blocking operations if any were planned

        except (socket.error, ConnectionResetError, BrokenPipeError, json.JSONDecodeError, KeyError) as e:
            print(f"Error in handle_client for Player {player_symbol}: {e} ({type(e).__name__})")
        finally:
            print(f"Finishing handler for Player {player_symbol}. Cleaning up...")
            with self.game_lock: # Ensure lock is acquired for final cleanup
                self.handle_disconnection(client_socket)


    def process_client_message(self, client_socket, player_symbol, data):
        # This function MUST be called with self.game_lock already acquired
        # because it modifies shared game state. (Caller of handle_client ensures this for message processing part)
        # --> Correction: The game_lock should be acquired *inside* this function for specific operations
        #     or the caller must ensure it. Let's make it explicit here for relevant parts.

        msg_type = data.get("type")
        payload = data.get("payload", {})

        # Acquire lock for operations that change shared state
        # with self.game_lock: # Moved lock to be more granular

        if msg_type == "make_move":
            with self.game_lock: # Lock only for move and subsequent state changes
                if self.game_active and not self.game.game_over and self.current_turn_client == client_socket:
                    col = payload.get("column")
                    if self.game.is_valid_move(col):
                        self.game.make_move(col)
                        board_payload = {"board": self.game.get_board_string()}
                        game_over_payload = None

                        if self.game.check_winner():
                            self.game.game_over = True
                            self.session_scores[self.game.winner] += 1
                            game_over_payload = {"winner": self.game.winner, "message": f"Player {self.game.winner} wins!", "board": self.game.get_board_string()}
                        elif self.game.is_board_full(): # Check after winner
                            self.game.game_over = True
                            game_over_payload = {"draw": True, "message": "It's a draw!", "board": self.game.get_board_string()}
                        
                        if self.game.game_over:
                            # self.game_active remains True until rematch decision or disconnect
                            self.broadcast_json({"type": "game_over", "payload": game_over_payload})
                            self.broadcast_json({"type": "score_update", "payload": {"scores": self.session_scores}})
                            for sock_fd, client_info_val in self.client_data.items(): client_info_val["rematch_requested"] = False # Corrected
                            print(f"Game over. Winner: {self.game.winner}, Draw: {self.game.is_draw}. Scores: {self.session_scores}")
                        else:
                            self.game.switch_player()
                            board_payload["turn"] = self.game.current_player_symbol
                            self.broadcast_json({"type": "board_update", "payload": board_payload})
                            self.current_turn_client = self.get_opponent_socket(client_socket)
                            if self.current_turn_client:
                                 self.send_json(self.current_turn_client, {"type":"your_turn", "payload": {"message": f"Player {self.game.current_player_symbol}'s turn."}})
                    else: # Invalid move
                        self.send_json(client_socket, {"type": "error", "payload": {"error_code": "INVALID_MOVE", "message": "Invalid move."}})
                # else: client tried to move out of turn or when game not active/over
                    # self.send_json(client_socket, {"type": "error", "payload": {"error_code": "OUT_OF_TURN", "message": "Not your turn or game not active."}})

        elif msg_type == "request_rematch":
            with self.game_lock: # Lock for rematch logic
                print(f"Player {player_symbol} requested a rematch.")
                if client_socket in self.client_data: self.client_data[client_socket]["rematch_requested"] = True
                
                opponent_socket = self.get_opponent_socket(client_socket)
                
                # Check if both players (who must still be connected) requested rematch
                can_rematch = False
                if opponent_socket and opponent_socket in self.client_data:
                    if self.client_data[client_socket].get("rematch_requested") and \
                       self.client_data[opponent_socket].get("rematch_requested"):
                        can_rematch = True
                
                if can_rematch:
                    print("Both players agreed to a rematch. Starting new game.")
                    self.current_session_starting_player = "O" if self.current_session_starting_player == "X" else "X"
                    self.game.reset_game(starting_player=self.current_session_starting_player)
                    # game_over is now false from reset_game
                    # game_active remains true as the session continues
                    
                    # Determine who starts this new game
                    # This logic assumes self.clients[0] and self.clients[1] are correctly ordered (X then O)
                    # A more robust way is to check symbols directly
                    p1_sock = self.clients[0]
                    p2_sock = self.clients[1]
                    p1_sym = self.client_data[p1_sock]['symbol']
                    p2_sym = self.client_data[p2_sock]['symbol']

                    if self.game.current_player_symbol == p1_sym: self.current_turn_client = p1_sock
                    elif self.game.current_player_symbol == p2_sym: self.current_turn_client = p2_sock
                    else: # Should not happen
                        self.current_turn_client = p1_sock # Default to first player if symbol mismatch
                        print(f"Warning: Starter symbol {self.game.current_player_symbol} didn't match client symbols {p1_sym}, {p2_sym}")


                    for sock_fd, client_info_val in self.client_data.items(): client_info_val["rematch_requested"] = False # Reset requests
                    
                    self.broadcast_json({"type": "new_game", "payload": {
                        "board": self.game.get_board_string(),
                        "turn": self.game.current_player_symbol,
                        "message": f"Rematch! Player {self.game.current_player_symbol} starts.",
                        "scores": self.session_scores
                    }})
                elif opponent_socket: # Only one requested so far, or opponent hasn't responded
                    self.send_json(client_socket, {"type": "rematch_info", "payload": {"message": "Rematch requested. Waiting for opponent..."}})
                    # Inform opponent only if they haven't requested yet
                    if not self.client_data[opponent_socket].get("rematch_requested"):
                         self.send_json(opponent_socket, {"type": "rematch_info", "payload": {"message": f"Player {player_symbol} wants a rematch! Click 'Play Again'."}})
                else: # Opponent disconnected
                     self.send_json(client_socket, {"type":"info", "payload":{"message": "Cannot rematch, opponent has left."}})
                     # This client might then send quit_session or just disconnect
        
        elif msg_type == "quit_session":
            with self.game_lock: # Lock for quit session
                print(f"Player {player_symbol} quit the session.")
                opponent_socket = self.get_opponent_socket(client_socket)
                if opponent_socket and opponent_socket in self.clients: # Check if opponent_socket is still valid
                    self.send_json(opponent_socket, {"type": "opponent_left_session", 
                                                    "payload": {"message": f"Player {player_symbol} has left the session."}})
                # The `finally` block in the calling `handle_client` will call `handle_disconnection`
                # which will effectively end the game for this client.
                # We need to ensure the client's thread knows to stop.
                # This can be done by removing it from self.clients, which the outer loop checks.
                if client_socket in self.clients:
                    self.clients.remove(client_socket) # This will cause the handle_client loop to exit
                # The actual handle_disconnection will be called by the finally block.


    def run(self):
        try:
            while True:
                ready_to_accept = False
                with self.game_lock:
                    if len(self.clients) < 2:
                        ready_to_accept = True
                        # If we are ready to accept, it means any previous session is fully cleared
                        # or we are waiting for the first/second player of a new session.
                        # Full reset for a new session (scores, client_data) happens in handle_disconnection
                        # when len(self.clients) becomes 0.
                        if len(self.clients) == 0 and (self.game_active or self.game.game_over): # Ensure clean slate if starting fresh
                            print("Server ensuring clean state before accepting new players.")
                            self.game.reset_game("X")
                            self.session_scores = {'X':0, 'O':0}
                            self.client_data.clear()
                            self.current_session_starting_player = "X"
                            self.game_active = False
                            self.current_turn_client = None


                if ready_to_accept:
                    print(f"Waiting for players... ({len(self.clients)}/2 connected). Game Active: {self.game_active}, Game Over: {self.game.game_over}")
                    try:
                        client_sock, address = self.server_socket.accept()
                        print(f"Connection from {address}")
                    except socket.error as e: print(f"Error accepting: {e}"); break
                    except OSError as e: print(f"OSError on accept (server socket likely closed): {e}"); break


                    with self.game_lock:
                        if len(self.clients) >= 2: # Re-check after acquiring lock
                            self.send_json(client_sock, {"type": "error", "payload": {"error_code": "SERVER_FULL", "message": "Server is full."}})
                            try: client_sock.close()
                            except: pass
                            continue

                        player_symbol = "X" if not self.client_data else "O" # Assign X if no client_data, else O
                        
                        self.clients.append(client_sock) # Add to generic list first
                        self.client_data[client_sock] = {
                            "symbol": player_symbol, "rematch_requested": False, "opponent_socket": None
                        }
                        
                        if len(self.clients) == 1: # This is the first player of a pair
                             self.send_json(client_sock, {"type": "info", "payload": {"message": "Waiting for an opponent..."}})
                        elif len(self.clients) == 2:
                            p1_sock, p2_sock = self.clients[0], self.clients[1]
                            self.client_data[p1_sock]["opponent_socket"] = p2_sock
                            self.client_data[p2_sock]["opponent_socket"] = p1_sock
                            
                            # Ensure symbols are distinct if assignment logic had issues
                            if self.client_data[p1_sock]["symbol"] == self.client_data[p2_sock]["symbol"]:
                                self.client_data[p2_sock]["symbol"] = "O" if self.client_data[p1_sock]["symbol"] == "X" else "X"
                            
                            print(f"Two players connected: {self.client_data[p1_sock]['symbol']} and {self.client_data[p2_sock]['symbol']}. Initializing game...")
                            
                            self.game.reset_game(starting_player=self.current_session_starting_player) 
                            self.game_active = True
                            
                            p1_sym = self.client_data[p1_sock]['symbol']
                            p2_sym = self.client_data[p2_sock]['symbol']

                            if self.game.current_player_symbol == p1_sym: self.current_turn_client = p1_sock
                            elif self.game.current_player_symbol == p2_sym: self.current_turn_client = p2_sock
                            else: # Default if mismatch (shouldn't happen with X/O)
                                self.current_turn_client = p1_sock 
                                print(f"Warning: Game starter {self.game.current_player_symbol} didn't match P1({p1_sym}) or P2({p2_sym}). Defaulting to P1.")

                            
                            self.broadcast_json({"type": "game_start", "payload": {
                                "board": self.game.get_board_string(),
                                "turn": self.game.current_player_symbol,
                                "message": f"Game starting! Player {self.game.current_player_symbol}'s turn.",
                                "scores": self.session_scores 
                            }})
                        
                        thread = threading.Thread(target=self.handle_client, args=(client_sock, player_symbol))
                        thread.daemon = True
                        self.client_threads[client_sock] = thread
                        thread.start()
                else: 
                    time.sleep(0.5) # Short sleep if not accepting, to avoid busy-waiting
        except KeyboardInterrupt: print("\nServer shutting down via Ctrl+C...")
        except Exception as e: print(f"Critical unhandled server error in run loop: {e}")
        finally:
            print("Closing all connections and shutting down server socket...")
            for client_sock_final in list(self.clients): # Use a copy
                try: self.send_json(client_sock_final, {"type": "info", "payload": {"message": "Server is shutting down."}})
                except: pass
                try: client_sock_final.close()
                except: pass
            self.server_socket.close()
            print("Server socket closed.")

if __name__ == "__main__":
    server = Connect4Server(port=5555)
    server.run()