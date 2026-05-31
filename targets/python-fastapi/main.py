import asyncio

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

MOD = 1000000007


# O(n²) sobre n objetos + O(C³) multiplicación de matrices C×C (C=64).
def cpu_compute(n: int) -> int:
    objects = [{"id": i, "x": (i * 31) % 1000} for i in range(n)]
    derived = [(o["x"] * 2 + 1) % 1000 for o in objects]

    checksum = 0
    for i in range(n):
        di = derived[i]
        for j in range(n):
            checksum = (checksum + di * derived[j]) % MOD

    C = 64
    for i in range(C):
        for j in range(C):
            s = 0
            for k in range(C):
                s += ((i * C + k) % 100) * ((k + j) % 100)
            checksum = (checksum + s) % MOD
    return checksum


# Aloca n objetos anidados (todos vivos a la vez) y serializa una muestra.
def mem_alloc(n: int):
    arr = [
        {
            "id": i,
            "name": "item-" + str(i),
            "tags": [i, i + 1, i + 2],
            "payload": {"a": i % 100, "b": (i * 2) % 100, "c": (i * 3) % 100},
        }
        for i in range(n)
    ]
    total = sum(o["payload"]["a"] for o in arr)
    return {"count": n, "sum": total, "sample": arr[:100]}


class Item(BaseModel):
    id: int
    name: str
    value: int
    active: bool


class Payload(BaseModel):
    items: list[Item]
    meta: dict = {}


@app.get("/holamundo")
def holamundo():
    return {"mensaje": "hola mundo"}


@app.get("/dbquery")
async def dbquery():
    await asyncio.sleep(0.025)
    rows = [{"id": k, "value": k * 10} for k in range(10)]
    return {"rows": rows}


@app.get("/cpucompute")
def cpucompute(n: int = 200):
    return {"checksum": cpu_compute(n), "n": n}


@app.get("/memalloc")
def memalloc(n: int = 20000):
    return mem_alloc(n)


@app.post("/payload")
def payload(body: Payload):
    active = [it for it in body.items if it.active]
    total = sum(it.value for it in active)
    sample = [{"id": it.id, "name": it.name.upper(), "value": it.value} for it in body.items[:10]]
    return {
        "received": len(body.items),
        "activeCount": len(active),
        "total": total,
        "sample": sample,
    }
