import struct
from attr import attrs, attrib
from attr.validators import instance_of
from twisted.internet.interfaces import ITransport, IProducer, IConsumer
from automat import MethodicalMachine
from nacl.secret import SecretBox
from nacl.exceptions import CryptoError
from . import _interfaces



@attrs
@implementer(_interfaces.IDilatedConnection)
class DilatedConnection(object):
    _wormhole = attrib()
    m = MethodicalMachine()
    set_trace = getattr(m, "_setTrace", lambda self, f: None)

    # I represent the durable connection for any Wormhole that has been
    # dilated. At any given time, I am either connected or not (there are
    # exactly 0 or 1 live connections). I manage the queue of messages and
    # their acks.

    def __attrs_post_init__(self):
        self._unacked_messages = []
        self._queued_messages = []
        self._connection = None

    @m.state(initial=True)
    def not_connected(self): pass # pragma: no cover

    @m.state()
    def connected(self): pass # pragma: no cover

    @m.input()
    def connection_made(self, connection):
        pass

    @m.input()
    def connection_lost(self):
        pass

    @m.input()
    def send(self, message):
        pass
    @m.input()
    def receive_ack(self, ack):
        pass

    @m.output()
    def send_queued_messages(self, connection):
        XXX
    @m.output()
    def queue_message(self, message):
        XXX
    @m.output()
    def queue_and_send_message(self, message):
        XXX
    @m.output()
    def process_ack(self, ack):
        XXX

    not_connected.upon(connection_made, enter=connected,
                       outputs=[send_queued_messages])
    not_connected.upon(send, enter=not_connected, outputs=[queue_message])
    connected.upon(send, enter=connected, outputs=[queue_and_send_message])
    connected.upon(receive_ack, enter=connected, outputs=[process_ack])
    connected.upon(connection_lost, enter=not_connected, outputs=[])

class OldPeerCannotDilateError(Exception):
    pass

@attrs
class Dilation(object):
    _w = attrib(validator=instance_of(IWormhole))

    def __attrs_post_init__(self):
        self._l3_waiters = []
        self._l3 = None

        
    def _wait_for_l3(self):
        d = Deferred()
        if self._l3 is not None:
            d.callback(self._l3)
        else:
            self._l3_waiters.append(d)
        return d

    def _l3_created(self, l3):
        assert self._l3 is None
        self._l3 = l3
        for d in self._l3_waiters:
            d.callback(l3)
        del self._l3_waiters

    def start(self):
        # we return the Endpoints right away, but any connections or listeners
        # must wait until we get the keys and version data
        ccep = ControlChannelEndpoint(self._wait_for_l3())
        osep = OutboundSubchannelEndpoint(self._wait_for_l3())
        isep = InboundSubchannelEndpoint(self._wait_for_l3())

        d = self._w._get_wormhole_versions()
        def _derive_keys(res):
            our_side, their_side, wormhole_versions = res
            can_dilate = wormhole_versions.get("can-dilate", 0) # int
            if can_dilate < 1:
                self._l3_created(Failure(OldPeerCannotDilateError()))
                return
            self._is_leader = our_side > their_side
            lf_key = self._w.derive_key("dilation: leader->follower",
                                        SecretBox.KEY_SIZE)
            fl_key = self._w.derive_key("dilation: follower->leader",
                                        SecretBox.KEY_SIZE)
            if self._is_leader:
                inbound_box = SecretBox(fl_key)
                outbound_box = SecretBox(lf_key)
            else:
                inbound_box = SecretBox(lf_key)
                outbound_box = SecretBox(fl_key)
            l3 = L3Connection(self._w, self._is_leader,
                              inbound_box, outbound_box)
            l3.start()
            self._l3_created(l3)
            # except that we don't do this, L3 does when it lacks an L2
            self._w._boss._S.send("lets-dilate-1", something)
        d.addCallback(_derive_keys)
        d.addErrback(log.err)

        return (ccep, osep, isep)

def start_dilator(w):
    d = Dilator(w)
    endpoints = d.start()
    return endpoints

# An object to manage the connection process for LETS-DILATE-n (one such object
# per 'n').

class ConnectorThingy:
    n = attrib()

    def event_rx_hints(hints): pass
        # initiate outbound connection to each hint
    def event_listener_ready(hint): pass
    def event_connection_finished_negotiation(p):
        # might cancel all orhers, or might wait for something better
        pass
    def event_nothing_better_timer_fired(): pass
    def event_cancel(): pass

    def output_notify_l3(): pass
    
    
