# Othello/game.py

from Othello.othello import State, PLAYER1, PLAYER2

class Player:
    def choose_move(self, state: State):
        raise NotImplementedError


class Game:
    def __init__(self, initial_state: State, player1: Player, player2: Player):
        self.initial_state = initial_state
        self.players = [player1, player2]

    def play(self):
        state = self.initial_state.clone()
        player_index = 0

        while not state.game_over():
            print("\nCurrent state, " + str(PLAYER_NAMES[state.nextPlayerToMove]) + " to move:")
            print(state)
            player = self.players[player_index]
            move = player.choose_move(state)
            if move is not None:
                print(move)
            state = state.applyMoveCloning(move)
            player_index = (player_index + 1) % len(self.players)

        print("\n*** Final winner: " + state.winner() + " ***")
        print(state)
        return state  # return final state or list of states as needed

    def playMCTS(self):
        state = self.initial_state.clone()
        player_index = 0
        while not state.game_over():
            player = self.players[player_index]
            move = player.choose_move(state)
            state = state.applyMoveCloning(move)
            player_index = (player_index + 1) % len(self.players)
            if abs(state.heuristic()) > 50:
                return state
        return state
