import socket
import os


CONTENT_TYPE_BY_EXTENSION = {"html": "text/html", "css": "text/css", "js": "application/javascript", "jpg": "image/jpeg",
                             "gif": "image/gif", "png": "image/png", "ico": "image/x-icon"}
PLAINTEXT_CONTENT_TYPE = "text/plain"
HTTP_VERSION = "HTTP/1.1"

OK_STATUS_CODE = 200
OK_REASON_PHRASE = "OK"
CREATED_STATUS_CODE = 201
CREATED_REASON_PHRASE = "Created"
BAD_REQUEST_STATUS_CODE = 400
BAD_REQUEST_REASON_PHRASE = "Bad Request"
FORBIDDEN_STATUS_CODE = 403
FORBIDDEN_REASON_PHRASE = "Forbidden"
NOT_FOUND_STATUS_CODE = 404
NOT_FOUND_REASON_PHRASE = "Not Found"
REQUEST_TIMEOUT_STATUS_CODE = 408
REQUEST_TIMEOUT_REASON_PHRASE = "Request Timeout"
INTERNAL_SERVER_ERROR_STATUS_CODE = 500
INTERNAL_SERVER_ERROR_REASON_PHRASE = "Internal Server Error"


class BadRequest(Exception):
    """
    This class is an exception that will be thrown when the request is in invalid format.
    The server should return the 400 Bad Request response with the given message.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def try_retrieve_from_dictionary(dictionary: dict, key, error_message: str):
    """
    Returns dictionary[key] if key is in dictionary, and raises BadRequest with the given error_message otherwise.
    """
    if key not in dictionary:
        raise BadRequest(error_message)
    return dictionary[key]


def try_parse_int(num: str, error_message: str) -> int:
    """
    Gets num - a string that should represent number.
    Returns int(num) if num really represents an integer and raises BadRequest with the given error_message otherwise.
    """
    try:
        return int(num)
    except:
        raise BadRequest(error_message)


def trim_linear_whitespaces(string: str) -> str:
    '''
    Trims linear whitespaces from beginning and end of the string, to account for RFC 7230 3.2.3 OWS.
    '''
    return string.strip(" \t")


def parse_header(header_line: str) -> tuple[str, str]:
    """
    Gets a header line and splits it to the header name and value.
    Returns a pair of header name, header value
    """
    header_splitter = header_line.find(':')
    if header_splitter == -1:
        raise BadRequest("Missing colon in header")
    header_value = trim_linear_whitespaces(header_line[header_splitter + 2:])
    return header_line[:header_splitter], header_value


def parse_request_path(path: str) -> tuple[str, dict[str, str]]:
    """
    This methods parses a request url, giving the actual url and the query parameters.
    It gets a full query url (path), and returns a pair of actual url and a dictionary containing the query parameters.
    Each entry in the dictionary has the parameter name as the key and the parameter value as value (None if no value).
    """
    path_question_mark_index = path.find('?')
    if path_question_mark_index == -1:  # no url parameters
        return (path, {})
    # before the question mark
    actual_path = path[:path_question_mark_index]
    # after the question mark
    parameters_string = path[path_question_mark_index + 1:]
    parameters_string_seperated = parameters_string.split('&')
    parameters = {}
    for parameter_string in parameters_string_seperated:
        equal_sign_index = parameter_string.find(
            '=')  # seperates name and value
        if equal_sign_index == -1:  # no value
            key = parameter_string
            value = None
        else:
            # before equal sign - name
            key = parameter_string[:equal_sign_index]
            # after equal sign - value
            value = parameter_string[equal_sign_index + 1:]
        parameters[key] = value
    return (actual_path, parameters)


class HttpRequest:
    """
    This class represents a HTTP request the server recieves.
    It has:
    method - string of the request method (GET/POST)
    request_path - the requested path as string
    query_parameters - a dictionary of the query parameters (key - header name (string), value - header value (string))
    headers - a dictionary of the request headers.
    The key is header name (string), the value is header value (string)
    body - a byte string of the request body.
    """

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
    """
    This class represents a HTTP Response the server sends.
    It has:
    status_code - response status code as int, for example 200 or 404
    reason_phrase - response reason phrase as string, for example OK or Not Found
    headers - a dictionary of the response headers.
    The key is header name (string), the value is header value (string)
    body - a byte string of the request body.
    """

    def __init__(self, status_code, reason_phrase, headers, body):
        self.__status_code = status_code
        self.__reason_phrase = reason_phrase
        self.__headers = headers
        self.__body = body

        # Add the Content-Length header to match the body
        self.__headers["Content-Length"] = len(body)

    def get_status_code(self):
        return self.__status_code

    def get_reason_phrase(self):
        return self.__reason_phrase

    def get_headers(self):
        return self.__headers

    def get_body(self):
        return self.__body


class ClientConnection:
    """
    This class represents an interaction with a specific HTTP client.
    It handles the protocol itself.
    It allows to recieve a HttpRequest instance and send a HttpResponse instance.
    """

    def __init__(self, sock):
        self.__socket = sock

    def recieve_line(self) -> str:
        """
        Recieves a single line, which means all characters until \r\n.
        Returns the line recieved.
        """
        cur_text = []
        while cur_text[-2:] != ["\r", "\n"]:  # recieve another character until meeting \r\n
            cur_text.append(self.__socket.recv(1).decode())
        cur_text = cur_text[:-2]  # remove \r\n in the end
        return ''.join(cur_text)

    def recieve_request(self) -> HttpRequest:
        """
        Recieves a request from the client.
        Parses the request and returns it as a HttpRequest instance.
        """
        # handling first line of request: method and path
        first_line = self.recieve_line()
        first_line_splitted = first_line.split(' ')
        if len(first_line_splitted) < 2:  # not enough elements in the first line
            raise BadRequest("Invalid first request line")
        method = first_line_splitted[0]
        request_path = first_line_splitted[1]
        # parse the request path to actual path and query parameters
        actual_path, query_parameters = parse_request_path(request_path)
        # receive headers
        headers = {}
        cur_line = self.recieve_line()  # start by reading the next line
        while cur_line != "":  # continue until \r\n\r\n (empty line)
            # parse the current line as header
            header, value = parse_header(cur_line)
            headers[header] = value
            cur_line = self.recieve_line()  # read the next line
        # receive content
        body = None  # start by body as None in case of no body
        if "Content-Length" in headers:  # if there's a content-length header, there is a request body
            # try to parse content-length as int
            length = try_parse_int(
                headers["Content-Length"], "Content-Length isn't integer")
            # recieve the value of bytes mentioned in content-length
            body = self.__socket.recv(length)
        return HttpRequest(method, actual_path, query_parameters, headers, body)

    def send_response(self, response: HttpResponse):
        """
        This method sends a HTTP response for the client.
        It gets the response as HttpResponse object and sends it according to the protocol.
        """
        # send first line
        first_line = f"{HTTP_VERSION} {response.get_status_code()} {response.get_reason_phrase()}\r\n"
        self.__socket.send(first_line.encode())
        # send the headers
        headers = response.get_headers()
        for header, value in headers.items():
            header_line = f"{header}: {value}\r\n"
            self.__socket.send(header_line.encode())
        # send the body
        # additional \r\n (empty line) to seperate the body
        self.__socket.send(b"\r\n")
        self.__socket.send(response.get_body())

    def close(self):
        self.__socket.close()


class HttpServer:
    """
    This class represents a HTTP Server.
    It maintains a server socket, and allows to accept a client (and returns it as a ClientConnection object)
    Gets host address, port and timeout for clients as parameters.
    """

    def __init__(self, host: str, port: int, client_timeout: float):
        self.__server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # create the server socket
        # bind to the given host and port
        self.__server_socket.bind((host, port))
        self.__server_socket.listen()  # start listening for clients
        self.client_timeout = client_timeout

    def accept_client(self) -> ClientConnection:
        """
        Accepts a client and returns ClientConnection object to allow interaction with it.
        """
        client_socket, _ = self.__server_socket.accept()
        client_socket.settimeout(self.client_timeout)
        return ClientConnection(client_socket)


def get_file_content(file_path: str) -> bytes:
    """
    This method reads the file in file_path and returns its contents as byte string
    """
    file = open(file_path, "rb")
    content = file.read()
    file.close()
    return content


def write_to_file(file_path: str, content: bytes):
    """
    This method writes a byte-string content to the file in file_path
    """
    file = open(file_path, "wb")
    file.write(content)
    file.close()


def parse_header_value_parameters(header_value_str: str) -> tuple[str, dict[str, str]]:
    """
    This method parses parameters given in header values.
    It gets a string of the unparsed header value, and seperates it to the main value and a dictionary of parameters.
    Each entry has the parameter name (string) as key and parameter value (string) as value.
    Returns a pair of the main value (string) and parameters (dictionary)
    """
    value_parts = header_value_str.split(';')
    # the first value is the main value, before any semicolon
    main_value = trim_linear_whitespaces(value_parts[0])
    parameters = {}
    for parameter_str in value_parts[1:]:
        # trim spaces in the beginning and the end of the value
        parameter_str = trim_linear_whitespaces(parameter_str)
        # find the seperator between the name and value
        name_value_splitter = parameter_str.find('=')
        if name_value_splitter == -1:  # in case it doesn't exist, raise BadRequest
            raise BadRequest("Invalid header parameter syntax")
        name = parameter_str[:name_value_splitter]  # before the equal sign
        value = parameter_str[name_value_splitter + 1:]  # after the equal sign
        if value[0] == "\"":  # if value is a quoted-string, remove the quotes and unescape
            value = value.removeprefix("\"").removesuffix(
                "\"")  # remove start and end quotes
            # Handle escaping. the rule is to replace \<char> with <char>.
            value_after_escaping = ""
            i = 0
            while i < len(value):  # iterate over the string
                if value[i] == '\\':  # if metting a backslash add only the next character and skip it
                    # there can't be a backslash at the end of the string because it escapes nothing.
                    if i == (len(value) - 1):
                        raise BadRequest(
                            "Invalid backslash at the end of string")
                    value_after_escaping += value[i + 1]
                    i += 2
                else:  # otherwise add the current one normally
                    value_after_escaping += value[i]
                    i += 1
            value = value_after_escaping
        parameters[name] = value
    return main_value, parameters


def parse_form_data(request_body: bytes, request_headers: dict[str, str]) -> tuple[dict[str, str], bytes]:
    """
    This method parses a single form data instance from a request headers and body.
    It retrieves the headers and the actual body.
    It returns the headers as a dictionary.
    Each entry has the header name (string) as key and header value (string) as value.
    The body is returned as a byte string.
    It returns a pair of (headers, body).
    """
    if request_body is None:  # verify that there is a request body.
        raise BadRequest("Missing request body")
    # extract the boundary from the content-type header as parameter
    content_type_header = try_retrieve_from_dictionary(
        request_headers, "Content-Type", "Missing Content-Type header")
    _, content_type_params = parse_header_value_parameters(content_type_header)
    boundary = try_retrieve_from_dictionary(
        content_type_params, "boundary", "Missing boundary in Content-Type header")
    # remove first and last boundary
    prefix = f"--{boundary}\r\n"
    suffix = f"\r\n--{boundary}--\r\n"
    request_body = request_body.removeprefix(
        prefix.encode()).removesuffix(suffix.encode())
    # seperate headers and body
    # the seperator is an empty line, which means \r\n\r\n
    headers_body_seperator_pos = request_body.find(b"\r\n\r\n")
    if headers_body_seperator_pos == -1:
        raise BadRequest("Invalid body structure")
    # before the seperator
    headers_str = request_body[:headers_body_seperator_pos]
    # after the seperator (of length 4)
    content = request_body[headers_body_seperator_pos + 4:]
    # parse headers
    headers_splitted = headers_str.split(b"\r\n")
    headers = {}
    for header_str in headers_splitted:
        header, value = parse_header(header_str.decode())
        headers[header] = value
    return headers, content


ROOT_DIRECTORY = "webroot"
UPLOADS_PATH = "/uploaded_imgs"


def calculate_next(request: HttpRequest) -> HttpResponse:
    """
    Used for the /calculate-next endpoint.
    Gets a HttpRequest, gets an integer num as a query parameter.
    Returns num + 1 (as a HttpResponse)
    """
    parameters = request.get_query_parameters()
    num_str = try_retrieve_from_dictionary(
        parameters, "num", "Missing num")  # get num from the query parameters
    num = try_parse_int(num_str, "num isn't integer")  # convert it to int
    response_body = str(num + 1).encode()
    response_headers = {"Content-Type": PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(OK_STATUS_CODE, OK_REASON_PHRASE, response_headers, response_body)


def calculate_area(request: HttpRequest) -> HttpResponse:
    """
    Used for the /calculate-area endpoint.
    Gets a HttpRequest, gets integers height and width as query parameters.
    Returns the area of a triangle with the given height and width (in a HttpRespones).
    That is, height * width / 2
    """
    parameters = request.get_query_parameters()
    height_str = try_retrieve_from_dictionary(
        parameters, "height", "Missing height")
    height = try_parse_int(height_str, "height isn't integer")
    width_str = try_retrieve_from_dictionary(
        parameters, "width", "Missing width")
    width = try_parse_int(width_str, "width isn't integer")
    area = (height * width) / 2  # calculate the area
    response_body = str(area).encode()
    response_headers = {"Content-Type": PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(OK_STATUS_CODE, OK_REASON_PHRASE, response_headers, response_body)


FILENAME_FORBIDDEN_CHARACTERS = "/\\?*:|\"<>"
FORBIDDEN_LAST_FILENAME_CHARACTERS = ". "


def is_valid_filename(name: str) -> bool:
    """
    This method checks if a given file name is valid, if the string can be used as the name of a file (in windows).
    Returns true if the file name is valid or false otherwise
    """
    # check if any character in the file name is forbidden
    if any(char in FILENAME_FORBIDDEN_CHARACTERS for char in name):
        return False
    if name[-1] in FORBIDDEN_LAST_FILENAME_CHARACTERS:  # file name can't end with dot or space
        return False
    if len(name) == 0:  # empty string isn't a valid file name
        return False
    return True  # if the name passes all of those checks, it's valid


def upload(request: HttpRequest) -> HttpResponse:
    """
    Used for the /upload endpoint (in POST method).
    Gets a file in the request body (from a form, in form-data format).
    It uploads the file to the server, in {WEBROOT}/{UPLOADS_PATH}
    Returns HTTP Response with status code 201 Created to indicate success.
    """
    form_data_headers, form_data_content = parse_form_data(
        request.get_body(), request.get_headers())  # parse the form data body
    # retrieve file name from the Content-Disposition header (as a parameter)
    content_disposition_header = try_retrieve_from_dictionary(
        form_data_headers, "Content-Disposition", "Missing Content-Disposition header in request body")
    _, content_disposition_params = parse_header_value_parameters(
        content_disposition_header)
    file_name = try_retrieve_from_dictionary(
        content_disposition_params, "filename", "Missing filename in Content-Disposition header in request body")
    # Validate that the file name is actualyl valid
    if not is_valid_filename(file_name):
        raise BadRequest("Invalid filename")
    file_path = f"{ROOT_DIRECTORY}{UPLOADS_PATH}/{file_name}"
    # write the file to the server.
    write_to_file(file_path, form_data_content)
    headers = {"Content-Type": PLAINTEXT_CONTENT_TYPE}
    return HttpResponse(CREATED_STATUS_CODE, CREATED_REASON_PHRASE, headers, b"Upload Sucessful")


def get_content_type(file_name: str) -> str:
    """
    This method returns the Content Type that should be used for a given file by it's name.
    It checks it according to the extension and defaults to text/plain in case of no extension or extension that isn't specified.
    Gets the file_name as string and returns the content type as string.
    """
    extension_seperator = file_name.rfind(".")  # the last dot in the name
    if extension_seperator != -1:  # If there's an extension
        extension = file_name[extension_seperator + 1:]  # after the last dot
        # If the extension exists in the CONTENT_TYPE_BY_EXTENSION dictionary, return the matching entry.
        if extension in CONTENT_TYPE_BY_EXTENSION:
            return CONTENT_TYPE_BY_EXTENSION[extension]
    # In case of no extension or extension not in dictionary, return PLAINTEXT_CONTENT_TYPE by default.
    return PLAINTEXT_CONTENT_TYPE


def get_image(request: HttpRequest) -> HttpResponse:
    """
    Used for the /image endpoint.
    Gets a HttpRequest. Gets image-name as a query parameter.
    Returns the uploaded file with this name (if exists).
    Returns 404 if it doesn't exist.
    Generates a HttpResponse and returns it.
    """
    image_name = try_retrieve_from_dictionary(
        request.get_query_parameters(), "image-name", "Missing image-name parameter")
    # validate that the image name is an actually valid file name
    if not is_valid_filename(image_name):
        raise BadRequest("Invalid image name")
    image_path = f"{ROOT_DIRECTORY}{UPLOADS_PATH}/{image_name}"
    # if a file with this name exists, return it in the response.
    if os.path.exists(image_path):
        image_content = get_file_content(image_path)
        # use the content type according to the image type.
        headers = {"Content-Type": get_content_type(image_name)}
        return HttpResponse(OK_STATUS_CODE, OK_REASON_PHRASE, headers, image_content)
    else:  # if it doesn't exist, return 404.
        headers = {}
        return HttpResponse(NOT_FOUND_STATUS_CODE, NOT_FOUND_REASON_PHRASE, headers, b"")


def get_file(request_path: str) -> HttpResponse:
    """
    Used in case the request doesn't match a previous specifically-handled endpoint.
    Gets a str of the request path.
    Gets the requested resource from the server and returns it in the HttpResponse.
    In case it doesn't exist, return 404.
    Also returns 403 in case of an attempt to access directory
    Generates a HttpResponse and returns it.
    """
    file_path = ROOT_DIRECTORY + request_path
    # test if there's a directory traversal attempt
    root_directory_absolute_path = os.path.abspath(
        ROOT_DIRECTORY + "/")  # absolute path of the root directory
    # absolute path of the requested file.
    request_absolute_path = os.path.abspath(file_path)
    # verify the abs path of the requested resource starts with the abs path of the root directory (which mean's its inside the root directory)
    if os.path.commonprefix([root_directory_absolute_path, request_absolute_path]) != root_directory_absolute_path:
        # In case it doesn't, return Forbidden HTTP response
        return HttpResponse(FORBIDDEN_STATUS_CODE, FORBIDDEN_REASON_PHRASE, {}, b"")
    if os.path.isdir(file_path):  # If the user asks for a directory, also return Forbidden
        return HttpResponse(FORBIDDEN_STATUS_CODE, FORBIDDEN_REASON_PHRASE, {}, b"")
    # If the user asks for a valid file and it exists, return it.
    if os.path.exists(file_path):
        response_body = get_file_content(file_path)
        # use content type according to the file name.
        response_headers = {"Content-Type": get_content_type(file_path)}
        return HttpResponse(OK_STATUS_CODE, OK_REASON_PHRASE, response_headers, response_body)
    # if the file doesn't exist, return 404.
    headers = {}
    return HttpResponse(NOT_FOUND_STATUS_CODE, NOT_FOUND_REASON_PHRASE, headers, b"")


# a dictionary of each custom api endpoint, key is (method, path) and value is the function to call for this endpoint.
API_METHODS = {
    ("GET", "/calculate-next"): calculate_next,
    ("GET", "/calculate-area"): calculate_area,
    ("POST", "/upload"): upload,
    ("GET", "/image"): get_image
}

# the server configuration: host address, port and client timeout
HOST_ADDRESS = "localhost"
PORT = 80
CLIENT_TIMEOUT = 2


def main():
    server = HttpServer(HOST_ADDRESS, PORT, CLIENT_TIMEOUT)
    while True:
        conn = server.accept_client()
        try:
            request = conn.recieve_request()  # recieve a request
            request_path = request.get_request_path()
            request_method = request.get_method()
            # if the request matches an api endpoint call the matching functoin
            if (request_method, request_path) in API_METHODS:
                response = API_METHODS[(request_method, request_path)](request)
            else:  # otherwise try to get the path as file.
                response = get_file(request_path)
            conn.send_response(response)
        except socket.timeout:  # In case of timeout when recieving the request, send a Request Timeout response
            # Signal to close the connection, as mentioned in rfc 7231 6.5.7
            response_headers = {"Connection": "close"}
            response = HttpResponse(
                REQUEST_TIMEOUT_STATUS_CODE, REQUEST_TIMEOUT_REASON_PHRASE, response_headers, b"")
            conn.send_response(response)
        # In the case of a bad request exception (raised when the request is invalid), send bad request response with the error message
        except BadRequest as e:
            body = e.message.encode()
            headers = {"Content-Type": PLAINTEXT_CONTENT_TYPE}
            response = HttpResponse(
                BAD_REQUEST_STATUS_CODE, BAD_REQUEST_REASON_PHRASE, headers, body)
            conn.send_response(response)
        except Exception as e:  # In case there was some error during the processing of the request
            response = HttpResponse(
                INTERNAL_SERVER_ERROR_STATUS_CODE, INTERNAL_SERVER_ERROR_REASON_PHRASE, {}, b"")
            # return Internal Server Error response
            conn.send_response(response)
        conn.close()


if __name__ == "__main__":
    main()
