import unittest
import socket
import time
import threading
from unittest import mock

from betfairlightweight.streaming.betfairstream import BetfairStream


class BetfairStreamTest(unittest.TestCase):

    def setUp(self):
        self.mock_listener = mock.Mock()
        self.unique_id = 1
        self.app_key = 'app_key'
        self.session_token = 'session_token'
        self.timeout = 6
        self.buffer_size = 1024
        self.description = 'test_stream'
        self.betfair_stream = BetfairStream(self.unique_id, self.mock_listener, self.app_key, self.session_token,
                                            self.timeout, self.buffer_size, self.description)

    def test_init(self):
        assert self.betfair_stream.unique_id == self.unique_id
        assert self.betfair_stream.listener == self.mock_listener
        assert self.betfair_stream.app_key == self.app_key
        assert self.betfair_stream.session_token == self.session_token
        assert self.betfair_stream.timeout == self.timeout
        assert self.betfair_stream.buffer_size == self.buffer_size
        assert self.betfair_stream.description == self.description

        assert self.betfair_stream._socket is None
        assert self.betfair_stream._running is False

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._read_loop')
    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._receive_all', return_value={})
    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._create_socket')
    def test_start(self, mock_create_socket, mock_receive_all, mock_read_loop):
        self.betfair_stream.start()

        assert self.betfair_stream._running is True
        mock_create_socket.assert_called_with()
        mock_receive_all.assert_called_with()
        self.mock_listener.on_data.assert_called_with({}, self.unique_id)
        mock_read_loop.assert_called_with()

    def test_stop(self):
        self.betfair_stream.stop()
        assert self.betfair_stream._running is False

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._send')
    def test_authenticate(self, mock_send):
        self.betfair_stream.authenticate()
        mock_send.assert_called_with(
                {'id': self.unique_id, 'appKey': self.app_key, 'session': self.session_token, 'op': 'authentication'}
        )

        self.betfair_stream.authenticate(999)
        mock_send.assert_called_with(
                {'id': 999, 'appKey': self.app_key, 'session': self.session_token, 'op': 'authentication'}
        )

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._send')
    def test_heartbeat(self, mock_send):
        self.betfair_stream.heartbeat()
        mock_send.assert_called_with(
                {'id': self.unique_id, 'op': 'heartbeat'}
        )

        self.betfair_stream.heartbeat(999)
        mock_send.assert_called_with(
                {'id': 999, 'op': 'heartbeat'}
        )

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._send')
    def test_subscribe_to_markets(self, mock_send):
        market_filter = {'test': 123}
        market_data_filter = {'another_test': 123}
        self.betfair_stream.subscribe_to_markets(market_filter, market_data_filter)
        mock_send.assert_called_with(
                {'op': 'marketSubscription', 'marketFilter': market_filter, 'id': self.unique_id,
                 'marketDataFilter': market_data_filter}
        )

        self.betfair_stream.subscribe_to_markets(market_filter, market_data_filter, 666)
        mock_send.assert_called_with(
                {'op': 'marketSubscription', 'marketFilter': market_filter, 'id': 666,
                 'marketDataFilter': market_data_filter}
        )

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._send')
    def test_subscribe_to_orders(self, mock_send):
        self.betfair_stream.subscribe_to_orders()
        mock_send.assert_called_with(
                {'id': self.unique_id, 'op': 'orderSubscription'}
        )

        self.betfair_stream.subscribe_to_orders(999)
        mock_send.assert_called_with(
                {'id': 999, 'op': 'orderSubscription'}
        )

    @mock.patch('ssl.wrap_socket')
    @mock.patch('socket.socket')
    def test_create_socket(self, mock_socket, mock_wrap_socket):
        self.betfair_stream._create_socket()

        mock_socket.assert_called_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_wrap_socket.assert_called()

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._data', return_value=False)
    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream._receive_all', return_value='{}\r\n')
    def test_read_loop(self, mock_receive_all, mock_data):
        mock_socket = mock.Mock()
        self.betfair_stream._socket = mock_socket

        self.betfair_stream._running = True
        threading.Thread(target=self.betfair_stream._read_loop).start()

        for i in range(0, 2):
            time.sleep(0.1)
        self.betfair_stream._running = False
        time.sleep(0.1)

        mock_data.assert_called_with('{}')
        mock_socket.close.assert_called_with()

    def test_receive_all(self):
        mock_socket = mock.Mock()
        data_return_value = b'{"op":"status"}\r\n'
        mock_socket.recv.return_value = data_return_value
        self.betfair_stream._socket = mock_socket

        data = self.betfair_stream._receive_all()
        assert data == ''

        self.betfair_stream._running = True
        data = self.betfair_stream._receive_all()
        mock_socket.recv.assert_called_with(self.buffer_size)
        assert data == data_return_value.decode('utf-8')

    @mock.patch('betfairlightweight.streaming.betfairstream.BetfairStream.stop')
    def test_data(self, mock_stop):
        self.mock_listener.on_data.return_value = False
        received_data = {"op": "status"}
        self.betfair_stream._data(received_data)

        self.mock_listener.on_data.assert_called_with(received_data)
        assert mock_stop.called

        self.mock_listener.on_data.return_value = True
        self.betfair_stream._data(received_data)

        self.mock_listener.on_data.assert_called_with(received_data)
        assert mock_stop.call_count == 1

    def test_send(self):
        mock_socket = mock.Mock()
        self.betfair_stream._socket = mock_socket
        message = {'message': 1}

        self.betfair_stream._send(message)
        assert mock_socket.send.call_count == 1
