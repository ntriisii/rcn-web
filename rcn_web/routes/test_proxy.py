import asyncio
import random
import string
import requests
import base64

from collections import defaultdict
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter(prefix="/proxy")

csrf_counts = defaultdict(lambda: 0)


@router.get("/analyzeProxy")
@router.post("/analyzeProxy")
async def analyze(req: Request):
    # await asyncio.sleep(random.randint(1, 3))
    body = await req.body()
    headers = req.headers
    url = req.url
    method = req.method
    csrf = req.headers.get("csrf-token")
    if not csrf or (csrf in csrf_counts and csrf_counts[csrf] > 3):
        return JSONResponse({"error": "error csrf"}, status_code=403)

    csrf_counts[csrf] += 1

    return JSONResponse(
        {
            "body": body.decode("utf-8"),
            "headers": dict(headers),
            "url": str(url),
            "method": method,
        },
        status_code=200,
    )


@router.get("/csrf_token")
async def get_csrf(req: Request):
    # await asyncio.sleep(random.randint(1, 3))
    csrf = "".join(random.choice(string.ascii_letters) for i in range(10))
    return JSONResponse({"csrf": csrf})


@router.get("/testingParams")
@router.post("/testingParams")
async def param_miner_test(req: Request):
    parsedq = parse_qs(urlparse(str(req.url)).query)
    headers = req.headers
    body = (await req.body()).decode("utf-8")
    test_params = ["Itemid", "_method", "_bc_fsnf"]
    test_headers = ["Auth-Realm", "Cert-Serialnumber", "Client-Unauthorized"]
    test_body = ["_bc_fsnf", "_method", "Itemid"]
    if (
        any(i in parsedq.keys() for i in test_params)
        or any(i.lower() in headers.keys() for i in test_headers)
        or any(i in body for i in test_body)
    ):

        return JSONResponse({}, status_code=404)


@router.post("/login")
async def login(request: Request):
    # print('---------------')
    # print(await request.body())
    # print('---------------')
    body = await request.json()
    csrf = body["csrf_token"]
    if csrf in csrf_tokens:
        csrf_tokens.remove(csrf)
    else:
        return HTMLResponse(
            "<html> <body> <h1> invalid csrf token </h1> </body></html>",
            status_code=403,
        )

    if body["username"] == "admin" and body["password"] == "p4ssw0rd":
        return HTMLResponse(
            """
      <!DOCTYPE html>
<html>
<head>
  <title>Welcome Page</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
    }
  </style>
</head>
<body>
  <h1>Welcome!</h1>
  <p>Thank you for visiting our website.</p>
  <img src="welcome-image.jpg" alt="Welcome Image">
  <p>Feel free to explore our website and learn more about us.</p>
  <a href="#">Learn More</a>
  <a href="#">Contact Us</a>
</body>
</html>
      """
        )

    import random

    return HTMLResponse(
        """
    <!DOCTYPE html>
<html>
<head>
  <title>Login Page</title>
</head>
<body>
  <h1>Login Page</h1>
  <form action="/login" method="post">
    <label for="username">Username:</label>
    <input type="text" id="username" name="username"><br><br>
    <label for="password">Password:</label>
    <input type="password" id="password" name="password"><br><br>
    <label for="csrf_token">CSRF Token:</label>
    <input type="hidden" id="csrf_token" name="csrf_token" value="your_csrf_token_here">
    <input type="submit" value="Login">
  </form>
</body>
</html>
    """,
        status_code=401,
    )


@router.get("/returnRandomData")
async def return_random_integral_data(request: Request):
    import random

    return JSONResponse(
        {
            "request-headers": dict(request.headers),
            "request-url": str(request.url),
            "random-integer": random.randint(0, 100),
            "base64-string": base64.b64encode(b"this is base64 encoded string").decode(
                "ascii"
            ),
        }
    )


@router.get("/requestURL")
def request_url(url: str):
    print(requests.get("https://" + url + "/").content)


csrf_tokens = []


@router.get("/getCSRFTokenJson")
async def csrf_token_json_response(
    request: Request,
):  # from rcn_core.storage.bases import BasicDataStorage

    # return JSONResponse(content)
    csrf_token = "".join(random.choice(string.ascii_letters) for i in range(40))
    csrf_tokens.append(csrf_token)
    return JSONResponse({"token": csrf_token})


@router.get("/getCSRFToken")
async def csrf_token_response(
    request: Request,
):  # from rcn_core.storage.bases import BasicDataStorage

    # return JSONResponse(content)
    csrf_token = "".join(random.choice(string.ascii_letters) for i in range(40))
    return HTMLResponse(
        f"""
<!DOCTYPE html>
<html>
<head>
  <title>What is CSRF?</title>
</head>
<body>
  <h1>What is CSRF?</h1>
  <p>CSRF stands for Cross-Site Request Forgery, a type of web attack where an attacker tricks a user into performing an unintended action on a web application.</p>
  <p>Here's an example of how it works:</p>
  <ol>
    <li>An attacker creates a malicious link that, when clicked, sends a request to a vulnerable web application.</li>
    <li>The request is authenticated using the user's session cookie, allowing the attacker to perform the action without the user's knowledge or consent.</li>
  </ol>
  <p>To prevent CSRF attacks, web applications use tokens, such as the one below:</p>
  <input type="hidden" name="csrf_token" value="{csrf_token}">
  <p>This token is generated by the web application and is included in every request. When the web application receives a request, it checks the token to ensure it matches the one stored in the user's session. If the tokens match, the request is considered valid and is processed accordingly.</p>
  <p>By using CSRF tokens, web applications can prevent attackers from tricking users into performing unintended actions.</p>
</body>
</html>
    """
    )


@router.get("/testRequest")
@router.post("/testRequest")
@router.put("/testRequest")
@router.delete("/testRequest")
@router.patch("/testRequest")
@router.head("/testRequest")
@router.options("/testRequest")
async def test_request(request: Request):

    # Get request data
    ctx = "html"
    method = request.method
    headers = dict(request.headers)
    url_params = dict(request.query_params)
    if url_params.get("__context"):
        ctx = url_params["__context"]
        del url_params["__context"]

    # Get body content
    body_content = b""
    try:
        body_content = await request.body()
    except:
        pass

    body_text = body_content.decode("utf-8", errors="ignore") if body_content else ""

    # Parse body as form data if it's form encoded
    body_params = {}
    if "content-type" in headers and "form" in headers["content-type"].lower():
        try:
            from urllib.parse import parse_qs

            parsed = parse_qs(body_text)
            body_params = {k: v[0] if v else "" for k, v in parsed.items()}

        except:
            body_params = {}

    # Combine all parameters for testing
    all_params = {**url_params, **body_params}

    # Generate XSS test response
    html_content = generate_xss_test_content(
        all_params, method, headers, body_text, ctx
    )

    return HTMLResponse(html_content)


def generate_xss_test_content(params, method, headers, body, ctx):
    """Generate HTML content with reflected parameters in various contexts for XSS testing"""

    # Create parameter reflections in different contexts
    param_reflections = []
    for key, value in params.items():

        # HTML comment context
        if ctx == "comment":
            param_reflections.append(f"<!-- {value} -->")

        # HTML context
        elif ctx == "html":
            param_reflections.append(f"<div>HTML Context: {value}</div>")

        # Attribute context (unquoted)
        elif ctx == "unquoted-attr":
            param_reflections.append(
                f"<div class={value}>Attribute Context (Unquoted)</div>"
            )

        # Attribute context (single quoted)
        elif ctx == "single-quoted-attr":
            param_reflections.append(
                f"<div class='{value}'>Attribute Context (Single Quoted)</div>"
            )

        # Attribute context (double quoted)
        elif ctx == "double-quoted-attr":
            param_reflections.append(
                f'<div class="{value}">Attribute Context (Double Quoted)</div>'
            )

        # JavaScript context
        elif ctx == "script":
            param_reflections.append(f'<script>var {key} = "{value}";</script>')

        # JavaScript event context
        elif ctx == "javascript-event":
            param_reflections.append(
                f"<button onclick=\"alert('{value}')\">JS Event Context</button>"
            )

        # URL context
        elif ctx == "url":
            param_reflections.append(f'<a href="{value}">URL Context</a>')

        # CSS context
        elif ctx == "css":
            param_reflections.append(
                f'<div style="background: url({value})">CSS Context</div>'
            )

        # Textarea context
        elif ctx == "textarea":
            param_reflections.append(f"<textarea>{value}</textarea>")

    # Join all reflections
    reflections_html = "\n".join([random.choice(param_reflections)])

    # Generate the full HTML response
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>XSS Test Endpoint</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f0f0f0;
        }}
        .header {{
            background-color: #333;
            color: #fff;
            padding: 20px;
            text-align: center;
            border-radius: 5px;
        }}
        .content {{
            margin-top: 20px;
            padding: 20px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        .section {{
            margin-bottom: 20px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .reflection {{
            background-color: #ffeeee;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #ff0000;
        }}
        .info {{
            background-color: #eef;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #0000ff;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>XSS Test Endpoint</h1>
        <p>Testing XSS vulnerabilities with reflected parameters</p>
    </div>
    
    <div class="content">
        <div class="section info">
            <h2>Request Information</h2>
            <p><strong>Method:</strong> {method}</p>
            <p><strong>Parameters:</strong> {len(params)} parameters received</p>
        </div>
        
        <div class="section">
            <h2>Reflected Parameters</h2>
            <p>The following parameters are reflected in various contexts:</p>
            {reflections_html}
        </div>
        
        <div class="section info">
            <h2>Raw Request Data</h2>
            <details>
                <summary>Click to expand headers</summary>
                <pre>{'__' or dict(headers)}</pre>
            </details>
            <details>
                <summary>Click to expand body</summary>
                <pre>{'__' or body}</pre>
            </details>
        </div>
        
        <div class="section">
            <h2>Test Cases</h2>
            <p>Try these payloads in parameters to test for XSS:</p>
            <ul>
                <li><code>&lt;script&gt;alert(1)&lt;/script&gt;</code></li>
                <li><code>"&gt;&lt;script&gt;alert(1)&lt;/script&gt;</code></li>
                <li><code>'&gt;&lt;script&gt;alert(1)&lt;/script&gt;</code></li>
                <li><code>javascript:alert(1)</code></li>
                <li><code>onerror=alert(1)</code></li>
                <li><code>&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;</code></li>
            </ul>
        </div>
    </div>
    
    <!-- Additional contexts for testing -->
    <div id="{params.get('id', '')}">ID Attribute Context</div>
    <div class="{params.get('class', '')}">Class Attribute Context</div>
    <input type="text" value="{params.get('value', '')}">
    <a href="{params.get('href', '')}">Link Context</a>
    <img src="{params.get('src', '')}" onerror="{params.get('onerror', '')}">
    
    <script>
        // JavaScript context with parameters
        var testData = {{
            "param1": "{params.get('js_param1', '')}",
            "param2": "{params.get('js_param2', '')}"
        }};
        
        // This is for testing DOM XSS
        document.write("{params.get('dom_param', '')}");
    </script>
</body>
</html>"""

    return html
