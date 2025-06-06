# Othello/main.py

from Othello import agent, othello, game, mcts
import sys
import re
import importlib
import os
import time
import csv

def create_player(arg, depth_or_time):
    if arg == 'human':
        return agent.HumanPlayer()
    elif arg == 'random':
        return agent.RandomAgent()
    elif arg == 'minimax':
        return agent.MinimaxAgent(depth_or_time)
    elif arg == 'alphabeta':
        return agent.AlphaBeta(depth_or_time)
    elif check_pattern(arg) or arg == 'mcts':
        if not os.path.exists(arg + ".py"):
            print("The agent is not defined in the system!")
            exit(1)
        module = importlib.import_module(arg)
        my_agent = getattr(module, arg)
        return my_agent(depth_or_time)
    else:
        print("The agent is not defined in the system!")
        exit(1)

def check_pattern(text):
    pattern = r'[a-z]{2,4}\d{2,4}'
    return re.match(pattern, text)

def get_arg(index, default=None):
    return sys.argv[index] if len(sys.argv) > index else default

if __name__ == '__main__':
    initial_state = othello.State()

    if len(sys.argv) > 1:
        agent1 = sys.argv[1]
        agent2 = sys.argv[2]
        depth_or_time = 3
    if len(sys.argv) == 4:
        depth_or_time = int(sys.argv[3])

    player1 = create_player(get_arg(1), depth_or_time)
    player2 = create_player(get_arg(2), depth_or_time)

    # Or for a built‐in test:
    # player1 = agent.RandomAgent()
    # player2 = mcts.mcts(10000)

    gm = game.Game(initial_state, player1, player2)
    gm.play()

    # Example: run 10 random‐vs‐MCTS matches and log results
    Winners = []
    gameTimes = []
    output = [["Random vs MCTS 10,000 Sim/Move"], ["Game", "Winner", "Time (seconds)"]]

    for i in range(10):
        startTime = time.time()
        final_state = gm.play()
        stopTime = time.time()
        winner = final_state.winner()
        gameTime = stopTime - startTime
        Winners.append(winner)
        gameTimes.append(gameTime)

    for i, w in enumerate(Winners):
        print(f"Game {i+1} Result")
        print(f"Winner = {w}")
        print(f"Total Game Time = {gameTimes[i]} seconds")
        data = [i+1, w, gameTimes[i]]
        output.append(data)

    with open('output.csv', 'a', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerows(output)
