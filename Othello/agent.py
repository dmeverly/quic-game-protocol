# Othello/agent.py

import math
import random
import sys
import time

# Instead of "import game" (which would look in sys.path for a 'game' module),
# explicitly import from the Othello package:
from Othello.game import Player
from Othello.othello import State, OthelloMove, PLAYER1, PLAYER2

class HumanPlayer(Player):
    def __init__(self):
        super().__init__()

    def choose_move(self, state: State):
        moves = state.generateMoves()
        for i, action in enumerate(moves):
            print(f"{i}: {action}")
        response = input("Please choose a move: ")
        return moves[int(response)]


class RandomAgent(Player):
    def __init__(self):
        super().__init__()

    def choose_move(self, state: State):
        moves = state.generateMoves()
        if len(moves) > 0:
            return random.choice(moves)
        return None


class MinimaxAgent(Player):
    def __init__(self, depth: int):
        super().__init__()
        self.depth = depth
        self.id = ""
        # Determine whether this agent is Player 1 or 2 by looking at sys.argv
        if len(sys.argv) > 1 and sys.argv[1] == "minimax":
            self.id = 'Player 1'
        else:
            self.id = 'Player 2'

    def choose_move(self, state: State):
        moves = state.generateMoves()
        if len(moves) < 1:
            return None

        if self.id == 'Player 1':
            return self.search(state, 'max', self.depth)
        else:
            return self.search(state, 'min', self.depth)

    def search(self, state: State, goal: str, depthLimit: int):
        root = node(state, None, None, goal, None, 0)
        stateSpace = []
        root.expand(depthLimit)

        # No legal moves -> pass
        if len(root.children) < 1:
            return None
        # Exactly one move -> pick it
        if len(root.children) == 1:
            return root.children[0].move

        # Otherwise build the state‐space up to depthLimit
        for child in root.children:
            stateSpace.append(child)
        for n in stateSpace:
            n.expand(depthLimit)
            for child in n.children:
                stateSpace.append(child)

        currentDepth = depthLimit
        while currentDepth > 0:
            for n in stateSpace:
                if n.depth == currentDepth:
                    n.parent.scoreParent()
                    n.parent.children.clear
            currentDepth -= 1

        # Choose the best child
        bestChild = root.children[0]
        if root.goal == 'max':
            for child in root.children:
                if child.score > bestChild.score:
                    bestChild = child
        else:
            for child in root.children:
                if child.score < bestChild.score:
                    bestChild = child

        return bestChild.move


class AlphaBeta(Player):
    def __init__(self, depth: int):
        super().__init__()
        self.depth = depth
        self.id = ""
        self.startTime = time.time() * 1000
        self.totalTime = time.time() * 1000 - self.startTime

        if len(sys.argv) > 1 and sys.argv[1] == "alphabeta":
            self.id = 'Player 1'
        else:
            self.id = 'Player 2'

    def choose_move(self, state: State):
        self.startTime = time.time() * 1000
        moves = state.generateMoves()
        if len(moves) < 1:
            return None
        if len(moves) == 1:
            return moves[0]

        if self.id == 'Player 1':
            root = node(state, None, None, 'max', None, 0)
        else:
            root = node(state, None, None, 'min', None, 0)

        best = self.ABSearch(self.depth, -math.inf, math.inf, root)
        for child in root.children:
            if child.score == best:
                self.totalTime = time.time() * 1000 - self.startTime
                print(f"Total Time = {self.totalTime/1000} seconds")
                return child.move

    def ABSearch(self, depthLimit, alpha, beta, parent):
        # Terminal test
        if parent.depth >= depthLimit or parent.state.game_over():
            return parent.state.heuristic()

        moves = parent.state.generateMoves()
        if len(moves) < 1:
            return parent.state.heuristic()

        if parent.goal == 'max':
            maximum = -math.inf
            for move in moves:
                newState = parent.state.applyMoveCloning(move)
                newNode = node(newState, parent, None, 'min', move, parent.depth+1)
                parent.children.append(newNode)
                maximum = max(maximum, self.ABSearch(depthLimit, alpha, beta, newNode))
                newNode.score = maximum
                alpha = max(alpha, maximum)
                if beta <= alpha:
                    break
            return maximum

        else:  # parent.goal == 'min'
            minimum = math.inf
            for move in moves:
                newState = parent.state.applyMoveCloning(move)
                newNode = node(newState, parent, None, 'max', move, parent.depth+1)
                parent.children.append(newNode)
                minimum = min(minimum, self.ABSearch(depthLimit, alpha, beta, newNode))
                newNode.score = minimum
                beta = min(beta, minimum)
                if beta <= alpha:
                    break
            return minimum


class node:
    def __init__(self, state, parent, score, goal, move, depth):
        self.parent = parent
        self.children = []
        self.score = score
        self.state = state
        self.goal = goal
        self.move = move
        self.depth = depth
        self.expanded = False
        self.scored = False

    def expand(self, depthLimit):
        if self.expanded:
            return
        self.expanded = True
        if self.depth > depthLimit:
            return

        moves = self.state.generateMoves()
        childGoal = 'min' if self.goal == 'max' else 'max'

        for move in moves:
            newState = self.state.applyMoveCloning(move)
            if self.depth + 1 >= depthLimit:
                self.children.append(node(newState, self, newState.heuristic(), childGoal, move, self.depth+1))
            else:
                self.children.append(node(newState, self, None, childGoal, move, self.depth+1))

    def scoreParent(self):
        if not self.children or self.scored:
            return
        self.scored = True

        if self.goal == 'max':
            if self.children[0].score is None:
                self.children[0].score = self.children[0].state.heuristic()
            maxScore = self.children[0].score
            for child in self.children:
                if child.score is None:
                    child.score = child.state.heuristic()
                maxScore = max(maxScore, child.score)
            self.score = maxScore
        else:
            if self.children[0].score is None:
                self.children[0].score = self.children[0].state.heuristic()
            minScore = self.children[0].score
            for child in self.children:
                if child.score is None:
                    child.score = child.state.heuristic()
                minScore = min(minScore, child.score)
            self.score = minScore
