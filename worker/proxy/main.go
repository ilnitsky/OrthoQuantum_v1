package main

import (
	"bufio"
	"bytes"
	"crypto/tls"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"time"

	"golang.org/x/net/proxy"
)

type RoConn struct {
	net.Conn
	buf *bytes.Buffer
}

func (conn RoConn) Read(p []byte) (n int, err error) {
	n, err = conn.Conn.Read(p)
	if n > 0 {
		_, _ = conn.buf.Write(p[:n])
	}
	return
}
func (conn RoConn) Write(p []byte) (int, error) {
	return 0, io.ErrClosedPipe
}
func (conn RoConn) Close() error {
	return nil
}
func (conn RoConn) SetDeadline(_ time.Time) error {
	return nil
}
func (conn RoConn) SetReadDeadline(_ time.Time) error {
	return nil
}
func (conn RoConn) SetWriteDeadline(_ time.Time) error {
	return nil
}

func getSNIAddr(conn net.Conn) (serverName string, buf *bytes.Buffer) {
	buf = new(bytes.Buffer)
	roConn := RoConn{
		Conn: conn,
		buf:  buf,
	}

	_ = tls.Server(
		roConn,
		&tls.Config{
			GetConfigForClient: func(helloInfo *tls.ClientHelloInfo) (*tls.Config, error) {
				serverName = helloInfo.ServerName
				return nil, nil
			},
		},
	).Handshake()
	return
}

var wg sync.WaitGroup
var socksServerAddr string

func doProxying(conn net.Conn, target string, buf *bytes.Buffer) {
	var localWG sync.WaitGroup
	timer := time.AfterFunc(10*time.Minute, func() { conn.Close() })
	defer func() {
		if timer.Stop() {
			conn.Close()
		}
	}()

	proxyDialer, err := proxy.SOCKS5("tcp", socksServerAddr, nil, proxy.Direct)
	if err != nil {
		log.Printf("Can't connect to local proxy server: %s", err)
		return
	}

	srvConn, err := proxyDialer.Dial("tcp", target)
	if err != nil {
		log.Printf("Can't connect to %s: %s", target, err)
		return
	}
	defer srvConn.Close()

	if DEBUG {
		log.Printf("Started proxying connection to %s", target)
	}
	localWG.Add(2)
	go func() {
		defer func() {
			_ = conn.(*net.TCPConn).CloseWrite()
			localWG.Done()
		}()
		_, _ = io.Copy(conn, srvConn)
	}()

	go func() {
		defer func() {
			_ = srvConn.(*net.TCPConn).CloseWrite()
			localWG.Done()
		}()
		_, err := io.Copy(srvConn, buf)
		if err != nil {
			return
		}
		_, _ = io.Copy(srvConn, conn)
	}()
	localWG.Wait()
	if DEBUG {
		log.Printf("Ended proxying to %s", target)
	}
}

func handleHTTPConnection(conn net.Conn) {
	defer wg.Done()

	buf := new(bytes.Buffer)
	roConn := RoConn{
		Conn: conn,
		buf:  buf,
	}
	rq, err := http.ReadRequest(bufio.NewReader(roConn))

	if err != nil || rq.Host == "" {
		log.Printf("Failed to get server name from http connection: %s", err)
		conn.Close()
		return
	}
	host, port, err := net.SplitHostPort(rq.Host)
	if err != nil {
		host = rq.Host
		port = "80"
	}
	doProxying(conn, net.JoinHostPort(host, port), buf)
}

func handleHTTPSConnection(conn net.Conn) {
	defer wg.Done()

	serverName, buf := getSNIAddr(conn)
	if DEBUG {
		log.Printf("SN: '%s', len: %d", serverName, buf.Len())
	}
	if serverName == "" {
		log.Println("Failed to get server name from https connection")
		conn.Close()
		return
	}

	doProxying(conn, net.JoinHostPort(serverName, "443"), buf)
}

type handlerFunc func(net.Conn)

func acceptAndHandle(l net.Listener, handler handlerFunc) {
	defer wg.Done()
	for {
		conn, err := l.Accept()
		if err != nil {
			return
		}
		wg.Add(1)
		go handler(conn)
	}
}

func getEnv(name string) string {
	val, found := os.LookupEnv(name)
	if !found {
		log.Fatalf("Env variable %s not set", name)
	}
	return val
}
func main() {
	socksServerAddr = net.JoinHostPort(getEnv("SOCKS_SERVER"), getEnv("SOCKS_PORT"))

	httpL, err := net.Listen("tcp", "127.0.0.1:80")
	if err != nil {
		log.Fatalf("Can't start listening on port 80: %s", err)
	}
	httpsL, err := net.Listen("tcp", "127.0.0.1:443")
	if err != nil {
		log.Fatalf("Can't start listening on port 443: %s", err)
	}
	wg.Add(2)
	go acceptAndHandle(httpL, handleHTTPConnection)
	go acceptAndHandle(httpsL, handleHTTPSConnection)

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)

	log.Println("Started proxy server")
	defer log.Println("Proxy server finished")
	// Block until a signal is received.
	<-c
	httpL.Close()
	httpsL.Close()
	wg.Wait()

}
