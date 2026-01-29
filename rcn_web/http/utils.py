import typing
import httpx

from mitmproxy import http
from json import JSONEncoder


def headers_obj_to_list(
    headers: "typing.Union[http.Headers, dict, list[list]] ",
) -> "list[list]":

    new_val = list()
    if isinstance(headers, httpx.Headers):
        for h, v in headers.multi_items():
            new_val.append([h.lower(), v])

    elif isinstance(headers, http.Headers):
        # NOTE:I don't know why the fuck this happens
        # but the freaking mitmproxy flow.request.headers
        # creates a header cookie per cookie
        cookie_header = ""
        for h, v in headers.fields:
            h = h.decode("utf-8", errors="surrogateescape").lower()
            v = v.decode("utf-8", errors="surrogateescape").strip()
            if h == "cookie":
                cookie_header += v + "; "
                continue

            new_val.append([h, v])

        if cookie_header:
            new_val.append(["cookie", cookie_header.strip()])

    elif isinstance(headers, dict):
        for h in headers:
            new_val.append([h.lower(), headers[h]])

    elif isinstance(headers, list):
        for h_list in headers:
            new_val.append((h_list[0].lower(), h_list[1]))

    else:
        print("***********")
        print(headers.__module__)
        print("***********")
        raise ValueError("headers must be in [dict, list, set, mitmproxy.http.Headers]")

    return new_val


def get_header_value(headers: "list[list]", key: str, default=None):
    for header_tuple in headers:
        if header_tuple[0] == key:
            return header_tuple[1]

    return default


def set_header_value(headers: "list[list]", key: str, value: str):
    elements = []
    for header_tuple in headers:
        if header_tuple[0] == key:
            elements.append(header_tuple)

    # remove all the previous key values
    for element in elements:
        headers.remove(element)

    headers.append([key, value])


def remove_header_key(headers: "list[list]", key: str):
    elements = []
    for header_tuple in headers:
        if header_tuple[0] == key:
            elements.append(header_tuple)

    # remove all the previous key values
    for element in elements:
        headers.remove(element)
