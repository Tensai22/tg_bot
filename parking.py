import requests
import config

def get_free_parking():
    response = requests.get(f"{config.PARKING_API}/free")
    return response.json() if response.status_code == 200 else []

#postgresql+asyncpg://tensai:e1R8FcwrIUma8z99ffg1qgcp8ONJM4xh@dpg-cvpulta4d50c73bv6de0-a.oregon-postgres.render.com/smart_parking_b3hj