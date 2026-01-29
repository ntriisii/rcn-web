import json

from fastapi.responses import JSONResponse
import typing


class PyObjSeralizedJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        def default_seralized(obj):
            if isinstance(obj, set):
                return list(obj)
            raise TypeError("cannot seralize type" f" {type(obj)}")

        return json.dumps(content, default=default_seralized).encode("utf-8")
