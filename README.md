# BarberCo — Backend Python + FastAPI

## Estructura del proyecto

```
barberico/
├── main.py            ← Backend FastAPI
├── index.html         ← Frontend (sin cambios visuales)
├── requirements.txt   ← Dependencias Python
├── barberico.db       ← Base de datos SQLite (se crea sola)
└── README.md
```

## Instalación

```bash
pip install -r requirements.txt
```

## Arrancar el servidor

```bash
python main.py
```

Luego abre tu navegador en: **http://localhost:8000**

## Credenciales de admin

- **Correo:** admin@barberia.com  
- **Contraseña:** admin123

## Cómo funciona

- El `index.html` al cargar hace un `GET /api/ping` para detectar si el backend está activo.
- **Con backend:** todos los datos se guardan en SQLite (`barberico.db`).
- **Sin backend (archivo directo):** el sistema cae automáticamente a `localStorage` — funciona igual que antes.

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /api/ping | Verificar que el backend está vivo |
| POST | /api/registro | Registrar nuevo usuario |
| POST | /api/login | Iniciar sesión |
| GET | /api/horarios | Listar horarios disponibles |
| GET | /api/citas | Citas (filtrar por `?usuario_id=`) |
| GET | /api/citas/admin | Citas con datos del cliente (admin) |
| POST | /api/citas | Crear nueva cita |
| PATCH | /api/citas/{id}/cancelar | Cancelar una cita |
| GET | /api/clientes | Listar clientes (admin) |
| GET | /api/stats | Estadísticas generales (admin) |

## Documentación interactiva

FastAPI genera docs automáticamente en: **http://localhost:8000/docs**
