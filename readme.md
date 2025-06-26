## QUIC Game Protocol: An Application Layer Demonstration

**Author**: David Everly  
**Language**: Python  
**Version**: 1 

---

# Description  
QGP.py is a script which supports a proof-of-concept (POC) implementation of the Quick Game Protocol over QUIC.
In brief, the script defines the PDU and DFA, as well as common class definitions in pdu.py and connectionContext.py.
With QGP running on two separate terminals, server and client, the script is designed to send communications from one terminal
to another using QUIC transport.  This state-based protocol uses fixed Protocol Data Units (PDU) to progress through
the Deterministic Finite Automata (DFA) in structured fashion. The active state of the DFA allows for ongoing communications
between server and client to support an interactive gaming interface.  The connection persists until client or server request
termination.

As proof of concept, QGP was configured to support a minimal implementation of the game Othello.  Information about game
rules and valid moves can easily be found elsewhere and are generally not within the scope of the POC for QGP. The game
states are send from the server with each new iteration, while user inputs are sent from the client. 


## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Configuration](#configuration)
- [Examples](#examples)
- [Results and Conclusion](#results-and-conclusion)
- [Future Work and Extension](#future-work-and-extension)
- [References](#references)
- [Contributing](#contributing)
- [Licenses](#licenses)

# Installation
Dependencies:
- aioquic==1.0.0
- asyncio==3.4.3
- attrs==23.2.0
- certifi==2024.2.2
- cffi==1.16.0
- cryptography==42.0.5
- dnslib==0.9.24
- pyasn1==0.5.1
- pyasn1-modules==0.3.0
- pycparser==2.21
- pylsqpack==0.3.18
- pyOpenSSL==24.1.0
- service-identity==24.1.0

Install using:  
```bash
pip install -r requirements.txt  
```  

Temporary certifications are in the certs directory

# Usage
Program is intended to be run using Unix-like terminal such as Linux, macOS Terminal (untested), or MINGW64 (Git Bash) on Windows.
For convenience, executable shell scripts are provided.

On two separate Unix-compatible terminals

to run server: 
```bash
./server
```
to run client: 
```bash
./client
```

Run the server first and wait for the server listening message to run the client.  When the client runs, the user is asked for
the server's IP address.  Note that the server prints its local IP address.  Enter the IP address as shown on the server terminal
to begin the connection.

The Connection continues automatically until login authentication begins.  The client is asked to enter a username and password.
Any string can be entered and will be accepted by the server, progressing to the active state.  During the active state, the
server and client exchange game states and game commands respectively.  The connection persists until the game is over or either
client request to exit.  Once the game completes, the final game state and results are displayed and the connection termination
process begins.

# Features  
## Game Coordinates
The coordinate system of the game board is zero-indexed, starting in the top left corner and moving top->bottom and left->right
Moves are listed in y,x order so:

Move x to 0,1 corresponds to:  
  
........  
x.......  
........  
........  
........  
........  
........  
........  

and 

Move x to 5,3 corresponds to:  
  
........  
........  
........  
........  
........  
...x....  
........  
........  

# Configuration  
## PDU
Valid PDUs used to progres through the DFA are provided for reference:
    CLIENT_HELLO    
    SERVER_RESPONSE 
    LOGIN_REQUEST   
    LOGIN_RESPONSE  
    LOGIN_CONFIRM   
    SEND_COMMAND    
    GAME_STATE      
    EXIT            

## DFA
PDUs signal progression to the next state as follors:
    STATE_PREINITIALIZATION - prior to CLIENT_HELLO, ends with SERVER_RESPONSE
    STATE_INITIALIZATION    - begins with SERVER_RESPONSE and continues until LOGIN_CONFIRM
    STATE_ACTIVE            - begins with LOGIN_CONFIRM and continues until EXIT
    STATE_CLOSED            - begins with EXIT until connection termination

Connection termination behavior differs between client and server.  While the client exits the program, the server remains
active to support new connection. Native behavior allows the server to support multiple connections concurrently.

# Examples  


# Results and Conclusion
The program is a demonstration of a state-aware application layer protocol implementation over QUIC

## Proof of Concept
This POC is meant to prove that GCP is capable of supporting game state messages across a network.  This is not a deployment-ready
implementation.  Note that login authentication, in its current state, will accept and confirm any username or password string sent 
from the client.  Futhermore, certifications were taken from those provided by course instructor and are set to be ignored by
QUIC TLS.  The program contains no security implementations and would be particularly vulnerable to DDOS attack unless the
activity would be detected and mitigated via QUIC. Finally, the port number is bound to 12345 for both server and client, and 
the gameName is hardcoded to support only the Othello game.  The server is designed to never close except by interrupt
or killing the terminal; a deployment-ready implementation should provide a way to close the server.

# Future Work and Extension  
The program is designed with several future extensions in mind. With minor changes, QGP can be extended to support multiple games
or persistent connection to support repeated playthroughs of the same game. The send_protocol_error method can be extended for
resend requests of invalid messages, or valid packages received during the incorrect connection state.  Another obvious extension
is to allow the client to choose difficulty levels. Othello contains multiple different AI models which vary in complexity. Some
of the models are likely to outperform most novice Othello players.  I selected a model which performs well-enough to be
challenging to defeat.

# References  
No external sources were used. However, LLM queries assisted with architectural design and debugging.  

# Contributing  
Code architecture was built over a minimal template which was provided to me by Drexel University during Graduate studies in 2025.

# Licenses  
None