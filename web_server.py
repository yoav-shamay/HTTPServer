import socket
import os


CONTENT_TYPE_BY_EXTENSION = {"html":"text/html", "css": "text/css", "js": "application/javascript", "jpg": "image/jpeg",
                          "gif": "image/gif", "png": "image/png", "ico": "image/x-icon"}
PLAINTEXT_CONTENT_TYPE = "text/plain"
CONTENT_TYPE_HEADER_NAME = "Content-Type" #TODO needs to be a constant?
ROOT_DIRECTORY = "webroot"
UPLOADS_PATH = "/imgs" #TODO change to saved_images? maybe do it differnt than ROOT?
#TODO \r\n as constnat?
HTTP_VERSION = "HTTP/1.1"

OK_STATUS_CODE = 200
BAD_REQUEST_STATUS_CODE = 400
NOT_FOUND_STATUS_CODE = 404
INTERNAL_SERVER_ERROR_STATUS_CODE = 500
#TODO status messages as constants

class BadRequest(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

def retrieve_from_input_dictionary(dictionary, key, error_message): #TODO do I need the message, make it generic somehow?
    if key not in dictionary:
        raise BadRequest(error_message)
    return dictionary[key]

def trim_linear_whitespaces(string):
    '''
    Trims linear whitespaces from beginning and end of the string, to account for RFC 7230 3.2.3
    '''
    return string.strip(" \t")

HEADER_VALUE_SEPERATOR = ':' #TODO needs to be a constant?

def parse_header(header_line):
    header_splitter = header_line.find(HEADER_VALUE_SEPERATOR)
    if header_splitter == -1:
        raise BadRequest("Missing colon in header")
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
            length = int(headers["Content-Length"])
            body = self.__socket.recv(length)
        return HttpRequest(method, actual_path, query_parameters, headers, body)


    def send_response(self, response):
        #send first line
        first_line = f"{HTTP_VERSION} {response.get_status_code()} {response.get_status_message()}\r\n" #TODO HTTP/1.1 as constant
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
    def __init__(self, host, port):
        self.__server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.__server_socket.bind((host, port))
        self.__server_socket.listen()
    def accept_client(self):
        client_socket, _ = self.__server_socket.accept()
        return ClientConnection(client_socket)
    #TODO add proper client handling inside the class? maybe submit request handler as function or something

def get_file_content(file_path):
    file = open(file_path, "rb")
    content = file.read()
    file.close()
    return content

def write_to_file(file_path, content):
    file = open(file_path, "wb")
    file.write(content)
    file.close()

PARAMETERS_SEPERATOR = ';'
PARAMETER_NAME_VALUE_SEPEATOR = '='

def parse_header_value_parameters(header_value_str): #TODO handle quoted values
    value_parts = header_value_str.split(PARAMETERS_SEPERATOR)
    main_value = trim_linear_whitespaces(value_parts[0])
    parameters = {}
    for parameter_str in value_parts[1:]:
        parameter_str = trim_linear_whitespaces(parameter_str)
        name_value_splitter = parameter_str.find(PARAMETER_NAME_VALUE_SEPEATOR)
        if name_value_splitter == -1:
            raise BadRequest("Invalid header parameter syntax")
        name = parameter_str[:name_value_splitter]
        value = parameter_str[name_value_splitter + 1:]
        parameters[name] = value
    return main_value, parameters

def parse_form_data(request_body, request_headers):
    content_type_header = retrieve_from_input_dictionary(request_headers, CONTENT_TYPE_HEADER_NAME, "Missing Content-Type header")
    _, content_type_params = parse_header_value_parameters(content_type_header)
    boundary = retrieve_from_input_dictionary(content_type_params, "boundary", "Missing boundary in Content-Type header")
    #remove first and last boundary
    print(boundary)
    prefix = f"--{boundary}\r\n"
    suffix = f"\r\n--{boundary}--\r\n"
    request_body = request_body.removeprefix(prefix.encode()).removesuffix(suffix.encode())
    #seperate headers and body
    print(request_body)
    headers_body_seperator = request_body.find(b"\r\n\r\n")
    if headers_body_seperator == -1:
        raise BadRequest("Invalid body structure")
    headers_str = request_body[:headers_body_seperator]
    content = request_body[headers_body_seperator + 4:]
    #parse headers
    headers_splitted = headers_str.split(b"\r\n")
    headers = {}
    for header_str in headers_splitted:
        header, value = parse_header(header_str.decode())
        headers[header] = value
    return headers, content



def calculate_next(request):
    parameters = request.get_query_parameters()
    if "num" in parameters:
        num = int(parameters["num"]) #TODO check that represents number?
        result = num + 1
    else:
        result = 5 #TODO should I BadRequest()? otherwise make constant?
    response_body = str(result).encode()
    response_headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE} #TODO constants
    return HttpResponse(OK_STATUS_CODE, "OK", response_headers, response_body)

def calculate_area(request):
    parameters = request.get_query_parameters()
    height = int(retrieve_from_input_dictionary(parameters, "height", "Missing height")) #TODO try parse int
    width = int(retrieve_from_input_dictionary(parameters, "width", "Missing width"))
    area = (height * width) / 2
    response_body = str(area).encode()
    response_headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(OK_STATUS_CODE, "OK", response_headers, response_body)

FILENAME_FORBIDDEN_CHARACTERS = "/\\?*:|\"<>"
FORBIDDEN_LAST_FILENAME_CHARACTERS = ". "
def is_valid_filename(name): #TODO add more checks?
    if any(char in FILENAME_FORBIDDEN_CHARACTERS for char in name):
        return False
    if name[-1] in FORBIDDEN_LAST_FILENAME_CHARACTERS:
        return False
    return True
    
def upload(request : HttpRequest):
    #upload image from form-data
    form_data_headers, form_data_content = parse_form_data(request.get_body(), request.get_headers())
    content_disposition_header = retrieve_from_input_dictionary(form_data_headers, "Content-Disposition", "Missing Content-Disposition header in request body")
    _, content_disposition_params = parse_header_value_parameters(content_disposition_header)
    file_name = retrieve_from_input_dictionary(content_disposition_params, "filename", "Missing filename in Content-Disposition header in request body")
    if not is_valid_filename(file_name):
        raise BadRequest("Invalid filename")
    file_path = ROOT_DIRECTORY + UPLOADS_PATH + "/" + file_name
    write_to_file(file_path, form_data_content)
    return HttpResponse(OK_STATUS_CODE, "OK", {}, b"") #TODO add success message? switch to no response status code?

def get_image(request):
    #parameters: image-name
    #return the uploaded image, 404 if doesnt exist
    image_name = retrieve_from_input_dictionary(request.get_query_parameters(), "image-name", "Missing image-name parameter")
    image_path = ROOT_DIRECTORY + UPLOADS_PATH + "/" + image_name
    if os.path.exists(image_path):
        image_content = read_file(image_path)
        image_extension_seperator = image_name.rfind(".")
        if image_extension_seperator != -1:
            extension = image_name[image_extension_seperator + 1]
            content_type = CONTENT_TYPE_BY_EXTENSION[extension]
        else:
            content_type = PLAINTEXT_CONTENT_TYPE
        headers = {CONTENT_TYPE_HEADER_NAME: content_type}
        return HttpResponse(OK_STATUS_CODE, "OK", headers, image_content)
    else:
        headers = {}
        return HttpResponse(NOT_FOUND_STATUS_CODE, "Not Found", headers, b"") #TODO add message?

def read_file(request_path):
    file_path = ROOT_DIRECTORY + request_path

    if os.path.exists(file_path): #TODO make sure no path traversal? http://stackoverflow.com/questions/45188708/how-to-prevent-directory-traversal-attack-from-python-code
        response_body = get_file_content(file_path)
        file_extension = file_path.split('.')[-1] #TODO check for existance
        response_headers = {CONTENT_TYPE_HEADER_NAME: CONTENT_TYPE_BY_EXTENSION[file_extension]} #TODO check extension existance
        return HttpResponse(OK_STATUS_CODE, "OK", response_headers, response_body) #TODO constants for 200 and OK
    else:
        headers = {}
        return HttpResponse(NOT_FOUND_STATUS_CODE, "Not Found", headers, b"") #TODO add message?

API_METHODS = {
    ("GET", "/calculate-next"): calculate_next,
    ("GET", "/calculate-area"): calculate_area,
    ("POST", "/upload"): upload,
    ("GET", "/image"): get_image
}

def main():
    server = HttpServer("localhost", 80)
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
        except BadRequest as e:
            body = e.message.encode()
            headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE}
            response = HttpResponse(BAD_REQUEST_STATUS_CODE, "Bad Request", headers, body)
            conn.send_response(response)
        except Exception as e:
            print(e)
            headers = {}
            response = HttpResponse(INTERNAL_SERVER_ERROR_STATUS_CODE, "Internal Server Error", headers, b"")
            conn.send_response(response)
        conn.close()


if __name__ == "__main__":
    main()

'''
TODO status codes as contants
TODO If string concat is quadratic move to list
TODO Add timeout
TODO Check permission to read from file?
TODO Prevent directory traversal attack
TODO I need to handle invalid request format?
TODO Redirect to index.html by default?
TODO read 4.4 for extra guidelines
TODO handle url encoding of characters
TODO percent encoding in form-data
TODO header name cant contain percent encoding but header value can
TODO parameter value encoding https://datatracker.ietf.org/doc/html/rfc5987
'''