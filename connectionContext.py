# connection_context.py

from enum import Enum, auto

class QGPState(Enum):
    STATE_PREINITIALIZATION       = auto()  # cli sends hello, svr sends response -> next
    STATE_INITIALIZATION          = auto()  # svr sends login, svr receives login_response, svr sends login_confirm -> next
    STATE_ACTIVE                  = auto()  # svr and cli exchange messages until cli sends exit command -> closed
    STATE_CLOSED                  = auto()  # departure scripts

class ConnectionContext:
    def __init__(self):
        self.state = QGPState.STATE_PREINITIALIZATION
        self.username = None
        self.game = "Othello"
        self.last_message_type = None

    def advanceState(self):
        match self.state:
            case QGPState.STATE_PREINITIALIZATION:
                self.state = QGPState.STATE_INITIALIZATION
            case QGPState.STATE_INITIALIZATION:
                self.state = QGPState.STATE_ACTIVE
            case QGPState.STATE_ACTIVE:
                self.state = QGPState.STATE_CLOSED
            case _:
                pass
        print(f"state advanced to {self.state}")