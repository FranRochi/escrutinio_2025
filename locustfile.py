import random
from locust import HttpUser, task, between

# ===========================
# Pool de credenciales reales
# ===========================
USERS = [
    {"username": "operador1", "password": "sistemas123"},
    {"username": "operador2", "password": "sistemas123"},
]

# ===========================
# Panelista: lee dashboards
# ===========================
class PanelistaUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def circuitos(self):
        self.client.get("/api/panel/circuitos/")

    @task(2)
    def secciones(self):
        self.client.get("/api/panel/secciones/")

    @task(1)
    def votantes(self):
        self.client.get("/api/panel/votantes/")


# ===========================
# Operador: carga votos y marca votantes
# ===========================
class OperadorUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        """
        Simula login por JWT usando operador1/2 de manera aleatoria.
        """
        creds = random.choice(USERS)
        r = self.client.post("/api/login/", json={
            "username": creds["username"],
            "password": creds["password"]
        })
        if r.status_code == 200 and "access" in r.json():
            token = r.json()["access"]
            self.client.headers.update({"Authorization": f"Bearer {token}"})
        else:
            print(f"⚠️ Error de login ({creds['username']}):", r.status_code, r.text)

    @task(3)
    def guardar_votos(self):
        """
        Simula carga de votos en una mesa existente.
        ⚠️ Ajustá mesa_id al rango real de tu base de datos.
        """
        mesa_id = random.randint(1, 10)  # <-- cambiá si tenés más mesas
        self.client.post("/guardar_votos", json={
            "mesa_id": mesa_id,
            "votos_cargo": [
                {"partido_postulacion_id": 1, "votos": random.randint(0, 50)},
                {"partido_postulacion_id": 2, "votos": random.randint(0, 50)},
            ],
            "votos_especiales": [
                {"cargo_postulacion_id": 1, "tipo": "blanco", "votos": random.randint(0, 5)}
            ],
            "resumen_mesa": {
                "electores_votaron": 200,
                "sobres_encontrados": 200,
                "diferencia": 0
            },
            "overwrite": True
        })

    @task(2)
    def marcar_voto(self):
        """
        Simula marcar votantes en padrón.
        ⚠️ Ajustá 'mesa' a una mesa válida asignada a ese operador.
        """
        self.client.post("/api/marcar_voto", json={
            "mesa": 1,  # <-- poné un número de mesa válido
            "orden": str(random.randint(1, 350)).zfill(3),
            "accion": "SI"
        })
