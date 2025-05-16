import pygame
import socket
import threading
import json
import sys
import time

# --- Pygame Constants ---
SQUARESIZE = 80
COLUMN_COUNT = 7
ROW_COUNT = 6
WIDTH = COLUMN_COUNT * SQUARESIZE
TOP_MARGIN = SQUARESIZE # For status, scores, dropping piece
BOTTOM_MARGIN = SQUARESIZE # For buttons
HEIGHT = (ROW_COUNT * SQUARESIZE) + TOP_MARGIN + BOTTOM_MARGIN # Corrected height calculation
SIZE = (WIDTH, HEIGHT)
RADIUS = int(SQUARESIZE / 2 - 5)

# Colors
BLUE = (0, 0, 200)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
YELLOW = (200, 200, 0)
WHITE = (255, 255, 255)
GREY = (150, 150, 150)
GREEN = (0, 200, 0)
LIGHT_GREY = (200, 200, 200)

# --- Custom Pygame Events for Network Messages ---
SERVER_MESSAGE_EVENT = pygame.USEREVENT + 1

class Button:
    def __init__(self, x, y, width, height, text='Button', color=GREY, text_color=BLACK, font_size=30):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.text = text
        self.text_color = text_color
        self.font = pygame.font.SysFont("monospace", font_size)
        self.is_hovered = False
        self.visible = True # Added visibility flag

    def draw(self, screen):
        if not self.visible:
            return
        current_color = LIGHT_GREY if self.is_hovered else self.color
        pygame.draw.rect(screen, current_color, self.rect, border_radius=5)
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def check_hover(self, mouse_pos):
        if not self.visible:
            self.is_hovered = False
            return
        self.is_hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

class Connect4ClientPygame:
    def __init__(self, server_ip, port=5555):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_ip = server_ip
        self.port = port
        self.connected = False
        self.player_symbol = None 
        self.opponent_symbol = None
        self.my_turn = False
        self.game_over = False
        self.board_array = [[' ' for _ in range(COLUMN_COUNT)] for _ in range(ROW_COUNT)]
        self.status_message = "Connecting..."
        self.hover_column = -1
        
        self.running_main_loop = True # For the main pygame loop
        self.running_networking = True # For the networking thread

        self.scores = {'X': 0, 'O': 0}
        self.my_score = 0
        self.opponent_score = 0
        self.rematch_requested_by_me = False
        self.rematch_info_message = ""

        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode(SIZE)
        pygame.display.set_caption("Connect 4: The Rematch!")
        self.font = pygame.font.SysFont("monospace", 25)
        self.score_font = pygame.font.SysFont("monospace", 22)

        button_y = (ROW_COUNT + 1) * SQUARESIZE + (BOTTOM_MARGIN - 50) / 2 # Centered in bottom margin
        button_width = 180
        button_height = 50
        spacing = 20
        total_button_width = 2 * button_width + spacing
        start_x = (WIDTH - total_button_width) // 2

        self.play_again_button = Button(start_x, button_y, button_width, button_height, "Play Again?", GREEN)
        self.quit_button = Button(start_x + button_width + spacing, button_y, button_width, button_height, "Quit", RED)
        self.play_again_button.visible = False # Initially hidden
        self.quit_button.visible = False      # Initially hidden


    def connect_to_server(self):
        try:
            print(f"Attempting to connect to server at {self.server_ip}:{self.port}...")
            self.client_socket.connect((self.server_ip, self.port))
            self.connected = True
            print(f"Successfully connected to server.")
            self.status_message = "Connected. Waiting for game..."
            
            self.network_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.network_thread.start()
            return True
        except socket.error as e:
            self.status_message = f"Connect Failed: {e}"; self.game_over = True; return False

    def send_json_to_server(self, data):
        if not self.connected: return
        try:
            message = json.dumps(data) + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
        except (socket.error, BrokenPipeError) as e:
            print(f"Error sending JSON: {e}.")
            self.status_message = "Connection lost (send error)."
            self.connected = False; self.game_over = True
            self.running_networking = False # Signal network thread to stop


    def receive_messages(self):
        buffer = ""
        while self.running_networking:
            if not self.connected:
                break 
            try:
                # Set a timeout for recv so the loop can check running_networking more often
                self.client_socket.settimeout(0.5) # Timeout of 0.5 seconds
                chunk = self.client_socket.recv(4096).decode('utf-8')
                self.client_socket.settimeout(None) # Reset timeout for other operations if any

                if not chunk: # Server closed connection gracefully
                    print("\nServer closed the connection.")
                    event_data = {"custom_type": "info", "payload": {"message": "Server disconnected."}}
                    pygame.event.post(pygame.event.Event(SERVER_MESSAGE_EVENT, {"server_data": event_data}))
                    self.connected = False
                    break 
                
                buffer += chunk
                while '\n' in buffer:
                    message_str, buffer = buffer.split('\n', 1)
                    try:
                        data_from_server = json.loads(message_str)
                        pygame.event.post(pygame.event.Event(SERVER_MESSAGE_EVENT, {"server_data": data_from_server}))
                    except json.JSONDecodeError:
                        print(f"\n[Warning] Received invalid JSON: '{message_str[:100]}...'")
                        error_payload = {"custom_type": "internal_error", "payload": {"message": "Invalid JSON from server."}}
                        pygame.event.post(pygame.event.Event(SERVER_MESSAGE_EVENT, {"server_data": error_payload}))
            
            except socket.timeout:
                continue # Timeout allows checking self.running_networking; just continue loop
            except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                if self.running_networking: # Only report if we weren't already shutting down
                    print(f"\nConnection error in receive: {e}.")
                    event_data = {"custom_type": "info", "payload": {"message": "Connection error."}}
                    pygame.event.post(pygame.event.Event(SERVER_MESSAGE_EVENT, {"server_data": event_data}))
                self.connected = False
                break 
            except Exception as e:
                 if self.running_networking:
                     print(f"\nUnexpected error in receive_messages: {e}.")
                     event_data = {"custom_type": "info", "payload": {"message": f"Network receive error: {type(e).__name__}"}}
                     pygame.event.post(pygame.event.Event(SERVER_MESSAGE_EVENT, {"server_data": event_data}))
                 self.connected = False
                 break
        
        self.running_networking = False # Ensure this is false when loop exits
        self.connected = False
        print("Networking thread stopped.")

    def handle_server_message_event(self, event_dict_from_pygame):
        actual_server_data = event_dict_from_pygame.get("server_data")
        if not actual_server_data:
            print(f"Received empty/malformed custom event: {event_dict_from_pygame}")
            return

        msg_type = actual_server_data.get("type") or actual_server_data.get("custom_type")
        payload = actual_server_data.get("payload", {})
        
        print(f"GUI Handling: Type='{msg_type}', Payload='{payload}'")

        if msg_type == "welcome":
            self.player_symbol = payload.get("symbol")
            self.opponent_symbol = 'O' if self.player_symbol == 'X' else 'X'
            self.status_message = payload.get("message", "Welcome!")
            self.rematch_info_message = ""
        elif msg_type == "info":
            self.status_message = payload.get("message", "Info.")
            if "Server disconnected" in self.status_message or "Connection error" in self.status_message:
                self.game_over = True; self.connected = False
                self.running_main_loop = False # Signal main Pygame loop to end
        elif msg_type == "internal_error":
             self.status_message = f"Client Error: {payload.get('message', 'Unknown internal error.')}"
        elif msg_type == "error":
            self.status_message = f"Err: {payload.get('message', 'Unknown')}"
            if payload.get('error_code') == "SERVER_FULL": self.running_main_loop = False
        elif msg_type == "game_start" or msg_type == "new_game":
            self.status_message = payload.get("message", "Game starting!")
            self.parse_and_update_board_from_string(payload.get("board"))
            self.my_turn = (payload.get("turn") == self.player_symbol)
            self.game_over = False
            self.play_again_button.visible = False; self.quit_button.visible = False
            self.rematch_requested_by_me = False
            self.rematch_info_message = ""
            if "scores" in payload:
                self.scores = payload["scores"]
                self.my_score = self.scores.get(self.player_symbol, 0)
                self.opponent_score = self.scores.get(self.opponent_symbol, 0)
        elif msg_type == "board_update":
            self.parse_and_update_board_from_string(payload.get("board"))
            self.my_turn = (payload.get("turn") == self.player_symbol)
            if not self.game_over:
                 self.status_message = f"Your turn!" if self.my_turn else f"Player {payload.get('turn')}'s turn."
        elif msg_type == "your_turn":
            self.my_turn = True
            if not self.game_over: self.status_message = payload.get("message", f"Your turn!")
        elif msg_type == "game_over":
            self.status_message = payload.get("message", "Game Over!")
            if payload.get("board"): self.parse_and_update_board_from_string(payload.get("board"))
            self.game_over = True; self.my_turn = False
            self.play_again_button.visible = True; self.quit_button.visible = True
            self.rematch_info_message = "" 
        elif msg_type == "score_update":
            self.scores = payload.get("scores", {'X':0, 'O':0})
            self.my_score = self.scores.get(self.player_symbol, 0)
            self.opponent_score = self.scores.get(self.opponent_symbol, 0)
        elif msg_type == "rematch_info":
            self.rematch_info_message = payload.get("message", "")
        elif msg_type == "opponent_disconnected" or msg_type == "opponent_left_session":
            self.status_message = payload.get("message", "Opponent left.")
            self.game_over = True; self.my_turn = False; self.rematch_info_message = "Session ended."
            self.play_again_button.visible = False # No rematch if opponent left
            self.quit_button.visible = True # Only quit option makes sense
            self.running_main_loop = False # Can choose to end client or just show final state
        else:
            print(f"[Unknown Message Type in GUI Handler]: Type: {msg_type}, Payload: {payload}")

    def parse_and_update_board_from_string(self, board_string):
        if not board_string: return
        lines = board_string.strip().split('\n')
        game_rows = []
        for line in lines:
            if line.startswith("| ") and line.endswith(" |"):
                parts = line[2:-2].split(" | ")
                if len(parts) == COLUMN_COUNT: game_rows.append(parts)
        if len(game_rows) >= ROW_COUNT:
            for r in range(ROW_COUNT):
                for c in range(COLUMN_COUNT):
                    self.board_array[r][c] = game_rows[r][c] if game_rows[r][c] in ['X', 'O'] else ' '

    def draw_board_and_pieces(self):
        board_y_offset = TOP_MARGIN
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                pygame.draw.rect(self.screen, BLUE, (c * SQUARESIZE, r * SQUARESIZE + board_y_offset, SQUARESIZE, SQUARESIZE))
                piece_in_board = self.board_array[r][c]
                piece_color = BLACK 
                if piece_in_board == 'X': piece_color = RED
                elif piece_in_board == 'O': piece_color = YELLOW
                pygame.draw.circle(self.screen, piece_color, 
                                   (int(c * SQUARESIZE + SQUARESIZE / 2), 
                                    int(r * SQUARESIZE + SQUARESIZE / 2 + board_y_offset)), RADIUS)

    def draw_dropping_piece_preview(self):
        if self.my_turn and not self.game_over and self.player_symbol and self.hover_column != -1:
            color = RED if self.player_symbol == 'X' else YELLOW
            pygame.draw.circle(self.screen, color, (self.hover_column * SQUARESIZE + SQUARESIZE // 2, TOP_MARGIN // 2), RADIUS)

    def run_game(self):
        if not self.connect_to_server():
            self.draw_game_elements(); pygame.display.flip(); time.sleep(3)
            self.cleanup_and_exit()
            return # Important: return here to prevent further execution

        clock = pygame.time.Clock()

        while self.running_main_loop:
            mouse_pos = pygame.mouse.get_pos()
            self.hover_column = mouse_pos[0] // SQUARESIZE if TOP_MARGIN <= mouse_pos[1] < TOP_MARGIN + ROW_COUNT * SQUARESIZE else -1


            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running_main_loop = False
                
                if event.type == SERVER_MESSAGE_EVENT:
                    self.handle_server_message_event(event.dict)

                if event.type == pygame.MOUSEMOTION:
                    self.play_again_button.check_hover(mouse_pos)
                    self.quit_button.check_hover(mouse_pos)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.game_over:
                        if self.play_again_button.is_clicked(event):
                            if not self.rematch_requested_by_me:
                                self.send_json_to_server({"type": "request_rematch"})
                                self.rematch_requested_by_me = True
                                self.rematch_info_message = "Rematch requested..."
                                self.play_again_button.visible = False # Hide after click
                        elif self.quit_button.is_clicked(event):
                            self.running_main_loop = False
                    elif self.my_turn:
                        # Check if click is within the board dropping area (top margin) or on columns themselves
                        col = mouse_pos[0] // SQUARESIZE
                        # Ensure click is in the valid area above the board for dropping
                        if 0 <= col < COLUMN_COUNT and mouse_pos[1] < TOP_MARGIN + (ROW_COUNT * SQUARESIZE) :
                            self.send_json_to_server({"type": "make_move", "payload": {"column": col}})
                            self.my_turn = False 
                            self.status_message = "Move sent..."
            
            self.draw_game_elements()
            pygame.display.flip()
            clock.tick(30)

        self.cleanup_and_exit()

    def cleanup_and_exit(self):
        print("Client cleanup_and_exit called.")
        self.running_networking = False # Signal networking thread
        if self.connected:
            if hasattr(self, 'client_socket'): # Check if socket exists
                 # Optionally send a quit message if server is designed to handle it
                self.send_json_to_server({"type": "quit_session"}) # Let server know
                time.sleep(0.1) # Give it a moment to send
        
        if hasattr(self, 'network_thread') and self.network_thread.is_alive():
            print("Waiting for network thread to join...")
            self.network_thread.join(timeout=1.0) # Short timeout

        if hasattr(self, 'client_socket'): # Check if socket exists
            try:
                print("Shutting down client socket...")
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except (socket.error, OSError): pass 
            finally:
                try: self.client_socket.close()
                except (socket.error, OSError): pass
        
        self.connected = False
        print("Client has shut down.")
        pygame.quit()
        sys.exit()


    def draw_game_elements(self):
        self.screen.fill(BLACK)
        
        pygame.draw.rect(self.screen, BLACK, (0,0, WIDTH, TOP_MARGIN)) # Area for dropping piece
        self.draw_dropping_piece_preview()

        self.draw_board_and_pieces() # Draws board below the top margin
        
        y_offset = 10
        if self.status_message:
            msg_surf = self.font.render(self.status_message, True, WHITE, BLACK) # Added background for readability
            msg_rect = msg_surf.get_rect(centerx=WIDTH/2, top=y_offset)
            self.screen.blit(msg_surf, msg_rect)
            y_offset += msg_surf.get_height() + 5

        if self.player_symbol:
            score_text = f"You ({self.player_symbol}): {self.my_score}  Opp ({self.opponent_symbol}): {self.opponent_score}"
            score_surf = self.score_font.render(score_text, True, WHITE, BLACK) # Added background
            score_rect = score_surf.get_rect(centerx=WIDTH/2, top=y_offset)
            self.screen.blit(score_surf, score_rect)
            y_offset += score_surf.get_height() + 5
        
        if self.rematch_info_message:
            rematch_msg_surf = self.score_font.render(self.rematch_info_message, True, LIGHT_GREY, BLACK) # Added background
            rematch_rect = rematch_msg_surf.get_rect(centerx=WIDTH/2, top=y_offset)
            self.screen.blit(rematch_msg_surf, rematch_rect)

        if self.game_over: # Buttons are only drawn if game is over
            self.play_again_button.draw(self.screen)
            self.quit_button.draw(self.screen)


if __name__ == "__main__":
    default_ip = 'localhost'
    try:
        temp_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); temp_s.connect(("8.8.8.8", 80))
        local_ip_suggestion = temp_s.getsockname()[0]; temp_s.close()
        default_ip = local_ip_suggestion
    except socket.error: pass

    server_ip = input(f"Enter Server IP (e.g., {default_ip}): ").strip() or default_ip
    
    client_game = Connect4ClientPygame(server_ip)
    client_game.run_game() # This now calls connect_to_server internally