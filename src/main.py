import uvicorn
from fastapi import FastAPI
import os
app = FastAPI()


@app.get("/hello")
def hello():
    return "200"


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app)
