# qgp.py
# This is the main driver code for running both the client and server communications via QGP.
# QGP is an application layer protocol over QUIC.
# The demo uses self‐signed certificates provided from the WEBRTC Lab.
# The script was built on the templates provided by WEBRTC Lab.

import socket
import argparse
import asyncio
import subprocess
import sys
import os
from typing import Dict, Optional

from aioquic.asyncio import connect, serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived
from aioquic.tls import SessionTicket

from pdu import MsgType, QGPMessage
from connectionContext import ConnectionContext, QGPState
from datetime import datetime
from Othello.agent   import MinimaxAgent, RandomAgent, HumanPlayer, AlphaBeta
from Othello.othello import State as OthelloState, OthelloMove, PLAYER1, PLAYER2
from Othello.game    import Game as OthelloGame, Player as OthelloPlayer
from Othello.mcts    import mcts


ALPN = "servers_are_fun?"

#define QUIC stream and connection handlers
class QuicStreamEvent:
    def __init__(self, stream_id: int, data: bytes, end_stream: bool):
        self.stream_id = stream_id
        self.data = data
        self.end_stream = end_stream


class EchoQuicConnection:
    def __init__(self, send_func, recv_coro, close_func, new_stream_func):
        self.send = send_func
        self.receive = recv_coro
        self.close = close_func
        self.new_stream = new_stream_func

#pack and send an error message, followed by closing connection
#this can be extended for re-send requests to keep connection open and request resubmission of lost packets
async def send_protocol_error(conn: EchoQuicConnection, stream_id: int, msg: str):
    error = QGPMessage(MsgType.EXIT, message=f"Protocol error: {msg}")
    await conn.send(QuicStreamEvent(stream_id, error.to_bytes(), True))
    conn.close()

#control handoff for Othello game
def launch_othello_subprocess():
    project_root = os.path.dirname(__file__)
    main_py = os.path.join(project_root, "Othello", "main.py")
    subprocess.Popen([sys.executable, main_py])


#timestamps for logs
def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#main server-side protocol script
async def serverProtocol(conn: EchoQuicConnection, stream_id: int):
    ctx = ConnectionContext()

    while True:
        try:
            event = await conn.receive()
            if not isinstance(event, QuicStreamEvent):
                print("No QuicStreamEvent")
                continue
            raw = event.data
            if raw is None or len(raw) == 0:
                print("Nothing was received")
                break

            clientMsg = QGPMessage.from_bytes(raw)
            old_state = ctx.state
            current_state = ctx.state

            # STATE_PREINITIALIZATION
            if current_state == QGPState.STATE_PREINITIALIZATION:
                if clientMsg.type != MsgType.CLIENT_HELLO:
                    await send_protocol_error(
                        conn, stream_id,
                        f"Expected CLIENT_HELLO in {current_state}, got {clientMsg.type}"
                    )
                    return

                # Move to INITIALIZATION
                ctx.advanceState()
                print(f"{timestamp()} [server] State change: {old_state.name} → {ctx.state.name}")

                # 1a) Send SERVER_RESPONSE (no FIN)
                srv_resp = QGPMessage(MsgType.SERVER_RESPONSE, message="Welcome!")
                print(f"{timestamp()} [server] Sending SERVER_RESPONSE: {srv_resp}")
                await conn.send(
                    QuicStreamEvent(stream_id, srv_resp.to_bytes(), False)
                )

                # 1b) Send LOGIN_REQUEST (no FIN)
                login_req = QGPMessage(
                    MsgType.LOGIN_REQUEST,
                    prompt="Please enter username and password"
                )
                print(f"{timestamp()} [server] Sending LOGIN_REQUEST: {login_req}")
                await conn.send(
                    QuicStreamEvent(stream_id, login_req.to_bytes(), False)
                )
                continue

            # STATE_INITIALIZATION
            elif current_state == QGPState.STATE_INITIALIZATION:
                if clientMsg.type != MsgType.LOGIN_RESPONSE:
                    await send_protocol_error(
                        conn, stream_id,
                        f"Expected LOGIN_RESPONSE in {current_state}, got {clientMsg.type}"
                    )
                    return

                # Extract username, transition to ACTIVE
                ctx.username = clientMsg.fields.get("username", "<unknown>")
                ctx.advanceState()
                print(f"{timestamp()} [server] State change: {old_state.name} → {ctx.state.name}")

                # 2a) Send LOGIN_CONFIRM
                login_conf = QGPMessage(
                    MsgType.LOGIN_CONFIRM,
                    status=0,
                    message=f"User {ctx.username} logged in"
                )
                print(f"{timestamp()} [server] Sending LOGIN_CONFIRM: {login_conf}")
                await conn.send(
                    QuicStreamEvent(stream_id, login_conf.to_bytes(), False)
                )

                ctx.othello_state = OthelloState()
                ctx.player2 = MinimaxAgent(3)
                # Build list of legal moves for player1
                moves = ctx.othello_state.generateMoves(PLAYER1)
                moves_list = [str(m) for m in moves]

                # Send initial GAME_STATE with the board and valid moves
                board_str = str(ctx.othello_state)
                game_state_msg = QGPMessage(MsgType.GAME_STATE,board=board_str,moves=moves_list)
                print(f"{timestamp()} [server] Sending GAME_STATE: [initial board + {len(moves_list)} moves]")
                await conn.send(QuicStreamEvent(stream_id, game_state_msg.to_bytes(), False))
                continue

            #  STATE_ACTIVE 
            elif current_state == QGPState.STATE_ACTIVE:
                if clientMsg.type == MsgType.SEND_COMMAND:
                    if "moveIndex" not in clientMsg.fields:
                        await send_protocol_error(
                            conn, stream_id,
                            "SEND_COMMAND missing field moveIndex"
                        )
                        return

                    move_idx = clientMsg.fields["moveIndex"]
                    # If client typed -1 → exit
                    if move_idx == -1:
                        ctx.advanceState()  # STATE_CLOSED
                        print(f"{timestamp()} [server] State change: {old_state.name} → {ctx.state.name}")

                        goodbye = QGPMessage(MsgType.EXIT, message="Server says: Goodbye!")
                        print(f"{timestamp()} [server] Sending EXIT: {goodbye}")
                        await conn.send(QuicStreamEvent(stream_id, goodbye.to_bytes(), True))
                        conn.close()
                        return

                    # Otherwise, get the human’s legal moves
                    legal_moves = ctx.othello_state.generateMoves(ctx.othello_state.nextPlayerToMove)
                    if (not isinstance(move_idx, int)) or move_idx < 0 or move_idx >= len(legal_moves):
                        # Invalid index → resend current board + moves + error
                        board_str = str(ctx.othello_state)
                        moves_list = [str(m) for m in legal_moves]
                        error_reply = QGPMessage(
                            MsgType.GAME_STATE,
                            board=board_str,
                            moves=moves_list,
                            error="Invalid move, please choose again."
                        )
                        print(f"{timestamp()} [server] Received invalid move index={move_idx}, resending board+moves with error")
                        await conn.send(QuicStreamEvent(stream_id, error_reply.to_bytes(), False))
                        continue  # stay in STATE_ACTIVE

                    # 2) Valid human move → apply it and record intermediateBoard
                    chosen_move: OthelloMove = legal_moves[move_idx]
                    ctx.othello_state.applyMove(chosen_move)
                    intermediateBoard = str(ctx.othello_state)
                    print(f"{timestamp()} [server] Applied human move {chosen_move}")

                    # 3) If game is now over (immediately after human move):
                    if ctx.othello_state.game_over():
                        board_str = str(ctx.othello_state)
                        final_msg = QGPMessage(
                            MsgType.GAME_STATE,
                            board=board_str,
                            moves=[],
                            final="Game Over: winner = " + ctx.othello_state.winner()
                        )
                        print(f"{timestamp()} [server] Game over immediately after human move {chosen_move}")
                        await conn.send(QuicStreamEvent(stream_id, final_msg.to_bytes(), False))
                        continue  # remain in STATE_ACTIVE (client should send EXIT)

                    # 4) Let AI move (PLAYER2), build up error_text describing AI and any forced passes:
                    error_text = ""
                    next_player = ctx.othello_state.nextPlayerToMove  # should be PLAYER2
                    ai_moves = ctx.othello_state.generateMoves(next_player)
                    AImove = ctx.player2.choose_move(ctx.othello_state)
                    ctx.othello_state.applyMove(AImove)
                    error_text += f"Opponent applied move {AImove}\n"
                    print(f"{timestamp()} [server] Opponent applied move {AImove}")

                    while True:
                        current_side = ctx.othello_state.nextPlayerToMove
                        human_moves = ctx.othello_state.generateMoves(PLAYER1)
                        ai_moves    = ctx.othello_state.generateMoves(PLAYER2)

                        # (i) Neither side can move → game over
                        if len(human_moves) == 0 and len(ai_moves) == 0:
                            board_str = str(ctx.othello_state)
                            final_msg = QGPMessage(
                                MsgType.GAME_STATE,
                                board=board_str,
                                moves=[],
                                final="Game Over: winner = " + ctx.othello_state.winner()
                            )
                            print(f"{timestamp()} [server] Game over after skipping turns")
                            await conn.send(QuicStreamEvent(stream_id, final_msg.to_bytes(), False))
                            return

                        # Human’s turn but no moves → pass them, continue letting AI move again
                        if current_side == PLAYER1 and len(human_moves) == 0:
                            ctx.othello_state.applyMove(None)  
                            error_text += "Human had no moves → passed\n"
                            print(f"{timestamp()} [server] Human had no legal moves, passed")
                            current_side = ctx.othello_state.nextPlayerToMove
                            ai_moves     = ctx.othello_state.generateMoves(current_side)
                            if len(ai_moves) == 0:
                                #its a gameover state... go confirm it
                                continue

                            AImove = ctx.player2.choose_move(ctx.othello_state)
                            ctx.othello_state.applyMove(AImove)
                            error_text += f"Opponent applied move {AImove}\n"
                            print(f"{timestamp()} [server] Opponent applied move {AImove}")
                            continue

                        if current_side == PLAYER1 and len(human_moves) > 0:
                            break

                        if current_side == PLAYER2 and len(ai_moves) > 0:
                            AImove = ctx.player2.choose_move(ctx.othello_state)
                            ctx.othello_state.applyMove(AImove)
                            error_text += f"Opponent applied move {AImove}\n"
                            print(f"{timestamp()} [server] Opponent applied move {AImove}")
                            continue

                    board_str = str(ctx.othello_state)
                    human_moves = ctx.othello_state.generateMoves(PLAYER1)
                    human_moves_list = [str(m) for m in human_moves]

                    # Trim trailing newline in error_text
                    if error_text.endswith("\n"):
                        error_text = error_text[:-1]

                    reply = QGPMessage(
                        MsgType.GAME_STATE,
                        board=board_str,
                        intermediateBoard=intermediateBoard,
                        error=error_text if error_text else None,
                        moves=human_moves_list
                    )
                    print(f"{timestamp()} [server] Sending updated board + {len(human_moves_list)} moves to client")
                    await conn.send(QuicStreamEvent(stream_id, reply.to_bytes(), False))
                    continue

                elif clientMsg.type == MsgType.EXIT:
                    ctx.advanceState()  # → STATE_CLOSED
                    print(f"{timestamp()} [server] State change: {old_state.name} → {ctx.state.name}")
                    goodbye = QGPMessage(MsgType.EXIT, message="Server says: Goodbye!")
                    print(f"{timestamp()} [server] Sending EXIT: {goodbye}")
                    await conn.send(QuicStreamEvent(stream_id, goodbye.to_bytes(), True))
                    conn.close()
                    return

                else:
                    await send_protocol_error(
                        conn, stream_id,
                        f"Expected SEND_COMMAND or EXIT in {current_state}, got {clientMsg.type}"
                    )
                    return

            # STATE_CLOSED 
            elif current_state == QGPState.STATE_CLOSED:
                return

            else:
                await send_protocol_error(
                    conn, stream_id,
                    f"Invalid server state {current_state}"
                )
                return

        except Exception as e:
            await send_protocol_error(conn, stream_id, f"Exception: {e}")
            return



#main client-side protocol script
#mirror of server-side logic but wait in each state until we move to next
#send hello immediately
async def clientProtocol(scope: Dict, conn: EchoQuicConnection):
    ctx = ConnectionContext()

    # STATE_PREINITIALIZATION: Send CLIENT_HELLO 
    if ctx.state != QGPState.STATE_PREINITIALIZATION:
        return

    hello = QGPMessage(
        MsgType.CLIENT_HELLO,
        version=1,
        gameName="Othello",
        options=0
    )
    sid = conn.new_stream()
    print(f"{timestamp()} [client] Sending CLIENT_HELLO: {hello}")
    await conn.send(QuicStreamEvent(sid, hello.to_bytes(), False))

    old_state = ctx.state
    ctx.advanceState()
    print(f"{timestamp()} [client] State change: {old_state.name} → {ctx.state.name}")

    #  STATE_INITIALIZATION: Expect SERVER_RESPONSE 
    ev = await conn.receive()
    serverMsg = QGPMessage.from_bytes(ev.data)
    if serverMsg.type != MsgType.SERVER_RESPONSE:
        await send_protocol_error(conn, sid, "Expected SERVER_RESPONSE")
        return
    print(f"{timestamp()} [client] Received SERVER_RESPONSE: {serverMsg}")

    #  STATE_INITIALIZATION: Expect LOGIN_REQUEST 
    ev = await conn.receive()
    serverMsg = QGPMessage.from_bytes(ev.data)
    if serverMsg.type != MsgType.LOGIN_REQUEST:
        await send_protocol_error(conn, sid, "Expected LOGIN_REQUEST")
        return
    prompt = serverMsg.fields.get("prompt", "")
    print(f"{timestamp()} [client] Received LOGIN_REQUEST, prompt: '{prompt}'")

    # 3) Send LOGIN_RESPONSE
    username = input("  Username: ").strip()
    password = input("  Password: ").strip()
    login_resp = QGPMessage(MsgType.LOGIN_RESPONSE,username=username,password=password)
    print(f"{timestamp()} [client] Sending LOGIN_RESPONSE: {login_resp}")
    await conn.send(QuicStreamEvent(sid, login_resp.to_bytes(), False))

    # INITIALIZATION → now expect LOGIN_CONFIRM
    ev = await conn.receive()
    serverMsg = QGPMessage.from_bytes(ev.data)
    if serverMsg.type != MsgType.LOGIN_CONFIRM:
        await send_protocol_error(conn, sid, "Expected LOGIN_CONFIRM")
        return
    print(f"{timestamp()} [client] Received LOGIN_CONFIRM: {serverMsg}")

    # Transition to ACTIVE
    old_state = ctx.state
    ctx.advanceState()
    print(f"{timestamp()} [client] State change: {old_state.name} → {ctx.state.name}")

    # STATE_ACTIVE: First, receive the initial GAME_STATE from server
    while True:
        ev = await conn.receive()
        serverMsg = QGPMessage.from_bytes(ev.data)

        # Must be GAME_STATE or EXIT
        if serverMsg.type == MsgType.GAME_STATE:
            board_str = serverMsg.fields.get("board", "")
            intermediateBoard = serverMsg.fields.get("intermediateBoard", None)
            moves_list = serverMsg.fields.get("moves", [])
            error_msg  = serverMsg.fields.get("error", None)
            final_msg  = serverMsg.fields.get("final", None)
            
            if intermediateBoard:
                print(intermediateBoard)

            if error_msg:
                print(f"\n{timestamp()} [client] Message: {error_msg}")

            print(f"{timestamp()} [client] Received BOARD:\n{board_str}")


            if final_msg:
                print(f"{timestamp()} [client] {final_msg}")
                # Now game is over. Ask user to hit Enter to acknowledge, then send EXIT
                input("Press Enter to exit the game…")
                goodbye = QGPMessage(MsgType.EXIT, message="Client says: exit")
                print(f"{timestamp()} [client] Sending EXIT: {goodbye}")
                await conn.send(QuicStreamEvent(sid, goodbye.to_bytes(), True))
                ctx.advanceState()
                print(f"{timestamp()} [client] State change: STATE_ACTIVE → {ctx.state.name}")
                conn.close()
                return

            # Otherwise, print the list of valid moves with indices
            print(f"{timestamp()} [client] Available moves:")
            for idx, move_str in enumerate(moves_list):
                print(f"  {idx} → {move_str}")
            print(f"  -1 → exit")

            # Prompt user for input
            user_input = input("Enter move index (or -1 to exit): ").strip()
            if user_input.lower() in ("-1", "exit"):
                goodbye = QGPMessage(MsgType.EXIT, message="Client says: exit")
                print(f"{timestamp()} [client] Sending EXIT: {goodbye}")
                await conn.send(QuicStreamEvent(sid, goodbye.to_bytes(), True))
                ctx.advanceState()
                print(f"{timestamp()} [client] State change: STATE_ACTIVE → {ctx.state.name}")
                conn.close()
                return

            # Otherwise, try to parse an integer
            try:
                move_index = int(user_input)
            except ValueError:
                print(f"{timestamp()} [client] Invalid input; you must type an integer index or -1.")
                continue

            # Build and send SEND_COMMAND(moveIndex)
            cmd_msg = QGPMessage(MsgType.SEND_COMMAND, moveIndex=move_index)
            print(f"{timestamp()} [client] Sending SEND_COMMAND: {cmd_msg}")
            await conn.send(QuicStreamEvent(sid, cmd_msg.to_bytes(), False))
            continue

        elif serverMsg.type == MsgType.EXIT:
            farewell = serverMsg.fields.get("message", "")
            print(f"{timestamp()} [client] Received EXIT from server: {farewell}")
            ctx.advanceState()
            print(f"{timestamp()} [client] State change: STATE_ACTIVE → {ctx.state.name}")
            return

        else:
            await send_protocol_error(conn, sid, "Expected GAME_STATE or EXIT in STATE_ACTIVE")
            return


# QUIC Protocol Handler
class EchoServerHandler:
    def __init__(self, connection, protocol, stream_id: int):
        self.connection = connection
        self.protocol   = protocol
        self.stream_id  = stream_id
        self.queue      = asyncio.Queue()
        self._protocol_task: Optional[asyncio.Task] = None

    async def handle_event(self, event):
        # Enqueue the raw PDU
        if isinstance(event, StreamDataReceived):
            self.queue.put_nowait(
                QuicStreamEvent(event.stream_id, event.data, event.end_stream)
            )
        else:
            return

        # On the very first PDU, spawn one long‐running serverProtocol
        # this ensures that the state is not accidentally reset
        if self._protocol_task is None:
            conn = EchoQuicConnection(self._send, self._receive, self._close, None)
            self._protocol_task = asyncio.create_task(
                serverProtocol(conn, self.stream_id)
            )

    async def _receive(self) -> QuicStreamEvent:
        return await self.queue.get()

    async def _send(self, qev: QuicStreamEvent):
        self.connection.send_stream_data(qev.stream_id, qev.data, qev.end_stream)
        self.protocol.transmit()

    def _close(self):
        self.protocol.remove_handler(self.stream_id)
        self.connection.close()


class EchoClientHandler:
    def __init__(self, connection, protocol):
        self.connection = connection
        self.protocol = protocol
        self.queue = asyncio.Queue()
        self._stream_id_assigned = False
        self.done = asyncio.Event()

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            self.queue.put_nowait(
                QuicStreamEvent(event.stream_id, event.data, event.end_stream)
            )

    async def launch(self):
        conn = EchoQuicConnection(self._send, self._receive, self._close, self._new_stream)
        await clientProtocol({}, conn)

        self.done.set()

    async def _receive(self) -> QuicStreamEvent:
        return await self.queue.get()

    async def _send(self, qev: QuicStreamEvent):
        self.connection.send_stream_data(qev.stream_id, qev.data, qev.end_stream)
        self.protocol.transmit()

    def _new_stream(self) -> int:
        sid = self.connection.get_next_available_stream_id()
        return sid

    def _close(self):
        self.connection.close()


class AsyncQGPProtocol(QuicConnectionProtocol):
    def __init__(self, *args, mode=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._mode = mode
        self._handlers = {}
        self._handler = None

        if mode == "client":
            self._handler = EchoClientHandler(self._quic, self)

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print(f"[protocol:{self._mode}] HandshakeCompleted (connection is up)")
            if self._mode == "client":
                asyncio.ensure_future(self._handler.launch())

        if isinstance(event, StreamDataReceived):
            print(f"[protocol:{self._mode}] StreamDataReceived on stream {event.stream_id}, {len(event.data)} bytes")
            if self._mode == "server":
                handler = self._handlers.setdefault(
                    event.stream_id,
                    EchoServerHandler(self._quic, self, event.stream_id)
                )
                asyncio.ensure_future(handler.handle_event(event))
            else:
                self._handler.quic_event_received(event)

    def remove_handler(self, stream_id: int):
        self._handlers.pop(stream_id, None)


# Determine which main script to run
# server is bound to 0.0.0.0   print the local IP
async def run_server(listen_address: str, listen_port: int, configuration: QuicConfiguration):
    bind_host = "0.0.0.0" if listen_address in ("", "localhost") else listen_address
    print(f"[server] Server starting... Listening on {bind_host}:{listen_port}")
    printLocalIPs()
    await serve(
        host=bind_host,
        port=listen_port,
        configuration=configuration,
        create_protocol=lambda *args, **kwargs: AsyncQGPProtocol(*args, mode="server", **kwargs),
        session_ticket_fetcher=SessionTicketStore().pop,
        session_ticket_handler=SessionTicketStore().add
    )
    await asyncio.Future() 

# query user for IP address
async def run_client(server: str, server_port: int, configuration: QuicConfiguration):
    print(f"[client] Client connecting to {server}:{server_port}...")
    async with connect(
        server,
        server_port,
        configuration=configuration,
        create_protocol=lambda *args, **kwargs: AsyncQGPProtocol(*args, mode="client", **kwargs)
    ) as client:
        await client._handler.done.wait()

#TLS bypassed in this demos
class SessionTicketStore:
    def __init__(self):
        self.tickets = {}

    def add(self, ticket: SessionTicket):
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes):
        return self.tickets.pop(label, None)


def printLocalIPs():
    hostname = socket.gethostname()
    print(f"[server] Host name: {hostname}")
    try:
        addrs = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
        seen = set()
        print("[server] Local IPv4 addresses:")
        for entry in addrs:
            ip = entry[4][0]
            if ip not in seen and not ip.startswith("127."):
                seen.add(ip)
                print("   " + ip)
    except Exception as e:
        print(f"[server] Unable to enumerate local IPs: {e}")


def serverConfig(certFile: str, keyFile: str) -> QuicConfiguration:
    configuration = QuicConfiguration(alpn_protocols=[ALPN], is_client=False)
    configuration.load_cert_chain(certFile, keyFile)
    return configuration


def clientConfig() -> QuicConfiguration:
    configuration = QuicConfiguration(alpn_protocols=[ALPN], is_client=True)
    configuration.verify_mode = False
    return configuration


def parse_args():
    parser = argparse.ArgumentParser(description="QUIC Game Protocol")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server_parser = subparsers.add_parser("server", help="Run as server")
    server_parser.add_argument("--listen", "-l", default="0.0.0.0",
                               help="IP address to bind (default: 0.0.0.0)")
    server_parser.add_argument("--port", "-p", type=int, default=12345,
                               help="Port to listen on (default: 12345)")
    server_parser.add_argument("--cert-file", type=str, required=True,
                               help="Path to TLS certificate PEM file")
    server_parser.add_argument("--key-file", type=str, required=True,
                               help="Path to TLS private key PEM file")

    client_parser = subparsers.add_parser("client", help="Run as client")
    client_parser.add_argument("--server", "-s", type=str, help="Server IP address")
    client_parser.add_argument("--port", "-p", type=int, default=12345,
                               help="Server port (default: 12345)")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "server":
        server_config = serverConfig(args.cert_file, args.key_file)
        asyncio.run(run_server(args.listen, args.port, server_config))
    elif args.mode == "client":
        if not args.server:
            args.server = input("Enter server IP address: ").strip()
        client_config = clientConfig()
        asyncio.run(run_client(args.server, args.port, client_config))
    exit(0)
