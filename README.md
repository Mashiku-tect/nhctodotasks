# NHC To Do Tasks

A Django-based departmental task management system for the National Housing Corporation. The project supports task assignment, self-managed work, fair staff dashboards, task review, notifications, and operational reporting.

## Core Features
- Role-based access for `manager`, `staff`, and `superuser`
- Task creation for personal work and department assignments
- Task status tracking: pending, in progress, completed, accepted, rejected
- Subtasks, comments, and file attachments
- Staff performance dashboard with section-wide visibility for manager-assigned work
- Report pages for My Tasks, Assigned Tasks, Overdue Tasks, and Due Soon Tasks
- In-app notifications for assignment, deadline reminders, review, and reassignment
- User management for managers and superusers

## User Roles
### Manager
- Creates and assigns tasks to staff in the same section
- Reviews completed staff work
- Monitors section dashboard and report pages
- Manages staff accounts in their section

### Staff
- Creates personal tasks
- Works on assigned tasks
- Sees section dashboard for transparency across fellow staff based on assigned work
- Accesses report pages for personal and assigned task history

### Superuser
- Manages all users
- Can access cross-section staff performance filtering
- Can log in locally even when Active Directory is unavailable

## Dashboard and Ranking Behavior
- Both managers and staff land on the `reports_performance` dashboard after login
- Shared ranking uses only manager-assigned tasks
- Self-created tasks are excluded from shared ranking
- Fresh pending tasks do not reduce ranking until they become overdue or are completed late
- Ranking order is based on:
  - `performance_score`
  - `on_time_rate`
  - `completed_tasks`
  - fewer overdue tasks

## In-App Notifications
### Staff Notifications
- New task assigned
- Task due soon
- Task overdue
- Task updated
- Task accepted
- Task rejected with reason

### Manager Notifications
- Task completed and waiting for review
- Assigned task overdue
- Task reassigned
- Review pending too long

### Notification Behavior
- Notifications appear in the header notification menu
- Due-soon, overdue, and review-delay reminders are generated in-app and limited to once per day per task
- Action-based notifications are created immediately when the related event happens

## Tech Stack
- Python 3.11
- Django 4.2
- SQLite for local development
- MySQL 8.4 for containerized and production deployment
- Bootstrap 5
- Docker Compose

## Project Structure
- `accounts/`: authentication, custom user model, user management
- `tasks/`: task workflows, reports, notifications, dashboard logic
- `templates/`: shared base templates
- `static/`: static assets
- `media/`: uploaded files
- `docs/`: deployment and workflow notes
- `scripts/`: deployment scripts

## Local Setup

### Prerequisites
- Python 3.11
- `pip`
- Optional: a virtual environment tool such as `venv`

### 1. Create and activate a virtual environment
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

### 3. Create a local environment file
Copy `.env.example` to `.env` and adjust values only if needed.

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

macOS or Linux:
```bash
cp .env.example .env
```

The default `.env.example` uses SQLite, so no database server is required for local development.

### 4. Apply migrations
```bash
python manage.py migrate
```

### 5. Create a superuser
```bash
python manage.py createsuperuser
```

### 6. Run the development server
```bash
python manage.py runserver
```

## Environment Configuration

### Local SQLite mode
Use SQLite for local development:

```env
DJANGO_DB_ENGINE=sqlite
SQLITE_PATH=db.sqlite3
```

If `DJANGO_DB_ENGINE` is unset, the project defaults to SQLite.

### MySQL mode
Use MySQL when deploying outside Docker or when matching production locally:

```env
DJANGO_DB_ENGINE=mysql
MYSQL_DATABASE=nhctodo
MYSQL_USER=nhctodo
MYSQL_PASSWORD=strong-password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

Other important environment variables:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `SESSION_COOKIE_AGE`
- `SESSION_IDLE_TIMEOUT_SECONDS`
- `AD_SERVER_URI`
- `AD_BIND_USER`
- `AD_BIND_PASSWORD`

## Docker Deployment
The included `docker-compose.yml` starts:

- `db`: MySQL 8.4
- `web`: Django + Gunicorn configured to use MySQL

### Deploy with Docker Compose
1. Copy `.env.docker.example` to `.env.docker`
2. Update at least these values in `.env.docker`:
   - `MYSQL_PASSWORD`
   - `MYSQL_ROOT_PASSWORD`
   - `DJANGO_SECRET_KEY`
   - `DJANGO_ALLOWED_HOSTS`
   - `AD_BIND_PASSWORD`
3. Make sure Docker Engine and the Docker Compose plugin are installed on the server
4. Start the stack:

```bash
docker compose up --build -d
```

Useful follow-up commands:
```bash
docker compose ps
docker compose logs -f web
```

Notes:
- The MySQL container is exposed only to other Docker services by default
- Persistent data is stored in Docker volumes: `mysql_data`, `media_data`, and `static_data`
- The container entrypoint automatically runs `migrate` and `collectstatic`

## Route Hardening
Public route prefixes are configurable so the app does not have to expose predictable paths like `/accounts/login/` or `/tasks/...`.

Set these in `.env` or `.env.docker` for deployment:

```env
DJANGO_ADMIN_URL_PREFIX=welcome-admin
DJANGO_ACCOUNTS_URL_PREFIX=ict-todolist
DJANGO_TASKS_URL_PREFIX=ict-todolist
```

Example resulting URLs:
- Login: `/ict-todolist/`
- Dashboard: `/ict-todolist/reports/staff-performance/`
- Reports Home: `/ict-todolist/reports/`
- My Tasks: `/ict-todolist/mytasks/`
- Assigned Tasks: `/ict-todolist/assigned/`
- Create Task: `/ict-todolist/create/`

## Validation and Tests
Run Django system checks:
```bash
python manage.py check
```

Run the test suite:
```bash
python manage.py test
```

If you are using Docker for deployment, validate the containerized stack with:
```bash
docker compose config
docker compose up --build
```

## CI/CD
GitHub Actions currently validates the app on pushes and pull requests and triggers deployment on `main` using a self-hosted runner.

See [docs/ci-cd.md](/d:/NHC%20DJANGO%20PROJECTS/nhctodotasks-main/docs/ci-cd.md) for deployment details.

## Current Limitations
- Active Directory-backed login needs environment-specific LDAP settings before it can work outside local superuser login
- The local environment must have project dependencies installed before `manage.py` commands will run
- CI currently runs `python manage.py check`; expanding it to run tests is a recommended next step once the environment is stable
