"""Forward Docker-side SOCKS connections to the host's loopback Xray listener."""
import os
import selectors
import socket
import socketserver


class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            upstream = socket.create_connection(('127.0.0.1', 10808), timeout=10)
            upstream.settimeout(None)
            with upstream, selectors.DefaultSelector() as selector:
                selector.register(self.request, selectors.EVENT_READ, upstream)
                selector.register(upstream, selectors.EVENT_READ, self.request)
                while selector.get_map():
                    for key, _ in selector.select(timeout=300):
                        data = key.fileobj.recv(65536)
                        if data:
                            key.data.sendall(data)
                        else:
                            selector.unregister(key.fileobj)
                            key.data.shutdown(socket.SHUT_WR)
        except OSError as exc:
            print(f'Xray relay connection failed: {exc}', flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    # Bind only Docker's host gateway, never all host interfaces.
    address = (os.environ.get('XRAY_RELAY_BIND', '172.17.0.1'), int(os.environ.get('XRAY_RELAY_PORT', '10809')))
    with Server(address, Relay) as server:
        print(f'Xray relay listening on {address[0]}:{address[1]}', flush=True)
        server.serve_forever()
