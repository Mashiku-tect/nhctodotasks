# NHC To Do Tasks

A Django-based departmental task management system for the National Housing Corporation. The project supports task assignment, self-managed work, fair staff dashboards, task review, notifications, and operational reporting.

## Core Features
- Role-based access for `manager`, `staff`, and `superuser`
- Task creation for personal work and department assignments
- Task status tracking: pending, in progress, completed, accepted, rejected
- Subtasks, comments, and file attachments
- Staff performance dashboard with section-wide visibility for manager-assigned work
- Report pages for:
  - My Task Report
  - Assigned Report
  - Overdue Tasks
  - Due Soon Tasks
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

## Current Dashboard Behavior
- Both manager and staff log in to the dashboard route: `reports_performance`
- Managers see their section dashboard focused on work they assigned
- Staff can see fellow staff in the same section for transparency
- Shared ranking is based only on manager-assigned tasks
- Self-created tasks are excluded from the shared performance dashboard
- Fresh pending tasks do not reduce ranking until they become overdue or are completed late

## Performance Ranking Calculation
- Shared ranking uses only manager-assigned tasks
- Self-created tasks are excluded from section ranking
- Ranking is driven by a fair `performance_score`
- Fresh pending tasks do not lower a staff member's rank
- Tasks start affecting ranking when they are:
  - completed on time
  - completed late
  - overdue and still open
  - rejected after review
- The current score gives:
  - full weight to on-time completed tasks
  - reduced weight to late completed tasks
  - no positive credit to overdue or rejected tasks
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
- Notifications appear in the in-app header notification menu
- Due soon, overdue, and review-delay reminders are generated in-app and limited to once per day per task
- Action-based notifications are created immediately when the related event happens

## Tech Stack
- Python
- Django 4.2
<<<<<<< HEAD
- SQLite for local fallback
- MySQL for production
=======
- SQLite
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222
- Bootstrap 5

## Project Structure
- `accounts/` : authentication, user model, user management
- `tasks/` : task workflows, reports, notifications, dashboard logic
- `templates/` : shared base templates
- `static/` : static assets
- `media/` : uploaded files

## Local Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
<<<<<<< HEAD
3. For local SQLite development, no database server is required.
4. For MySQL, create a `.env` from `.env.example` and update the MySQL values.
5. Apply migrations:
   ```bash
   python manage.py migrate
   ```
6. Create a superuser if needed:
   ```bash
   python manage.py createsuperuser
   ```
7. Run the development server:
=======
3. Apply migrations:
   ```bash
   python manage.py migrate
   ```
4. Create a superuser if needed:
   ```bash
   python manage.py createsuperuser
   ```
5. Run the development server:
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222
   ```bash
   python manage.py runserver
   ```

<<<<<<< HEAD
## Database Configuration
The project now supports two database modes through environment variables:

- SQLite fallback for local development:
  - `DJANGO_DB_ENGINE=sqlite` or leave it unset
  - Optional: `SQLITE_PATH=/path/to/db.sqlite3`
- MySQL for production:
  - `DJANGO_DB_ENGINE=mysql`
  - `MYSQL_DATABASE`
  - `MYSQL_USER`
  - `MYSQL_PASSWORD`
  - `MYSQL_HOST`
  - `MYSQL_PORT`

Example production environment:
```env
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DJANGO_DB_ENGINE=mysql
MYSQL_DATABASE=nhctodo
MYSQL_USER=nhctodo
MYSQL_PASSWORD=strong-password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

## Docker Production Setup
The included `docker-compose.yml` now starts:

- `db`: MySQL 8.4
- `web`: Django + Gunicorn configured to use MySQL

Before deploying:

1. Copy `.env.docker.example` to `.env.docker`
2. Change these values in `.env.docker`:
   - `MYSQL_PASSWORD`
   - `MYSQL_ROOT_PASSWORD`
   - `DJANGO_SECRET_KEY`
   - `DJANGO_ALLOWED_HOSTS`

Then run:
```bash
docker compose up --build -d
```

=======
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222
## Important URLs
- Login: `/accounts/login/`
- Dashboard: `/tasks/reports/staff-performance/`
- Reports Home: `/tasks/reports/`
- My Tasks: `/tasks/mytasks/`
- Assigned Tasks: `/tasks/assigned/`
- Create Task: `/tasks/create/`

## Test Commands
Run the checks:
```bash
python manage.py check
```

Run tests:
```bash
python manage.py test
```

## Recent Cleanup Completed
- Removed duplicate `Category` model definition
- Fixed conflicting task routes by giving `do_task` its own URL
- Added a dedicated reports landing page
- Improved the staff performance dashboard with fairer ranking based on manager-assigned work only
- Added in-app notifications for due soon, overdue, review, acceptance, rejection, updates, and reassignment
- Made staff dashboard section-transparent
- Added automated tests for dashboard fairness and visibility behavior

## Suggested Next Improvements
- Add Excel or PDF export for reports
- Add more automated tests for task review and reassignment
- Improve README screenshots and deployment notes
- Add background scheduling so reminder notifications can be pushed even when users are not currently opening the app
