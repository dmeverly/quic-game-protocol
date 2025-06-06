# Othello/mcts.py

import math
import random
import sys
import time

# Instead of "import game", "import agent", force package imports:
from Othello.game  import Game, Player
from Othello.agent import RandomAgent

TIMER = False

class mcts(Player):
    def __init__(self, timer):
        super().__init__()
        self.timer = timer
        self.id = ""
        self.startTime = time.time()*1000
        self.totalTime = time.time()*1000 - self.startTime

        if len(sys.argv) > 1 and sys.argv[1] == "mcts":
            self.id = 'Player 1'
        else:
            self.id = 'Player 2'

    def choose_move(self, state):
        self.startTime = time.time()*1000
        corners = []
        if self.id == 'Player 1':
            self.root = self.createNode(state, None, [], None, 0, 0, 0, True)
            corners.extend([
                f"Player O to 0,0",
                f"Player O to 7,7",
                f"Player O to 0,7",
                f"Player O to 7,0"
            ])
        else:
            self.root = self.createNode(state, None, [], None, 0, 0, 0, False)
            corners.extend([
                f"Player X to 0,0",
                f"Player X to 7,7",
                f"Player X to 0,7",
                f"Player X to 7,0"
            ])

        exploredStates = hashTable()
        self.totalTime = 0
        iterations = 0

        if len(self.root.movesRemaining) < 1:
            return None
        if len(self.root.movesRemaining) == 1:
            return self.root.movesRemaining[0]

        # If any corner is available, take it immediately
        for legalMove in self.root.movesRemaining:
            if str(legalMove) in corners:
                self.totalTime = time.time() - (self.startTime/1000)
                print(f"Total Iterations = 0")
                print(f"Total Time = {self.totalTime} seconds")
                return legalMove

        if TIMER:
            while (self.totalTime < self.timer - 100):
                iterations += 1
                node = self.treePolicy(self.root, exploredStates)
                if node is not None:
                    node2 = self.defaultPolicy(node)
                    Node2Score = self.score(node2)
                    self.backup(node, Node2Score)
                self.totalTime = time.time()*1000 - self.startTime
            selection = self.bestChild(self.root).action
            print(f"Total Iterations = {iterations}")
            return selection

        while iterations < self.timer:
            iterations += 1
            node = self.treePolicy(self.root, exploredStates)
            if node is not None:
                node2 = self.defaultPolicy(node)
                Node2Score = self.score(node2)
                self.backup(node, Node2Score)
            self.totalTime = time.time() - (self.startTime/1000)
        selection = self.bestChild(self.root).action
        print(f"Total Time = {self.totalTime} seconds")
        return selection

    def createNode(self, state, parent, children, action, used, score, value, maximizer):
        return node(state, parent, children, action, used, score, value, maximizer)

    def bestChild(self, node):
        if len(node.children) == 1:
            return node.children[0]
        maxChild = node.children[0]
        for child in node.children:
            child.findValue()
            if child.value > maxChild.value:
                maxChild = child
        return maxChild

    def treePolicy(self, currentNode, exploredStates):
        if len(currentNode.state.generateMoves()) < 1:
            return currentNode

        while len(currentNode.movesRemaining) > 0:
            move = random.choice(currentNode.movesRemaining)
            newState = currentNode.state.applyMoveCloning(move)
            currentNode.movesRemaining.remove(move)
            newNode = node(newState, currentNode, [], move, 0, 0, 0, currentNode.setChildGoal(currentNode.maximizer))
            currentNode.children.append(newNode)
            if not exploredStates.statePresent(newState):
                exploredStates.add(newState)
                return newNode

        return self.treePolicy(self.bestChild(currentNode), exploredStates)

    def defaultPolicy(self, currentNode):
        tempPlayer1 = RandomAgent()
        tempPlayer2 = RandomAgent()
        # Silence the console while playing out
        backup_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        tempGame = Game(currentNode.state, tempPlayer1, tempPlayer2)
        finalState = tempGame.playMCTS()
        sys.stdout.close()
        sys.stdout = backup_stdout
        return finalState

    def score(self, state):
        return state.score()

    def backup(self, node, score):
        node.used += 1
        if node.maximizer:
            if score == 0:
                node.score += 0.5
            if score < 0:
                node.score += 1
        else:
            if score == 0:
                node.score += 0.5
            if score > 0:
                node.score += 1
        if node.parent is not None:
            self.backup(node.parent, score)


class node:
    def __init__(self, state, parent, children, action, used, score, value, maximizer):
        self.state = state
        self.parent = parent
        self.children = children
        self.action = action
        self.used = used
        self.score = score
        self.value = value
        self.maximizer = maximizer
        self.movesRemaining = state.generateMoves()

    def findValue(self):
        if self.used != 0:
            self.value = (self.score / self.used) + math.sqrt(2) * math.sqrt(math.log(self.parent.used) / self.used)
        elif self.parent.used > 0:
            self.value = math.sqrt(2) * math.sqrt(math.log(self.parent.used))
        else:
            self.value = math.sqrt(2) * math.sqrt(math.log(self.parent.used + 1))

    def setChildGoal(self, parentGoal):
        return not parentGoal


class hashTable:
    def __init__(self):
        self.hashMap = dict()

    def add(self, state):
        h = state.heuristic()
        hstate = linkedList(state, None)
        if h in self.hashMap:
            nxt = self.hashMap[h]
            while nxt.next is not None:
                nxt = nxt.next
            nxt.next = hstate
        else:
            self.hashMap[h] = hstate

    def statePresent(self, state):
        h = state.heuristic()
        if h in self.hashMap:
            nxt = self.hashMap[h]
            if nxt.value == state:
                return True
            while nxt.next is not None:
                if nxt.value == state:
                    return True
                nxt = nxt.next
        return False


class linkedList:
    def __init__(self, value, nxt):
        self.value = value
        self.next = nxt
