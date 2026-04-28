# Software Requirements Specification (SRS)

## Project Title

NHC To Do Tasks

## Document Purpose

This Software Requirements Specification defines the functional and non-functional requirements for the NHC To Do Tasks system. The document is based on the current Django implementation in this repository and is intended to support project understanding, maintenance, handover, testing, and future enhancement.

## 1. Introduction

### 1.1 Purpose of the System

NHC To Do Tasks is a departmental task management system for the National Housing Corporation. The system helps managers assign work to staff, helps staff manage their own and assigned tasks, and provides operational visibility through reports, notifications, and daily accountability tracking.

### 1.2 Scope

The system supports:

- User authentication using Active Directory for normal users
- Local Django authentication for superusers
- Creation of self-assigned tasks
- Manager assignment of tasks to staff in the same section
- Task execution, completion, review, rejection, and reassignment
- File attachments, comments, and subtasks
- In-app notifications
- Daily accountability submissions and manager digest views
- Historical task reporting, including deleted-task records
- User management for managers within their section

### 1.3 Intended Users

- Staff members
- Managers
- System administrators / superusers
- ICT or deployment/support personnel

## 2. Overall Description

### 2.1 Product Perspective

The system is a web-based application built with Django. It uses:

- SQLite for local development
- MySQL for Docker and production-style deployment
- Bootstrap-based server-rendered pages
- Gunicorn for containerized serving
- Environment-based configuration for routing, sessions, database, and authentication

### 2.2 Product Goals

The system is intended to:

- Improve task assignment and follow-up within departments
- Give staff a clear view of their work and deadlines
- Give managers visibility into assigned work and staff performance
- Preserve historical task records for reporting
- Reduce missed deadlines through reminders and review workflows

### 2.3 User Classes and Characteristics

#### Staff

- Can log in through Active Directory when configured
- Can create personal tasks for themselves
- Can work on tasks assigned by managers
- Can submit daily accountability updates
- Can view their own reports and assigned-task history

#### Manager

- Can assign tasks to active staff in the same section
- Can review, reject, or accept completed staff work
- Can reassign tasks within the same section
- Can manage staff accounts in the same section
- Can view overdue, due-soon, and performance reports
- Can view staff daily accountability digests for their section

#### Superuser

- Can log in locally using Django credentials
- Can access Django admin
- Can view cross-section reporting and digest information

### 2.4 Operating Environment

- Python 3.11
- Django 4.2
- Web browser for end users
- SQLite or MySQL database
- Optional Docker Compose deployment
- Application timezone: `Africa/Dar_es_Salaam`

### 2.5 Constraints

- Staff and managers depend on correct Active Directory/LDAP configuration for normal authentication
- URL prefixes are configurable and may not match Django defaults
- Manager task assignment is limited to staff in the same section
- Category-based assignment is enforced for manager-created department tasks

### 2.6 Assumptions and Dependencies

- Active Directory connectivity is available in environments that require staff/manager login
- Required environment variables are configured correctly
- Static and media storage are writable
- MySQL is available when `DJANGO_DB_ENGINE=mysql`

## 3. System Features and Functional Requirements

### 3.1 Authentication and Session Management

#### Description

The system authenticates normal users through Active Directory and allows local password login for superusers.

#### Functional Requirements

- FR-1: The system shall authenticate non-superusers against Active Directory.
- FR-2: The system shall allow local Django-password authentication for superusers.
- FR-3: The system shall deny login when required credentials are missing or invalid.
- FR-4: The system shall display an authentication error message when login fails.
- FR-5: The system shall redirect authenticated users to the staff performance page after login.
- FR-6: The system shall enforce a single active browser/device session per user.
- FR-7: The system shall log out users after a configurable idle timeout.
- FR-8: The system shall disable caching for authenticated application responses.

### 3.2 User and Role Management

#### Description

Managers can manage staff accounts within their own section. Superuser management is handled separately through Django admin.

#### Functional Requirements

- FR-9: The system shall support user roles `manager` and `staff` in the application domain, with superuser privileges provided through Django.
- FR-10: A manager shall be able to create staff accounts in the same section.
- FR-11: A manager shall be able to view and filter staff accounts in the same section.
- FR-12: A manager shall be able to activate or deactivate a staff account in the same section.
- FR-13: A manager shall be able to delete a staff account in the same section.
- FR-14: A manager shall not be allowed to deactivate or delete their own account through the staff-management interface.

### 3.3 Task Creation

#### Description

Users can create tasks. Staff create self-tasks, while managers can create self-tasks or assign departmental tasks to staff.

#### Functional Requirements

- FR-15: The system shall allow authenticated users to create personal tasks assigned to themselves.
- FR-16: The system shall require a task title and due date during creation.
- FR-17: The system shall allow optional task description, priority, category, and file attachments.
- FR-18: A manager shall be able to assign a task to one or more active staff users in the same section.
- FR-19: A manager-assigned task shall require a valid category belonging to the manager's section.
- FR-20: The system shall validate that selected assignees belong to the selected category and section.
- FR-21: The system shall create a `UserTask` assignment record for each assignee.
- FR-22: The system shall generate assignment notifications for staff who receive manager-assigned tasks.

### 3.4 Task Viewing and Lists

#### Description

The system provides separate views for self-created tasks, assigned tasks, and detailed task pages.

#### Functional Requirements

- FR-23: The system shall provide a "My Tasks" view for tasks created by and assigned to the same user.
- FR-24: The system shall provide an "Assigned Tasks" view for manager-to-staff assignments.
- FR-25: The system shall allow filtering task lists by search text, due-date class, status, and review state.
- FR-26: The system shall paginate task list results.
- FR-27: The system shall provide a task detail page showing task metadata, assignees, subtasks, attachments, comments, status, and due-date state.
- FR-28: The system shall allow task detail access only to users related to the task or managers who assigned it.

### 3.5 Task Progress and Completion

#### Description

Assigned users can start work and complete tasks, with validation around subtasks and attachments.

#### Functional Requirements

- FR-29: The system shall allow an assigned user to change a task from `pending` to `in_progress`.
- FR-30: The system shall reset review status to `pending` when a task is started.
- FR-31: The system shall prevent task completion while any related subtasks remain incomplete.
- FR-32: The system shall allow staff completing manager-assigned tasks to upload completion attachments.
- FR-33: The system shall limit completion-time uploads for assigned staff tasks to a maximum of 3 files per completion action.
- FR-34: The system shall mark manager-assigned tasks as completed for the corresponding assignment records when staff complete them.
- FR-35: The system shall record the completing user and completion timestamp.
- FR-36: The system shall notify the assigning manager when a staff member completes a task and it is ready for review.

### 3.6 Subtasks

#### Description

Tasks may include subtasks used to break down work.

#### Functional Requirements

- FR-37: The system shall allow subtasks to be associated with a task.
- FR-38: The system shall allow the subtask creator to retrieve subtask details for editing.
- FR-39: The system shall allow the subtask creator to mark a subtask as completed.
- FR-40: The system shall allow the subtask creator to delete a subtask.
- FR-41: The system shall restrict subtask modification and completion to the creating user.

### 3.7 Task Editing, Deletion, and Reassignment

#### Description

Task owners and assigning managers may update tasks. Managers may also reassign tasks.

#### Functional Requirements

- FR-42: The system shall allow self-task owners to edit their own tasks.
- FR-43: The system shall allow assigning managers to edit tasks they assigned.
- FR-44: The system shall require title and due date when editing a task.
- FR-45: The system shall allow managers to change category and assignees while editing assigned tasks.
- FR-46: The system shall create notifications when task updates affect assigned staff.
- FR-47: The system shall allow a user who assigned a task to delete it.
- FR-48: The system shall preserve deleted-task history in the reporting store before deleting the live task.
- FR-49: The system shall allow only a manager who assigned a task to reassign it.
- FR-50: Reassignment shall be limited to active staff in the same section and selected category.
- FR-51: Reassignment shall reset status to `pending` and review status to `pending`.
- FR-52: The system shall notify both the new assignee and the assigning manager when reassignment occurs.

### 3.8 Review and Comment Workflow

#### Description

Managers review completed assigned tasks and may accept or reject them. Comments support feedback and replies.

#### Functional Requirements

- FR-53: Only a manager who assigned a task shall be able to review it.
- FR-54: The system shall allow a manager to accept completed staff work.
- FR-55: The system shall allow a manager to reject work and return it to `pending`.
- FR-56: The system shall require a rejection reason when rejecting work.
- FR-57: The system shall store the rejection reason as a comment on the task.
- FR-58: The system shall notify assigned staff when work is accepted.
- FR-59: The system shall notify assigned staff when work is rejected.
- FR-60: The system shall allow task comments and threaded replies.
- FR-61: The system shall prevent a user from replying to their own comment.
- FR-62: The system shall restrict task-comment replies to the involved staff member or assigning manager.

### 3.9 Notifications

#### Description

The system includes in-app notifications for task events and reminders.

#### Functional Requirements

- FR-63: The system shall create notifications for task assignment, update, acceptance, rejection, completion-for-review, and reassignment events.
- FR-64: The system shall create due-soon reminders for staff on open assigned tasks approaching the deadline.
- FR-65: The system shall create overdue reminders for staff on open assigned tasks past the deadline.
- FR-66: The system shall create overdue reminders for managers on staff tasks they assigned.
- FR-67: The system shall create review-delay reminders for managers when completed tasks remain pending review beyond the configured threshold.
- FR-68: The system shall limit reminder-type notifications to once per task per user per day.
- FR-69: The system shall allow a user to mark all their notifications as read.
- FR-70: The system shall redirect a user to the notification target page when opening a notification.

### 3.10 Reports and Historical Records

#### Description

The system includes operational reports and preserves historical assignment records, even when tasks are later deleted.

#### Functional Requirements

- FR-71: The system shall provide a reports home page.
- FR-72: The system shall provide a "My Task Report" for self-created tasks.
- FR-73: The system shall provide an "Assigned Task Report" for assignment history.
- FR-74: The system shall preserve task history in a reporting table separate from live task records.
- FR-75: The system shall support filtering historical records by date range, status, deleted state, and keyword.
- FR-76: The system shall show deleted-task records in report history when available.
- FR-77: The system shall provide an overdue tasks report for managers.
- FR-78: The system shall provide a due-soon report for managers.

### 3.11 Staff Performance Dashboard

#### Description

The system computes section or global staff performance summaries based on assigned-task outcomes.

#### Functional Requirements

- FR-79: The system shall provide a staff performance dashboard after login.
- FR-80: Managers shall see staff performance for their own section.
- FR-81: Staff shall see staff performance for their own section.
- FR-82: Superusers shall be able to view staff performance across sections.
- FR-83: The system shall support filtering the performance dashboard by created-date range, section, and staff type.
- FR-84: The system shall calculate total, completed, pending, overdue, rejected, on-time completed, and late completed task counts.
- FR-85: The system shall calculate completion rate, on-time rate, and performance score per staff member.
- FR-86: The system shall rank staff by performance score, on-time rate, completed tasks, and lower overdue count.

### 3.12 Daily Accountability

#### Description

Staff submit daily check-ins, while managers and superusers monitor the daily digest.

#### Functional Requirements

- FR-87: The system shall provide a daily accountability board for staff users.
- FR-88: The system shall allow a staff user to save a daily check-in draft.
- FR-89: The system shall allow a staff user to submit a daily check-in.
- FR-90: A daily check-in shall be unique per user per date.
- FR-91: A daily check-in may include selected priority tasks, morning focus, progress update, blockers, end-of-day summary, tomorrow plan, and proof file.
- FR-92: The system shall prevent submission of an empty daily check-in.
- FR-93: The system shall notify section managers when a staff member submits a daily check-in.
- FR-94: The system shall provide a daily digest view for managers for their section.
- FR-95: The system shall provide a cross-section daily digest for superusers.
- FR-96: The daily digest shall identify submitted users, blockers, silent users, and same-day completed-task counts.
- FR-97: The system shall provide a daily check-in detail view for managers and superusers.

## 4. Business Rules

- BR-1: Managers may assign or reassign tasks only within their own section.
- BR-2: Only active staff users are eligible for assignment or reassignment.
- BR-3: Manager-assigned tasks use category membership to determine valid assignees.
- BR-4: Self-tasks are created by assigning the same user as both assigner and assignee.
- BR-5: A task cannot be completed until all subtasks are completed.
- BR-6: Rejected assigned work returns to a pending state.
- BR-7: Reminder notifications for due soon, overdue, and delayed review are generated no more than once per task per day.
- BR-8: Historical reporting must continue to show task records even after the live task is deleted.
- BR-9: Session protection allows only one active session per user at a time.
- BR-10: Application date-sensitive logic uses the Tanzania timezone.

## 5. Data Requirements

### 5.1 Core Entities

- `User`: stores username, email, section, role, staff type, and active/staff/superuser flags
- `UserSession`: stores the active session key per user
- `Category`: groups staff membership by section
- `CategoryMember`: maps users into categories
- `Task`: stores title, description, due date, priority, attachments, completion metadata, and category
- `UserTask`: stores assignment relationship, task status, review status, assigner, assignee, and completion timestamp
- `SubTask`: stores subtask items under a task
- `Comment`: stores task comments and replies
- `TaskAttachment`: stores uploaded files for a task
- `Notification`: stores in-app notifications and read state
- `TaskReportRecord`: stores historical task-report snapshots, including deleted state
- `DailyCheckIn`: stores daily accountability content and selected priority tasks

### 5.2 Status Values

#### Task assignment status

- `pending`
- `in_progress`
- `completed`
- `overdue`
- `rejected`
- `accepted`

#### Review status

- `pending`
- `accepted`
- `rejected`

#### Task priority

- `normal`
- `high`

## 6. External Interface Requirements

### 6.1 User Interface

- The system shall provide browser-based pages for login, task lists, task details, reports, daily accountability, and user management.
- The system shall provide separate views for self-tasks, assigned tasks, reports, and daily accountability.
- The system shall display in-app notifications in the user interface.

### 6.2 Software Interfaces

- Active Directory / LDAP for normal user authentication
- SQLite for local development
- MySQL for Docker and production-style deployment
- Django admin for superuser administration

### 6.3 Deployment Interfaces

- Environment variables for all key settings
- Docker Compose for `web` and `db` services
- Gunicorn as the WSGI server in containers

## 7. Non-Functional Requirements

### 7.1 Security

- NFR-1: The system shall require authentication for protected application pages.
- NFR-2: The system shall enforce role-based access to task, report, and user-management features.
- NFR-3: The system shall enforce a single active session per user.
- NFR-4: The system shall support session idle timeout using configurable settings.
- NFR-5: The system shall prevent client-side caching of authenticated responses.
- NFR-6: The system shall use configurable route prefixes for login, task, and admin access paths.

### 7.2 Reliability and Data Integrity

- NFR-7: The system shall preserve report snapshots when live tasks are edited, reassigned, or deleted.
- NFR-8: The system shall validate required inputs before creating or updating task records.
- NFR-9: The system shall enforce one daily check-in per user per day.

### 7.3 Usability

- NFR-10: The system shall provide feedback messages for successful and failed actions.
- NFR-11: The system shall present filters and paginated task lists to improve navigation.

### 7.4 Maintainability

- NFR-12: The system shall use environment-driven configuration to support local, Docker, and deployed environments.
- NFR-13: The codebase shall remain organized by Django app responsibilities such as `accounts` and `tasks`.

### 7.5 Portability

- NFR-14: The system shall run locally with SQLite and in containers with MySQL.
- NFR-15: The system shall support deployment through Docker Compose.

## 8. Out of Scope

The current implementation does not define the following as formal in-scope requirements:

- Email notifications
- Mobile application clients
- Public APIs for third-party integration
- Multi-language localization
- Advanced analytics beyond the implemented reports

## 9. Acceptance Summary

The system shall be considered aligned with this SRS when:

- Users can authenticate according to their role and environment
- Managers can assign, review, and reassign staff work within section rules
- Staff can manage self-tasks, complete assigned tasks, and submit daily accountability updates
- Notifications and reports behave as documented
- Historical task records remain available even after live deletion
- Session and access-control rules are enforced

## 10. Related Project Documents

- [README.md](../README.md)
- [docs/ci-cd.md](./ci-cd.md)
