# BuildCorp EVA4 — Backend y plataforma operativa

API REST Django/DRF para gestión de obras, tareas, auditoría e inventario de herramientas. El despliegue actual usa **dos instancias EC2 separadas**, **Nginx con TLS**, **Gunicorn**, **Amazon RDS PostgreSQL** y **Amazon S3**. No se requiere API Gateway ni cambios de infraestructura AWS para operar la versión actual.

---

## 1. Arquitectura

```text
Navegador
   │ HTTPS
   ▼
EC2 Frontend (18.234.88.124)
Nginx + TLS (vhost buildcorp)
   ├── /            → SPA estática en /var/www/buildcorp-frontend
   └── /api/        → proxy al backend privado 172.31.20.129
                         │
                         ▼
EC2 Backend (54.147.180.131)
Nginx (HTTP interno)
   └── unix:/home/ubuntu/apps/backend/backend.sock
         │
         ▼
Gunicorn (3 workers, systemd `gunicorn.service`)
         │
         ▼
Django 5 / DRF (`/api/v1/`)
   ├── RDS PostgreSQL (TLS, `sslmode=require`)
   └── S3 privado (adjuntos; URLs prefirmadas)

Dominio público: https://buildcorp2.duckdns.org
```

### Componentes

| Capa | Tecnología | Función |
|---|---|---|
| Cliente | SPA HTML/CSS/JS | Login, obras, tareas, inventario, pedidos, devoluciones y auditoría |
| Frontend EC2 | Nginx + TLS | Sirve la SPA y proxya `/api/` al backend |
| Backend EC2 | Nginx + Gunicorn | Reverse proxy al socket Unix de Django |
| API | Django REST Framework | JWT, RBAC, reglas de negocio y auditoría |
| Base de datos | Amazon RDS PostgreSQL | Persistencia transaccional |
| Archivos | Amazon S3 | Adjuntos de tareas con cifrado AES-256 |

`ALLOWED_HOSTS` debe incluir `buildcorp2.duckdns.org`, `localhost`, `127.0.0.1` y la IP privada del backend usada por el proxy (`172.31.20.129`). `CORS_ALLOWED_ORIGINS` debe incluir el dominio público.

---

## 2. Modelo de datos

El app `core` contiene 12 entidades:

1. `User` (UUID, login por email, rol `ADMIN`/`MANAGER`/`MEMBER`).
2. `Workspace`.
3. `WorkspaceMember`.
4. `Project`.
5. `Tag`.
6. `Task`.
7. `TaskComment`.
8. `Subtask`.
9. `AuditLog`.
10. `Tool` (catálogo y stock).
11. `ToolRequest` (pedido de herramientas).
12. `ToolReturn` (devolución numerada `#001`, `#002`, ...).

El stock se descuenta al aprobar/entregar un pedido y se repone al recepcionar una devolución, dentro de transacciones atómicas con `select_for_update`.

---

## 3. Roles y permisos

### `ADMIN`
- Ver todas las obras, tareas, pedidos y devoluciones.
- Crear, editar y eliminar herramientas del catálogo.
- Cambiar estados de pedidos: `PENDIENTE` → `APROBADA`/`ENTREGADA`/`RECHAZADA`; `APROBADA` → `ENTREGADA`/`RECHAZADA`.
- Al rechazar, debe indicar un motivo breve que se guarda en `notes`.
- Recepcionar devoluciones y ver la bitácora de auditoría completa.

### `MEMBER`
- Consultar catálogo y stock.
- Crear pedidos asociados a una tarea/frente de obra.
- Cancelar solo sus propios pedidos en `PENDIENTE`.
- Registrar devoluciones de pedidos entregados.
- Ver pedidos propios o asignados y sus devoluciones.
- No puede editar herramientas, cambiar estados, recepcionar devoluciones ni ver la pestaña de auditoría.

> `MANAGER` existe como valor legacy en el modelo, pero no otorga privilegios administrativos en el comportamiento actual; operativamente se trata como `MEMBER`.

---

## 4. Endpoints principales

Base: `https://buildcorp2.duckdns.org/api/v1/` (en local: `http://localhost:8000/api/v1/`).

| Método | Endpoint | Acceso | Descripción |
|---|---|---|---|
| `POST` | `/auth/register/` | Público | Registro de usuario (siempre `MEMBER` en la práctica). |
| `POST` | `/auth/token/` | Público | Login JWT: `access` + `refresh`. |
| `POST` | `/auth/token/refresh/` | Público | Renueva el `access`. |
| `GET` | `/auth/me/` | Autenticado | Perfil del usuario actual. |
| `GET` | `/health/` | Público | Estado del servicio y conexión RDS. |
| `GET` | `/docs/`, `/schema/` | Público | Swagger / OpenAPI 3. |
| `GET/POST` | `/workspaces/` | Autenticado | Sedes/áreas operativas. |
| `GET/PUT/PATCH/DELETE` | `/workspaces/{id}/` | Owner/ADMIN | Edición de sede. |
| `GET/POST` | `/workspace-members/` | Autenticado | Membresías por sede (`?workspace=`). |
| `GET/POST` | `/projects/` | Autenticado | Obras/proyectos. |
| `GET/PUT/PATCH/DELETE` | `/projects/{id}/` | Owner/ADMIN | Edición de obra. |
| `GET/POST` | `/tags/` | Autenticado | Etiquetas de tareas. |
| `GET/POST` | `/tasks/` | Autenticado | Tareas; filtros `?status=`, `?priority=`, `?project=`. |
| `GET/PUT/PATCH/DELETE` | `/tasks/{id}/` | Owner/ADMIN o avance de campo | Edición/adjo de evidencia S3. |
| `GET/POST` | `/comments/` | Autenticado | Comentarios/notas de terreno (`?task=`). |
| `GET/POST` | `/subtasks/` | Autenticado | Checklist (`?task=`). |
| `GET/POST` | `/tools/` | GET: autenticado / POST: ADMIN | Catálogo; ADMIN edita `name`, `description` y `stock` con `PATCH /tools/{id}/`. |
| `GET/POST` | `/tool-requests/` | Autenticado | Pedidos; ADMIN filtra `?status=`, `?tool=`. |
| `GET/PATCH/DELETE` | `/tool-requests/{id}/` | Según rol | Cambio de estado y motivo de rechazo en `notes`. |
| `GET/POST` | `/tool-returns/` | Autenticado | Devoluciones numeradas. |
| `GET/PATCH/DELETE` | `/tool-returns/{id}/` | ADMIN para verificar/borrar | `PATCH { "status": "RECEPCIONADA" }` repone stock. |
| `GET` | `/audit-logs/` | Autenticado | ADMIN ve todo; MEMBER ve solo sus eventos. |

La paginación por defecto es `PAGE_SIZE: 20`.

---

## 5. Desarrollo local

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # DB_ENGINE vacío usa SQLite local
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Comandos de validación:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core
```

En EC2 se usa el venv del servidor:

```bash
cd /home/ubuntu/apps/backend
./venv/bin/python manage.py check
./venv/bin/python manage.py makemigrations --check --dry-run
env -u DB_ENGINE ./venv/bin/python manage.py test core
```

> Con `.env` de producción, `load_dotenv()` vuelve a cargar `DB_ENGINE=postgresql`; la suite crea y destruye una base de prueba en RDS.

Datos de ejemplo del módulo de herramientas:

```bash
./venv/bin/python manage.py seed_tool_module
```

El seed es idempotente: reutiliza el primer `ADMIN` y el primer `MEMBER` existentes y no duplica catálogo ni pedidos.

---

## 6. Despliegue en producción

### Backend (EC2 `54.147.180.131`)

```bash
ssh -i "eva4.pem" ubuntu@54.147.180.131
cd /home/ubuntu/apps/backend

# El push lo realiza el responsable del repositorio; en la instancia solo se integra:
git pull origin main

./venv/bin/python manage.py check
./venv/bin/python manage.py makemigrations --check --dry-run
env -u DB_ENGINE ./venv/bin/python manage.py test core
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py seed_tool_module

sudo systemctl restart gunicorn
sudo nginx -t && sudo systemctl reload nginx
curl -i http://localhost/api/v1/health/
sudo journalctl -u gunicorn -n 50 --no-pager
```

Permisos esperados del código: archivos `644`, propiedad `ubuntu:www-data`, socket accesible por `www-data`. El servicio `gunicorn` debe quedar `active`.

### Frontend (EC2 `18.234.88.124`)

La SPA **no** se sube al backend. Se stagea y se instala con propiedad `www-data:www-data`:

```bash
# Desde local:
scp -i "eva4-frontend-key.pem" -r frontend/* ubuntu@18.234.88.124:/tmp/buildcorp-frontend/

# En la EC2 frontend:
cd /tmp/buildcorp-frontend
sudo install -d -o www-data -g www-data /var/www/buildcorp-frontend/js /var/www/buildcorp-frontend/css
sudo install -o www-data -g www-data -m 644 index.html /var/www/buildcorp-frontend/
sudo install -o www-data -g www-data -m 644 js/api.js js/auth.js js/app.js /var/www/buildcorp-frontend/js/
sudo install -o www-data -g www-data -m 644 css/styles.css /var/www/buildcorp-frontend/css/

sudo nginx -t
sudo systemctl reload nginx
curl -I https://buildcorp2.duckdns.org/
```

`index.html` referencia `css/styles.css?v=20261128` y `js/app.js?v=20261128` para forzar la renovación de caché. Si se vuelve a modificar el frontend, incrementar la versión.

### Verificación funcional mínima

```bash
curl -i https://buildcorp2.duckdns.org/api/v1/health/
curl -i https://buildcorp2.duckdns.org/api/v1/tools/          # 401 sin token
curl -i https://buildcorp2.duckdns.org/api/v1/tool-requests/  # 401 sin token
curl -i https://buildcorp2.duckdns.org/api/v1/tool-returns/   # 401 sin token
```

Con tokens reales: MEMBER no debe poder hacer `POST /tools/` ni ver `/audit-logs/` en la UI; ADMIN debe completar el ciclo aprobar → entregar → devolver → recepcionar.

---

## 7. Respaldo y rollback

Antes de una migración o cambio de datos:

```bash
# Backend
cp -a /home/ubuntu/apps/backend/core /home/ubuntu/core.pre-inventario
mkdir -p /home/ubuntu/db_backups
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  > /home/ubuntu/db_backups/eva4-pre-inventario.sql

# Frontend
sudo cp -a /var/www/buildcorp-frontend /home/ubuntu/frontend.pre-inventario
```

### Rollback backend

```bash
cd /home/ubuntu/apps/backend
sudo systemctl stop gunicorn

# Con el código actual (que conoce la migración 0002):
./venv/bin/python manage.py migrate core 0001

# Restaurar código y, si aplica, datos:
cp -a /home/ubuntu/core.pre-inventario/. core/
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -f /home/ubuntu/db_backups/eva4-pre-inventario.sql

sudo systemctl start gunicorn
sudo nginx -t && sudo systemctl reload nginx
curl -i http://localhost/api/v1/health/
```

### Rollback frontend

```bash
sudo cp -a /home/ubuntu/frontend.pre-inventario/. /var/www/buildcorp-frontend/
sudo chown -R www-data:www-data /var/www/buildcorp-frontend
sudo nginx -t && sudo systemctl reload nginx
```

Después de cualquier rollback, verificar health, login, catálogo y endpoints protegidos.

---

## 8. Seguridad y observabilidad

- Autenticación JWT HS256 (`access` 60 min, `refresh` 24 h por defecto).
- Contraseñas hasheadas con PBKDF2 y validadores de Django.
- Auditoría automática de operaciones sobre entidades críticas, con IP detrás de proxy.
- Headers de seguridad en Nginx: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `server_tokens off`.
- RDS con TLS; S3 con AES-256, ACL públicas deshabilitadas y URLs prefirmadas.
- Logs: `/home/ubuntu/apps/backend/logs/gunicorn-access.log` y `gunicorn-error.log`; también `journalctl -u gunicorn`.

---

## 9. Estado operativo recomendado

- Confirmar que el commit pendiente esté pusheado antes de dar por cerrada la entrega.
- No subir frontend a la EC2 backend ni backend a la EC2 frontend.
- Mantener `ALLOWED_HOSTS` y `CORS_ALLOWED_ORIGINS` sincronizados con el dominio y la IP privada del proxy.
- Tras cambios de JS/CSS, actualizar el query string de versión en `index.html`.
