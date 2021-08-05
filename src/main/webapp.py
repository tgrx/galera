from fastapi import FastAPI
from starlette.requests import Request

application = FastAPI()


@application.get("/")
def handler(request: Request):
    return {
        "request": {
            "client": {
                "host": request.client.host,
                "port": request.client.port,
            },
            "headers": request.headers,
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(application, host="0.0.0.0", port=8000, log_level="debug")
