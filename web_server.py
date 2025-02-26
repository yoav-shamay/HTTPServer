import socket
import os


CONTENT_TYPE_BY_EXTENSION = {"html":"text/html", "css": "text/css", "js": "application/javascript", "jpg": "image/jpeg",
                          "gif": "image/gif", "png": "image/png", "ico": "image/x-icon"}
PLAINTEXT_CONTENT_TYPE = "text/plain"
HTTP_VERSION = "HTTP/1.1"

OK_STATUS_CODE = 200
OK_STATUS_MESSAGE = "OK" #TODO merge both status code and status message to a single string
CREATED_STATUS_CODE = 201
CREATED_STATUS_MESSAGE = "Created"
BAD_REQUEST_STATUS_CODE = 400
BAD_REQUEST_STATUS_MESSAGE = "Bad Request"
FORBIDDEN_STATUS_CODE = 403
FORBIDDEN_STATUS_MESSAGE = "Forbidden"
NOT_FOUND_STATUS_CODE = 404
NOT_FOUND_STATUS_MESSAGE = "Not Found"
REQUEST_TIMEOUT_STATUS_CODE = 408
REQUEST_TIMEOUT_STATUS_MESSAGE = "Request Timeout"
INTERNAL_SERVER_ERROR_STATUS_CODE = 500
INTERNAL_SERVER_ERROR_STATUS_MESSAGE = "Internal Server Error"

CONTENT_TYPE_HEADER_NAME = "Content-Type" #TODO needs to be a constant? if so so other things too?

class BadRequest(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

def try_retrieve_from_dictionary(dictionary, key, error_message): #TODO do I need the message, make it generic somehow?
    if key not in dictionary:
        raise BadRequest(error_message)
    return dictionary[key]

def try_parse_int(num, error_message):
    try:
        return int(num)
    except:
        raise BadRequest(error_message)

def trim_linear_whitespaces(string):
    '''
    Trims linear whitespaces from beginning and end of the string, to account for RFC 7230 3.2.3
    '''
    return string.strip(" \t")

def parse_header(header_line):
    header_splitter = header_line.find(':')
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
    def parse_request_path(path): #TODO should this just be global instead?
        path_question_mark_index = path.find('?')
        if path_question_mark_index == -1: #no url parameters
            return (path, {})
        actual_path = path[:path_question_mark_index] #before the question mark
        parameters_string = path[path_question_mark_index + 1:] #after the question mark
        parameters_string_seperated = parameters_string.split('&')
        parameters = {}
        for parameter_string in parameters_string_seperated:
            equal_sign_index = parameter_string.find('=')
            if equal_sign_index == -1: #no value
                key = parameter_string
                value = None
            else:
                key = parameter_string[:equal_sign_index]
                value = parameter_string[equal_sign_index + 1:]
            parameters[key] = value
        return (actual_path, parameters)
    

    def recieve_line(self):
        cur_text = []
        while cur_text[-2:] != ["\r", "\n"]: #recieve another character until meeting \r\n
            cur_text += self.__socket.recv(1).decode()
        cur_text = cur_text[:-2] #remove \r\n in the end
        return ''.join(cur_text)

    def recieve_request(self):
        #handling first line of request: method and path
        first_line = self.recieve_line()
        first_line_splitted = first_line.split(' ')
        if len(first_line_splitted) < 2:
            raise BadRequest("Invalid first request line")
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
            length = try_parse_int(headers["Content-Length"], "Content-Length isn't integer")
            body = self.__socket.recv(length)
        return HttpRequest(method, actual_path, query_parameters, headers, body)


    def send_response(self, response):
        #send first line
        first_line = f"{HTTP_VERSION} {response.get_status_code()} {response.get_status_message()}\r\n"
        self.__socket.send(first_line.encode())
        headers = response.get_headers()
        for header, value in headers.items():
            header_line = f"{header}: {value}\r\n"
            self.__socket.send(header_line.encode())
        self.__socket.send(b"\r\n")
        self.__socket.send(response.get_body())


    def close(self):
        self.__socket.close()

class HttpServer: #TODO is this class necessary?
    def __init__(self, host, port, client_timeout):
        self.__server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.__server_socket.bind((host, port))
        self.__server_socket.listen()
        self.client_timeout = client_timeout
    def accept_client(self):
        client_socket, _ = self.__server_socket.accept()
        client_socket.settimeout(self.client_timeout)
        return ClientConnection(client_socket)

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
        if name_value_splitter == -1:
            raise BadRequest("Invalid header parameter syntax")
        name = parameter_str[:name_value_splitter]
        value = parameter_str[name_value_splitter + 1:]
        if value[0] == "\"": #value is quoted-string
            value = value.removeprefix("\"").removesuffix("\"") #remove start and end quotes
            #Handle escaping. the rule is to replace \<char> with <char>.
            value_after_escaping = ""
            i = 0
            while i < len(value):
                if value[i] == '\\':
                    if i == (len(value) - 1):
                        raise BadRequest("Invalid backslash at the end of string")
                    value_after_escaping += value[i + 1]
                    i += 2
                else:
                    value_after_escaping += value[i]
                    i += 1
            value = value_after_escaping
        parameters[name] = value
    return main_value, parameters

def parse_form_data(request_body, request_headers):
    content_type_header = try_retrieve_from_dictionary(request_headers, CONTENT_TYPE_HEADER_NAME, "Missing Content-Type header")
    _, content_type_params = parse_header_value_parameters(content_type_header)
    boundary = try_retrieve_from_dictionary(content_type_params, "boundary", "Missing boundary in Content-Type header")
    #remove first and last boundary
    prefix = f"--{boundary}\r\n"
    suffix = f"\r\n--{boundary}--\r\n"
    request_body = request_body.removeprefix(prefix.encode()).removesuffix(suffix.encode())
    #seperate headers and body
    headers_body_seperator_pos = request_body.find(b"\r\n\r\n")
    if headers_body_seperator_pos == -1:
        raise BadRequest("Invalid body structure")
    headers_str = request_body[:headers_body_seperator_pos]
    content = request_body[headers_body_seperator_pos + 4:]
    #parse headers
    headers_splitted = headers_str.split(b"\r\n")
    headers = {}
    for header_str in headers_splitted:
        header, value = parse_header(header_str.decode())
        headers[header] = value
    return headers, content

ROOT_DIRECTORY = "webroot"
UPLOADS_PATH = "/uploaded_imgs" #TODO should it be /imgs?

def calculate_next(request):
    parameters = request.get_query_parameters()
    if "num" in parameters:
        num = try_parse_int(parameters["num"], "num isn't integer")
        result = num + 1
    else:
        result = 5 #TODO should I BadRequest()? otherwise make constant?
    response_body = str(result).encode()
    response_headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(OK_STATUS_CODE, OK_STATUS_MESSAGE, response_headers, response_body)

def calculate_area(request):
    parameters = request.get_query_parameters()
    height_str = try_retrieve_from_dictionary(parameters, "height", "Missing height")
    height = try_parse_int(height_str, "height isn't integer")
    width_str = try_retrieve_from_dictionary(parameters, "width", "Missing width")
    width = try_parse_int(width_str, "width isn't integer")
    area = (height * width) / 2
    response_body = str(area).encode()
    response_headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(OK_STATUS_CODE, OK_STATUS_MESSAGE, response_headers, response_body)

FILENAME_FORBIDDEN_CHARACTERS = "/\\?*:|\"<>"
FORBIDDEN_LAST_FILENAME_CHARACTERS = ". "
def is_valid_filename(name):
    if any(char in FILENAME_FORBIDDEN_CHARACTERS for char in name): # check if any character in the file name is forbidden
        return False
    if name[-1] in FORBIDDEN_LAST_FILENAME_CHARACTERS:  #file name can't end with dot or space
        return False
    if len(name) == 0: #empty string isn't valid file name
        return False
    return True
    
def upload(request : HttpRequest):
    #upload image from form-data
    form_data_headers, form_data_content = parse_form_data(request.get_body(), request.get_headers())
    content_disposition_header = try_retrieve_from_dictionary(form_data_headers, "Content-Disposition", "Missing Content-Disposition header in request body")
    _, content_disposition_params = parse_header_value_parameters(content_disposition_header)
    file_name = try_retrieve_from_dictionary(content_disposition_params, "filename", "Missing filename in Content-Disposition header in request body")
    if not is_valid_filename(file_name):
        raise BadRequest("Invalid filename")
    file_path = ROOT_DIRECTORY + UPLOADS_PATH + "/" + file_name
    write_to_file(file_path, form_data_content)
    headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(CREATED_STATUS_CODE, CREATED_STATUS_MESSAGE, headers, b"Upload Sucessful")

def get_content_type(file_name):
    extension_seperator = file_name.rfind(".")
    if extension_seperator != -1:
        extension = file_name[extension_seperator + 1:]
        if extension in CONTENT_TYPE_BY_EXTENSION:
            return CONTENT_TYPE_BY_EXTENSION[extension]
    return PLAINTEXT_CONTENT_TYPE

def get_image(request):
    #parameters: image-name
    #return the uploaded image, 404 if doesnt exist
    image_name = try_retrieve_from_dictionary(request.get_query_parameters(), "image-name", "Missing image-name parameter")
    if not is_valid_filename(image_name):
        raise BadRequest("Invalid image name")
    image_path = ROOT_DIRECTORY + UPLOADS_PATH + "/" + image_name
    if os.path.exists(image_path):
        image_content = get_file_content(image_path)
        headers = {CONTENT_TYPE_HEADER_NAME: get_content_type(image_name)}
        return HttpResponse(OK_STATUS_CODE, OK_STATUS_MESSAGE, headers, image_content)
    else:
        headers = {}
        return HttpResponse(NOT_FOUND_STATUS_CODE, NOT_FOUND_STATUS_MESSAGE, headers, b"")

def get_file(request_path):
    file_path = ROOT_DIRECTORY + request_path
    # test if there's a directory traversal attempt
    root_directory_absolute_path = os.path.abspath(ROOT_DIRECTORY + "/")
    request_absolute_path = os.path.abspath(file_path)
     #If the abs path of the request doesn't start with the abs path of the root directory, the request asks for a resource outside of it
    if os.path.commonprefix([root_directory_absolute_path, request_absolute_path]) != root_directory_absolute_path:
        return HttpResponse(FORBIDDEN_STATUS_CODE, FORBIDDEN_STATUS_MESSAGE, {}, b"") #Return Forbidden HTTP response
    if os.path.isdir(file_path): #If the user asks for a directory, also return Forbidden
        return HttpResponse(FORBIDDEN_STATUS_CODE, FORBIDDEN_STATUS_MESSAGE, {}, b"")
    if os.path.exists(file_path):
        response_body = get_file_content(file_path)
        response_headers = {CONTENT_TYPE_HEADER_NAME: get_content_type(file_path)}
        return HttpResponse(OK_STATUS_CODE, OK_STATUS_MESSAGE, response_headers, response_body)
    else:
        headers = {}
        return HttpResponse(NOT_FOUND_STATUS_CODE, NOT_FOUND_STATUS_MESSAGE, headers, b"")

API_METHODS = {
    ("GET", "/calculate-next"): calculate_next,
    ("GET", "/calculate-area"): calculate_area,
    ("POST", "/upload"): upload,
    ("GET", "/image"): get_image
}

ADDRESS = "localhost"
PORT = 80
CLIENT_TIMEOUT = 2

def main():
    server = HttpServer(ADDRESS, PORT, CLIENT_TIMEOUT)
    while True:
        conn = server.accept_client() #TODO handle multiple requests?
        try:
            request = conn.recieve_request()
            request_path = request.get_request_path()
            request_method = request.get_method()
            if (request_method, request_path) in API_METHODS:
                response = API_METHODS[(request_method, request_path)](request)
            else:
                response = get_file(request_path)
            conn.send_response(response)
        except socket.timeout: #In case of timeout when recieving the request, send a Request Timeout response
            response_headers = {"Connection": "close"} #Signal to close the connection, as mentioned in rfc 7231 6.5.7
            response = HttpResponse(REQUEST_TIMEOUT_STATUS_CODE, REQUEST_TIMEOUT_STATUS_MESSAGE, response_headers, b"")
            conn.send_response(response)
        except BadRequest as e: #In the case of a bad request exception (raised when the request is invalid), send bad request response with the error message
            body = e.message.encode()
            headers = {CONTENT_TYPE_HEADER_NAME: PLAINTEXT_CONTENT_TYPE}
            response = HttpResponse(BAD_REQUEST_STATUS_CODE, BAD_REQUEST_STATUS_MESSAGE, headers, body)
            conn.send_response(response)
        except Exception as e: #In case there was some error during the processing of the request
            print(e) #TODO remove this and also "as e"
            response = HttpResponse(INTERNAL_SERVER_ERROR_STATUS_CODE, INTERNAL_SERVER_ERROR_STATUS_MESSAGE, {}, b"")
            conn.send_response(response) #return Internal Server Error response
        print("Finished processing request") #TODO remove
        conn.close()


if __name__ == "__main__":
    main()

'''
TODO all errors testing. tested: timeout, invalid request first line, directory traversal, directory access
TODO Redirect to index.html by default?
TODO read 4.4 for extra guidelines
TODO handle url encoding of characters
TODO percent encoding in form-data
TODO header name cant contain percent encoding but header value can
TODO parameter value encoding https://datatracker.ietf.org/doc/html/rfc5987
TODO find out why upload doesn't work some of the time randomly
TODO documentation and comments
TODO height, width, num as floats?
'''