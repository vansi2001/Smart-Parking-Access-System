import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",                     # main:app là file main.py chứa FastAPI app
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="../frontend/server.key",
        ssl_certfile="../frontend/server.crt",
        reload=True
    )
