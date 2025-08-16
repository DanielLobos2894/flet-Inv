import uvicorn
from api import app

if __name__ == "__main__":
    # Ejecutar el servidor en 0.0.0.0 para hacerlo accesible en la red local
    # El puerto 8000 es el predeterminado
    uvicorn.run(app, host="0.0.0.0", port=8000)
