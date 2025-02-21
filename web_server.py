import socket
import os

class HttpRequest:
    def __init__(self, method, requestPath, headers, body):
        self.__method = method
        self.__requestPath = requestPath
        self.__headers = headers
        self.__body = body
    def getMethod(self):
        return self.__method
    def getRequestPath(self):
        return self.__requestPath
    def getHeaders(self):
        return self.__headers
    def getBody(self):
        return self.__body

class HttpResponse:
    def __init__(self, statusCode, statusMessage, headers, body):
        self.__statusCode = statusCode
        self.__statusMessage = statusMessage
        self.__headers = headers
        self.__body = body
    
    def getStatusCode(self):
        return self.__statusCode
    
    def getStatusMessage(self):
        return self.__statusMessage
    
    def getHeaders(self):
        return self.__headers
    
    def getBody(self):
        return self.__body

class ClientConnection:
    def __init__(self, sock):
        self.sock = sock


    def recieve_line(self):
        cur_text = ""
        while cur_text[-2:] != "\r\n":
            cur_text += self.sock.recv(1).decode()
        return cur_text[:-2]
    def parse_header(self, header_line): #TODO make static
        header_splitted = header_line.split(': ')
        return header_splitted[0], header_splitted[1]
    

    def recieve_request(self):
        #handling first line of request: method and path
        first_line = self.recieve_line()
        first_line_splitted = first_line.split(' ')
        method = first_line_splitted[0]
        path = first_line_splitted[1]
        #receive headers
        headers = {}
        cur_line = self.recieve_line()
        while cur_line != "":
            header, value = self.parse_header(cur_line)
            headers[header] = value
            cur_line = self.recieve_line()
        #receive content
        body = None
        if "Content-Length" in headers:
            body = self.sock.receive(headers["Content-Length"])
        return HttpRequest(method, path, headers, body)


    def send_response(self, response):
        #send first line
        first_line = f"HTTP/1.1 {response.getStatusCode()} {response.getStatusMessage()}\r\n"
        self.sock.send(first_line.encode())
        headers = response.getHeaders()
        for header, value in headers.items():
            header_line = f"{header}: {value}\r\n"
            self.sock.send(header_line.encode())
        self.sock.send(b"\r\n")
        self.sock.send(response.getBody())


    def close(self):
        self.sock.close()

class HttpServer: #TODO is this class neccessary?
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.server_socket.bind(("localhost", 80))
        self.server_socket.listen()
    def accept_client(self):
        client_socket, address = self.server_socket.accept()
        return ClientConnection(client_socket)
    #TODO add proper client handling inside the class?

def get_file_content(file_path):
    file = open(file_path, "rb")
    content = file.read()
    file.close()
    return content

EXTENSION_CONTENT_TYPE = {"html":"text/html", "css": "text/css", "js": "application/javascript", "jpg": "image/jpeg", "image/gif": "gif", "image/png": "png"}
#TODO add .ico

def main():
    server = HttpServer()
    while True:
        conn = server.accept_client() #Handle multiple requests?
        request = conn.recieve_request()
        file_path = "webroot" + request.getRequestPath()
        if os.path.exists(file_path): #TODO make sure no path traversal? or should I just ignore the vulnerability? http://stackoverflow.com/questions/45188708/how-to-prevent-directory-traversal-attack-from-python-code
            response_body = get_file_content(file_path)
            file_extension = file_path.split('.')[-1]
            response_headers = {"Content-Type": EXTENSION_CONTENT_TYPE[file_extension], "Content-Length": len(response_body)}
            response = HttpResponse(200, "OK", response_headers, response_body)
            conn.send_response(response)
        else:
            #TODO send 404
            
            pass
        conn.close()


if __name__ == "__main__":
    main()