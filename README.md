# NHC To Do Tasks

NHC To Do Tasks is a Django web application for managing department work inside the National Housing Corporation. It helps managers assign tasks, helps staff track progress, and provides reports, notifications, and daily accountability tools.

## What the system does

- Lets managers assign work to staff in the same section
- Lets staff create and manage their own personal tasks
- Tracks task progress from pending to completion and review
- Supports subtasks, comments, and file attachments
- Shows staff performance and task history reports
- Sends in-app notifications for assignments, deadlines, reviews, and reassignments
- Includes a daily accountability board and daily digest views

## User roles

### Manager
- Create tasks for staff
- Review completed work
- Monitor section performance
- Manage users in the same section

### Staff
- Create personal tasks
- Work on assigned tasks
- View reports and daily accountability pages

### Superuser
- Access Django admin
- Manage all users
- Log in locally with a Django password even if Active Directory is unavailable

## Main technology

- Python 3.11
- Django 4.2
- SQLite for local development
- MySQL 8.4 for Docker or production-style deployment
- Bootstrap 5
- Gunicorn
- Docker Compose

## Project structure

- `accounts/` - authentication, user model, user management
- `tasks/` - task workflow, reports, notifications, daily board
- `templates/` - shared templates
- `static/` - images and static files
- `media/` - uploaded files
- `docs/` - deployment and CI/CD notes
- `scripts/` - helper scripts

## Quick start for local development

This is the easiest way to run the project on your computer. Local development uses SQLite by default, so you do not need MySQL.

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create the environment file

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```bash
cp .env.example .env
```

The default `.env.example` already uses SQLite:

```env
DJANGO_DB_ENGINE=sqlite
SQLITE_PATH=db.sqlite3
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create a superuser

```bash
python manage.py createsuperuser
```

This superuser can log in with a normal Django username and password.

### 6. Start the development server

```bash
python manage.py runserver
```

Open the app in your browser:

- Login page: `http://127.0.0.1:8000/ict-todolist/`
- Admin page: `http://127.0.0.1:8000/welcome-admin/`

## Login behavior

The project uses two authentication paths:

- Normal users authenticate through Active Directory
- Superusers authenticate locally with Django credentials

For local development, the simplest option is:

1. Create a superuser
2. Log in with that superuser account

If Active Directory is not configured, normal staff and manager AD login will not work until the LDAP settings are filled in.

## Important environment variables

### General Django settings

- `DJANGO_SECRET_KEY` - secret key for Django
- `DJANGO_DEBUG` - `True` or `False`
- `DJANGO_ALLOWED_HOSTS` - comma-separated hosts

### Database

For SQLite:

```env
DJANGO_DB_ENGINE=sqlite
SQLITE_PATH=db.sqlite3
```

For MySQL:

```env
DJANGO_DB_ENGINE=mysql
MYSQL_DATABASE=nhctodo
MYSQL_USER=nhctodo
MYSQL_PASSWORD=your-password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

### Session settings

- `SESSION_COOKIE_AGE`
- `SESSION_IDLE_TIMEOUT_SECONDS`

### URL prefixes

The app hides the default-looking routes by using configurable URL prefixes.

```env
DJANGO_ADMIN_URL_PREFIX=welcome-admin
DJANGO_ACCOUNTS_URL_PREFIX=ict-todolist
DJANGO_TASKS_URL_PREFIX=ict-todolist
```

With the default values:

- Login page: `/ict-todolist/`
- Reports home: `/ict-todolist/reports/`
- Staff performance: `/ict-todolist/reports/staff-performance/`
- My tasks: `/ict-todolist/mytasks/`
- Assigned tasks: `/ict-todolist/assigned/`
- Create task: `/ict-todolist/create/`
- Admin: `/welcome-admin/`

### Active Directory settings

These are required for staff and manager AD login:

- `AD_SERVER_URI`
- `AD_PORT`
- `AD_BASE_DN`
- `AD_BIND_USER`
- `AD_BIND_PASSWORD`
- `AD_USERNAME_ATTR`
- `AD_TIMEOUT`
- `AD_AUTO_CREATE_USERS`
- `AD_DEFAULT_ROLE`
- `AD_DEFAULT_SECTION`
- `AD_DEFAULT_STAFF_TYPE`
- `AD_EMAIL_DOMAIN`

## Running with Docker Compose

Use Docker if you want a production-style setup with MySQL and Gunicorn.

### 1. Create the Docker environment file

```bash
cp .env.docker.example .env.docker
```

On Windows PowerShell:

```powershell
Copy-Item .env.docker.example .env.docker
```

### 2. Update the required values

At minimum, set these before starting:

- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `AD_BIND_PASSWORD`

### 3. Start the containers

```bash
docker compose up --build -d
```

### 4. Check container status

```bash
docker compose ps
docker compose logs -f web
```

### What Docker starts

- `db` - MySQL 8.4
- `web` - Django app running with Gunicorn

The container entrypoint automatically:

- waits for the database
- runs `python manage.py migrate`
- runs `python manage.py collectstatic`
- starts Gunicorn on port `8000` by default

Persistent data is stored in these Docker volumes:

- `mysql_data`
- `media_data`
- `static_data`

## Useful commands

Run system checks:

```bash
python manage.py check
```

Run tests:

```bash
python manage.py test
```

Validate Docker Compose configuration:

```bash
docker compose config
```

## CI/CD

GitHub Actions is used for validation on pushes and pull requests, and deployment is triggered from `main` using a self-hosted runner.

More details are in [docs/ci-cd.md](docs/ci-cd.md).

## Current limitations

- Active Directory login will not work until the LDAP settings are configured correctly
- Local development is easiest with a superuser account instead of AD login
- CI currently focuses on Django checks; test coverage can still be expanded
