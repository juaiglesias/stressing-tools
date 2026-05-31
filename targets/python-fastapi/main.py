from fastapi import FastAPI

app = FastAPI()


@app.get("/holamundo")
def holamundo():
    return {"mensaje": "hola mundo"}
