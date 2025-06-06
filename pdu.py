# PDU definition and management

import json
from enum import IntEnum

#defines valid communication states (PDU)

class MsgType(IntEnum):
    CLIENT_HELLO    = 1
    SERVER_RESPONSE = 2
    LOGIN_REQUEST   = 3
    LOGIN_RESPONSE  = 4
    LOGIN_CONFIRM   = 5
    SEND_COMMAND    = 6
    GAME_STATE      = 7
    EXIT            = 8

#defines a valid message with methods to convert to and from bytes for sending over wire
#type is the int representation of the valid MsgTypes defined above
#fields are the payload
class QGPMessage:
    def __init__(self, mtype: MsgType, **fields):
        self.type = int(mtype)
        self.fields = fields

    def to_bytes(self) -> bytes:
        return json.dumps({
            "type": self.type,
            "fields": self.fields
        }).encode("utf-8")

    @staticmethod
    def from_bytes(data: bytes) -> "QGPMessage":
        obj = json.loads(data.decode("utf-8"))
        mtype = MsgType(obj["type"])
        return QGPMessage(mtype, **obj["fields"])

    def __repr__(self):
        return f"<QGPMessage type={self.type} fields={self.fields}>"
