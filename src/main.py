import uvicorn
from fastapi import FastAPI
app = FastAPI()


@app.get("/hello")
def hello():
    return "200"


if __name__ == "__main__":
    uvicorn.run(app)
