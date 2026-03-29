# NHC To Do Tasks

A Django-based departmental task management system for the National Housing Corporation. The project supports task assignment, self-managed work, staff transparency dashboards, task review, notifications, and operational reporting.

## Core Features
- Role-based access for `manager`, `staff`, and `superuser`
- Task creation for personal work and department assignments
- Task status tracking: pending, in progress, completed, accepted, rejected
- Subtasks, comments, and file attachments
- Staff performance dashboard with section-wide visibility
- Report pages for:
  - My Task Report
  - Assigned Report
  - Overdue Tasks
  - Due Soon Tasks
- Notifications for task assignment and review actions
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
- Sees section dashboard for transparency across fellow staff
- Accesses report pages for personal and assigned task history

### Superuser
- Manages all users
- Can access cross-section staff performance filtering

## Current Dashboard Behavior
- Both manager and staff log in to the dashboard route: `reports_performance`
- Managers see their section dashboard focused on work they assigned
- Staff can see fellow staff in the same section for transparency

## Tech Stack
- Python
- Django 4.2
- SQLite
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
3. Apply migrations:
   ```bash
   python manage.py migrate
   ```
4. Create a superuser if needed:
   ```bash
   python manage.py createsuperuser
   ```
5. Run the development server:
   ```bash
   python manage.py runserver
   ```

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
- Improved the staff performance dashboard with filters and summary metrics
- Made staff dashboard section-transparent
- Added baseline automated tests for login and dashboard behavior

## Suggested Next Improvements
- Add Excel or PDF export for reports
- Add more automated tests for task review and reassignment
- Improve README screenshots and deployment notes
- Add scheduled reminders for due soon and overdue tasks
