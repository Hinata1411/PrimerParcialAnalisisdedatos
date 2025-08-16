# main.py
from fastapi import FastAPI
from api import router as productos_router  # si api.py está al mismo nivel

app = FastAPI(title="API Cooperativa", version="1.0.0")
app.include_router(productos_router)

# opcional para ejecutar con `python main.py`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
