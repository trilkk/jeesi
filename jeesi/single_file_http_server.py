import threading
from http.server import *

from jeesi.common import is_verbose

########################################
# Globals ##############################
########################################

g_served_content = None
g_served_content_encoding = None
g_help_string = """====
HTTP server has been started to provide the ['Content-Encoding', 'br']
header required for a for the compressed payload.
You may open the following link in your browser:
http://localhost:%i
===="""

########################################
# Functions ############################
########################################

class SingleFileRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler always serving a single file."""

    def do_GET(self):
        """Serve GET request."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        if g_served_content_encoding:
            self.send_header("Content-Encoding", g_served_content_encoding)
        self.send_header("Content-Length", str(len(g_served_content)))
        self.end_headers()
        self.wfile.write(g_served_content)

########################################
# Functions ############################
########################################

def async_serve_forever(srv):
    """Async task to run serve_forever()."""
    srv.serve_forever()

def create_single_file_http_server(port, uncompressed_file, compressed_file):
    """Creates a HTTP server at given port, serving given file(s)."""
    global g_served_content
    global g_served_content_encoding
    if compressed_file and compressed_file.exists() and (compressed_file.suffix.lower() == ".br"):
        if is_verbose():
            print("SingleFileRequestHandler: serving compressed file '%s' (%i bytes)" % (compressed_file, compressed_file.stat().st_size))
        with compressed_file.open("rb") as fd:
            g_served_content = fd.read()
        g_served_content_encoding = "br"
    elif uncompressed_file and uncompressed_file.exists():
        if is_verbose():
            print("SingleFileRequestHandler: serving uncompressed file '%s' (%i bytes)" % (uncompressed_file, uncompressed_file.stat().st_size))
        with uncompressed_file.open("rb") as fd:
            g_served_content = fd.read()
    else:
        raise RuntimeError("no file to serve in %s" % (str([uncompressed_file, compressed_file])))
    return ThreadingHTTPServer(("", port), SingleFileRequestHandler)

def get_single_file_http_server_help(port):
    """Gets the help string for the single file HTTP server."""
    return g_help_string % (port)

def start_single_file_http_server(port, uncompressed_file, compressed_file):
    """Starts a HTTP server at given port, serving given file(s), returns running thread."""
    srv = create_single_file_http_server(port, uncompressed_file, compressed_file)
    thr = threading.Thread(target=async_serve_forever, args=(srv,))
    thr.start()
    return thr
