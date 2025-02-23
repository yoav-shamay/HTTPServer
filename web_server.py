import socket
import os
class BadRequest(Exception):
    pass

def retrieve_from_input_dictionary(dictionary, key):
    if key not in dictionary:
        raise BadRequest() #TODO info message
    return dictionary[key]

def trim_linear_whitespaces(string):
    '''
    Trims linear whitespaces from beginning and end of the string, to account for RFC 7230 3.2.3
    '''
    return string.strip(" \t")


def parse_header(header_line):
    header_splitter = header_line.find(':')
    if header_splitter == -1:
        raise BadRequest()
    header_value = trim_linear_whitespaces(header_line[header_splitter + 2:])
    return header_line[:header_splitter], header_value

class HttpRequest:
    def __init__(self, method, request_path, query_parameters, headers, body):
        self.__method = method
        self.__request_path = request_path
        self.__query_parameters = query_parameters
        self.__headers = headers
        self.__body = body
    def get_method(self):
        return self.__method
    def get_request_path(self):
        return self.__request_path
    def get_query_parameters(self):
        return self.__query_parameters
    def get_headers(self):
        return self.__headers
    def get_body(self):
        return self.__body

class HttpResponse:
    def __init__(self, status_code, status_message, headers, body):
        self.__status_code = status_code
        self.__status_message = status_message
        self.__headers = headers
        self.__body = body

        self.__headers["Content-Length"] = len(body) #TODO should this logic be here?
    
    def get_status_code(self):
        return self.__status_code
    
    def get_status_message(self):
        return self.__status_message
    
    def get_headers(self):
        return self.__headers
    
    def get_body(self):
        return self.__body

class ClientConnection:
    def __init__(self, sock):
        self.__socket = sock

    @staticmethod
    def parse_request_path(path):
        path_question_mark_index = path.find('?')
        if path_question_mark_index == -1: #no url parameters
            return (path, {})
        actual_path = path[:path_question_mark_index]
        parameters_string = path[path_question_mark_index + 1:]
        parameters_string_seperated = parameters_string.split('&')
        parameters = {}
        for parameter_string in parameters_string_seperated:
            equal_sign_index = parameter_string.find('=')
            if equal_sign_index == -1:
                key = parameter_string
                value = None
            else:
                key = parameter_string[:equal_sign_index]
                value = parameter_string[equal_sign_index + 1:]
            parameters[key] = value
        return (actual_path, parameters)
    

    def recieve_line(self):
        cur_text = ""
        while cur_text[-2:] != "\r\n":
            cur_text += self.__socket.recv(1).decode()
        return cur_text[:-2]

    def recieve_request(self):
        #handling first line of request: method and path
        first_line = self.recieve_line()
        first_line_splitted = first_line.split(' ')
        method = first_line_splitted[0]
        request_path = first_line_splitted[1]
        actual_path, query_parameters = ClientConnection.parse_request_path(request_path)
        #receive headers
        headers = {}
        cur_line = self.recieve_line()
        while cur_line != "":
            header, value = parse_header(cur_line)
            headers[header] = value
            cur_line = self.recieve_line()
        #receive content
        body = None
        if "Content-Length" in headers:
            length = int(headers["Content-Length"][0])
            body = self.__socket.receive(length)
        return HttpRequest(method, actual_path, query_parameters, headers, body)


    def send_response(self, response):
        #send first line
        first_line = f"HTTP/1.1 {response.get_status_code()} {response.get_status_message()}\r\n" #TODO HTTP/1.1 as constant?
        self.__socket.send(first_line.encode())
        headers = response.get_headers()
        for header, value in headers.items():
            header_line = f"{header}: {value}\r\n"
            self.__socket.send(header_line.encode())
        self.__socket.send(b"\r\n")
        self.__socket.send(response.get_body())


    def close(self):
        self.__socket.close()

class HttpServer: #TODO is this class neccessary?
    def __init__(self):
        self.__server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.__server_socket.bind(("localhost", 80)) #TODO make port a constant? make it a parameter?
        self.__server_socket.listen()
    def accept_client(self):
        client_socket, _ = self.__server_socket.accept()
        return ClientConnection(client_socket)
    #TODO add proper client handling inside the class?

def get_file_content(file_path):
    file = open(file_path, "rb")
    content = file.read()
    file.close()
    return content

def write_to_file(file_path, content):
    file = open(file_path, "wb")
    file.write(content)
    file.close()

def parse_header_value_parameters(header_value_str):
    value_parts = header_value_str.split(';')
    main_value = trim_linear_whitespaces(value_parts[0])
    parameters = {}
    for parameter_str in value_parts[1:]:
        parameter_str = trim_linear_whitespaces(parameter_str)
        name_value_splitter = parameter_str.find('=')
        name = parameter_str[:name_value_splitter]
        value = parameter_str[name_value_splitter + 1:]
        parameters[name] = value
    return main_value, parameters

def parse_form_data(request_body, request_headers):
    content_type_header = retrieve_from_input_dictionary(request_headers, "Content-Type")
    _, content_type_params = parse_header_value_parameters(content_type_header)
    boundary = retrieve_from_input_dictionary(content_type_params, "boundary")
    #remove first and last boundary
    request_body = request_body.removeprefix(f"{boundary}\r\n").removesuffix(f"\r\n{boundary}\r\n")
    #seperate headers and body
    headers_seperator = request_body.find("\r\n\r\n")
    if headers_seperator == -1:
        raise BadRequest() #TODO message?
    headers_str = request_body[:headers_seperator]
    content = request_body[headers_seperator + 4:]
    #parse headers
    headers_splitted = headers_str.split("\r\n")
    headers = {}
    for header_str in headers_splitted:
        header, value = parse_header(header_str)
        headers[header] = value
    return headers, content


CONTENT_TYPE_BY_EXTENSION = {"html":"text/html", "css": "text/css", "js": "application/javascript", "jpg": "image/jpeg",
                          "gif": "image/gif", "png": "image/png", "ico": "image/x-icon"}
PLAINTEXT_CONTENT_TYPE = "text/plain"
ROOT_DIRECTORY = "webroot"
UPLOADS_PATH = "/imgs"

def calculate_next(request):
    parameters = request.get_query_parameters()
    if "num" in parameters:
        num = int(parameters["num"]) #TODO check that represents number?
        result = num + 1
    else:
        result = 5 #TODO should I BadRequest()? otherwise make constant?
    response_body = str(result).encode()
    response_headers = {"Content-Type": PLAINTEXT_CONTENT_TYPE} #TODO constants
    return HttpResponse(200, "OK", response_headers, response_body)

def calculate_area(request):
    parameters = request.get_query_parameters()
    height = int(retrieve_from_input_dictionary(parameters, "height"))
    width = int(retrieve_from_input_dictionary(parameters, "width"))
    area = (height * width) / 2
    response_body = str(area).encode()
    response_headers = {"Content-Type": PLAINTEXT_CONTENT_TYPE} #TODO constants
    return HttpResponse(200, "OK", response_headers, response_body)


def upload(request : HttpRequest):
    #upload image from form-data
    form_data_headers, form_data_content = parse_form_data(request.get_body(), request.get_headers())
    content_disposition_header = retrieve_from_input_dictionary(form_data_headers, "Content-Disposition")
    _, content_disposition_params = parse_header_value_parameters(content_disposition_header)
    file_name = retrieve_from_input_dictionary(content_disposition_params, "filename")
    #TODO file name validation
    file_path = ROOT_DIRECTORY + UPLOADS_PATH + "/" + file_name
    write_to_file(file_path, form_data_content)
    return HttpResponse(200, "OK", {}, b"") #TODO add success message?

def get_image(request):
    #parameters: image-name
    #return the uploaded image, 404 if doesnt exist
    #TODO implement
    pass

def read_file(request_path):
    file_path = ROOT_DIRECTORY + request_path

    if os.path.exists(file_path): #TODO make sure no path traversal? http://stackoverflow.com/questions/45188708/how-to-prevent-directory-traversal-attack-from-python-code
        response_body = get_file_content(file_path)
        file_extension = file_path.split('.')[-1] #TODO check for existance
        response_headers = {"Content-Type": CONTENT_TYPE_BY_EXTENSION[file_extension]} #TODO check extension existance
        return HttpResponse(200, "OK", response_headers, response_body) #TODO constants for 200 and OK
    else:
        #TODO send 404
        print("404")
        pass

API_METHODS = {
    ("GET", "/calculate-next"): calculate_next,
    ("GET", "/calculate-area"): calculate_area,
    ("POST", "/upload"): upload,
    ("GET", "/image"): get_image
}

def main():
    server = HttpServer()
    while True:
        conn = server.accept_client() #Handle multiple requests
        try:
            request = conn.recieve_request()
            request_path = request.get_request_path()
            request_method = request.get_method()
            if (request_method, request_path) in API_METHODS:
                response = API_METHODS[(request_method, request_path)](request)
            else:
                response = read_file(request_path)
            conn.send_response(response)
        except BadRequest:
            #TODO support extra bad request info?
            #TODO send bad request
            pass
        except Exception as e:
            #TODO send internal server error
            print(e)
            pass
        conn.close()


if __name__ == "__main__":
    main()

'''
TODO 4.10, 4.11
TODO status codes as contants
TODO If string concat is quadratic move to list
TODO Add timeout
TODO Check permission to read from file
TODO Prevent directory traversal attack
TODO I need to handle invalid request format?
TODO Redirect to index.html by default?
TODO read 4.4 for extra guidelines
TODO handle url encoding of characters
TODO percent encoding in form-data
'''