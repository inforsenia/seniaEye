import logging
import json
from pathlib import Path

# Crear archivo en la raíz del proyecto
LOG_FILE = Path("eventos.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)

def guardar_evento(evento: dict):
    """
    Guarda un evento en el archivo eventos.log en formato JSON
    """
    logging.info(json.dumps(evento))