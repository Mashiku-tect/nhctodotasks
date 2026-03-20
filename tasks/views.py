import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import Task, UserTask,SubTask,Comment,TaskAttachment
from django.utils import timezone
from django.http import HttpResponseForbidden,JsonResponse
from django.db.models import Q
from collections import defaultdict
from django.views.decorators.http import require_POST
import os
from django.utils import timezone
import pytz
from django.core.paginator import Paginator
from datetime import date

tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
today = timezone.now().astimezone(tanzania_tz).date()


User = get_user_model()

def compute_task_status(usertasks):
    statuses = {ut.status for ut in usertasks}

    if statuses == {'completed'}:
        return 'completed'
    elif statuses == {'rejected'}:
        return 'rejected'
    elif statuses == {'in_progress'}:
        return 'in_progress'
    else:
        return 'pending'



@login_required
def create_task(request):
    user = request.user
    subordinates = []

    if user.role == 'manager':
        subordinates = User.objects.filter(
            section=user.section,
            role='staff',
            is_active=True
        )

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '')
        attachment = request.FILES.get("attachment")
        due_date = request.POST.get('due_date')
        priority = request.POST.get('priority', 'normal')

        if not title or not due_date:
            return JsonResponse(
                {'error': 'Title and due date are required.'},
                status=400
            )

        assigned_users = [user]  # default assignment: self
        messages.success(request, "Task created successfully!")
        redirect_url = '/tasks/mytasks/'  # default redirect for staff or manager self-task

        if user.role == 'manager':
            task_type = request.POST.get('task_type')

            if task_type == 'assign':
                user_ids = request.POST.getlist('assigned_to[]')
                assigned_users = User.objects.filter(
                    id__in=user_ids,
                    section=user.section,
                    role='staff',
                    is_active=True
                )

                if not assigned_users.exists():
                    return JsonResponse(
                        {'error': 'Please select at least one valid staff member.'},
                        status=400
                    )

                # If manager is assigning to others, redirect to assigned_tasks
                
                redirect_url = '/tasks/assigned/'

        task = Task.objects.create(
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            attachment=attachment
        )

        UserTask.objects.bulk_create([
            UserTask(
                task=task,
                assigned_by=user,
                assigned_to=assignee,
                status='pending'
            )
            for assignee in assigned_users
        ])

        return JsonResponse({
            'message': 'Task created successfully!',
            'redirect_url': redirect_url
        })

    return render(
        request,
        'tasks/create_task.html',
        {
            'subordinates': subordinates,
            'PRIORITY_CHOICES': Task.PRIORITY_CHOICES,
        }
    )


#get users Mytasks(his/her own tasks)
@login_required
def my_tasks(request):
    user = request.user
    query = request.GET.get('q', '')

    my_usertasks = UserTask.objects.filter(
        assigned_by=user,
        assigned_to=user,
        task__title__icontains=query
    ).select_related('task').order_by('-created_at')

    tasks_list = [ut.task for ut in my_usertasks]

    # ✅ CHANGE HERE (10 per page)
    paginator = Paginator(tasks_list, 10)

    page_number = request.GET.get('page')
    tasks = paginator.get_page(page_number)

    return render(request, 'tasks/my_tasks.html', {
        'tasks': tasks
    })


@login_required
def assigned_tasks(request):
    user = request.user
    status_filter = request.GET.get('status')
    review_filter = request.GET.get('review')
    due_filter = request.GET.get('due')
    search_query = request.GET.get('q')

    # ✅ 1. FIRST define queryset
    if user.role == 'staff':
        visible_qs = (
            UserTask.objects
            .select_related('task', 'assigned_by', 'assigned_to')
            .filter(assigned_to=user)
            .exclude(assigned_by=user)
        )
    else:
        visible_qs = (
            UserTask.objects
            .select_related('task', 'assigned_by', 'assigned_to')
            .filter(assigned_by=user)
            .exclude(assigned_to=user)
        )

    # ✅ 2. THEN apply filters
    from datetime import date

    if search_query:
        visible_qs = visible_qs.filter(task__title__icontains=search_query)

    if due_filter == 'today':
        visible_qs = visible_qs.filter(task__due_date=date.today())
    elif due_filter == 'overdue':
        visible_qs = visible_qs.filter(task__due_date__lt=date.today())
    elif due_filter == 'upcoming':
        visible_qs = visible_qs.filter(task__due_date__gt=date.today())

    grouped_tasks = defaultdict(list)
    for ut in visible_qs:
        grouped_tasks[ut.task].append(ut)

    task_list = []
    for task in grouped_tasks.keys():
        all_usertasks = (
            task.user_tasks
            .select_related('assigned_to', 'assigned_by')
            .exclude(Q(assigned_to=user) & Q(assigned_by=user))
        )

        own_usertask = all_usertasks.filter(assigned_to=user).first()
        computed_status = compute_task_status(all_usertasks)

        # Days left & overdue
        days_left = (task.due_date - date.today()).days
        is_overdue = False
        reassign_needed = False
        if days_left < 0 and computed_status in ['pending', 'in_progress']:
            is_overdue = True
            reassign_needed = True  # flag for manager to reassign
            days_left = 0

        # Deadline progress
        start_date = task.created_at.date()
        end_date = task.due_date
        total_days = (end_date - start_date).days
        days_passed = (date.today() - start_date).days
        deadline_progress = min(max(int((days_passed / total_days) * 100), 0), 100) if total_days > 0 else 100

        task_dict = {
            "task": task,
            "usertasks": all_usertasks,
            "own_usertask": own_usertask,
            "computed_status": computed_status,
            "days_left": days_left,
            "is_overdue": is_overdue,
            "reassign_needed": reassign_needed,
            "deadline_progress": deadline_progress
        }

        task_list.append(task_dict)

    # Pagination
    paginator = Paginator(task_list, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'tasks/assigned_tasks.html', {
        'task_list': page_obj,
        'page_obj': page_obj
    })

@login_required
def reassign_task(request, task_id):
    task = Task.objects.get(id=task_id)

    if request.user.role != 'manager':
        return redirect('assigned_tasks')

    if request.method == 'POST':
        new_user_id = request.POST.get('assigned_to')
        new_user = User.objects.get(id=new_user_id)

        # Find existing usertask for this task
        existing_usertask = UserTask.objects.filter(task=task, assigned_to__in=[new_user, request.user]).first()

        if existing_usertask:
            # Update existing usertask
            existing_usertask.assigned_to = new_user
            existing_usertask.status = 'pending'
            existing_usertask.review_status = 'pending'
            existing_usertask.save()
        else:
            # Create new assignment
            UserTask.objects.create(
                task=task,
                assigned_by=request.user,
                assigned_to=new_user,
                status='pending',
                review_status='pending'
            )

        return redirect('assigned_tasks')

    # GET request: show manager a dropdown to select user
    staff_users = User.objects.filter(role='staff')
    return render(request, 'tasks/reassign_task.html', {
        'task': task,
        'staff_users': staff_users
    })

#dashboard view
@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()  # Tanzanian date if timezone set

    if user.role == "manager":
        # Tasks assigned to staff in this manager's section
        section_staff_tasks = UserTask.objects.filter(
            assigned_to__role='staff',
            assigned_to__section=user.section
        )

        my_open_tasks_count = section_staff_tasks.exclude(status__in=['completed', 'rejected']).count()
        overdue_tasks_count = section_staff_tasks.filter(
            task__due_date__lt=today
        ).exclude(status__in=['completed', 'rejected']).count()

        rejected_tasks_count = UserTask.objects.filter(
            assigned_by=request.user,
            review_status='rejected'
        ).count()

        completed_tasks_count = section_staff_tasks.filter(status='completed').count()

    else:
        # Staff sees only their own tasks
        my_open_tasks_count = UserTask.objects.filter(
            assigned_to=user
        ).exclude(status__in=['completed', 'rejected']).count()

        overdue_tasks_count = UserTask.objects.filter(
            assigned_to=user,
            task__due_date__lt=today
        ).exclude(status__in=['completed', 'rejected']).count()

        rejected_tasks_count = UserTask.objects.filter(
        assigned_to=request.user,
        review_status='rejected'
         ).count()

        completed_tasks_count = UserTask.objects.filter(
            assigned_to=user,
            status='completed'
        ).count()

    return render(request, "tasks/dashboard.html", {
        'my_open_tasks_count': my_open_tasks_count,
        'overdue_tasks_count': overdue_tasks_count,
        'rejected_tasks_count': rejected_tasks_count,
        'completed_tasks_count': completed_tasks_count,
    })


# view task details function
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # Only get a UserTask for the current user if they are staff
    user_task = UserTask.objects.filter(task=task, assigned_to=request.user).first()

    # Managers can view any task
    if request.user.role != 'manager' and not user_task:
        return HttpResponseForbidden("You are not assigned to this task.")

    # Flags for staff users
    is_my_task = False
    is_assigned_task = False
    task_completed = False
    task_accepted = False

    if user_task:
        is_my_task = user_task.assigned_by == request.user and user_task.assigned_to == request.user
        is_assigned_task = user_task.assigned_to == request.user and user_task.assigned_by != request.user
        task_completed = user_task.status == 'completed'
        task_accepted = user_task.status == 'accepted'

    # SUBTASKS
    subtasks = task.subtasks.all()
    for subtask in subtasks:
        subtask.is_completed = subtask.status == 'completed'

    incomplete_subtasks = subtasks.exclude(status='completed').exists()

    # COMMENTS (for assigned tasks)
    comments = []
    if is_assigned_task:
        comments = (
            Comment.objects.filter(task=task, parent__isnull=True)
            .select_related('user')
            .prefetch_related('replies')
        )

    # Only users who assigned the task can delete
    can_delete = UserTask.objects.filter(task=task, assigned_by=request.user).exists()

    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'can_delete': can_delete,
        'task_completed': task_completed,
        'subtasks': subtasks,
        'incomplete_subtasks': incomplete_subtasks,
        'is_my_task': is_my_task,
        'is_assigned_task': is_assigned_task,
        'comments': comments,
        'task_accepted': task_accepted,
    })




#get subtask for populating the modal
@login_required
def subtask_json(request, subtask_id):
    subtask = get_object_or_404(SubTask, id=subtask_id)

    if subtask.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    return JsonResponse({
        'id': subtask.id,
        'title': subtask.title,
        'description': subtask.description,
    })




#start a task
@login_required
def start_task(request, usertask_id):
    ut = get_object_or_404(UserTask, id=usertask_id, assigned_to=request.user)
    ut.status = 'in_progress'
    ut.review_status = 'pending'   # reset review status
    ut.save()

    # Conditional redirect
    if ut.assigned_to == ut.assigned_by:
        return redirect('my_tasks')          # my own task
    else:
        return redirect('assigned_tasks')    # task assigned by someone else


#complete a subtask
@login_required
def complete_subtask(request, subtask_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    subtask = get_object_or_404(SubTask, id=subtask_id)

    if subtask.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    subtask.status = 'completed'
    subtask.save()

    return JsonResponse({'success': True})



#complete tasks*validate subtasks)
@login_required
def complete_task(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    task = get_object_or_404(Task, id=task_id)

    user_task = get_object_or_404(
        UserTask,
        task=task,
        assigned_to=request.user
    )

    if task.subtasks.exclude(status='completed').exists():
        return JsonResponse(
            {'error': 'Complete all subtasks first.'},
            status=400
        )

    is_assigned_task = (
        user_task.assigned_to == request.user and
        user_task.assigned_by != request.user
    )

    if is_assigned_task:
        files = request.FILES.getlist('attachments')

        if len(files) > 3:
            return JsonResponse(
                {'error': 'Maximum 3 attachments allowed.'},
                status=400
            )

        allowed_extensions = {'.pdf', '.jpeg', '.jpg', '.png'}
        allowed_mime_types = {
            'application/pdf',
            'image/jpeg',
            'image/png',
        }

        for f in files:
            ext = os.path.splitext(f.name)[1].lower()

            if ext not in allowed_extensions:
                return JsonResponse(
                    {'error': f'Invalid file type: {f.name}'},
                    status=400
                )

            if f.content_type not in allowed_mime_types:
                return JsonResponse(
                    {'error': f'Invalid file content: {f.name}'},
                    status=400
                )

            TaskAttachment.objects.create(
                task=task,
                uploaded_by=request.user,
                file=f
            )

    user_task.status = 'completed'
    user_task.save()

    return JsonResponse({'success': True})





#delete a task
@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if not UserTask.objects.filter(
        task=task,
        assigned_by=request.user
    ).exists():
        return HttpResponseForbidden("You cannot delete this task.")

    task.delete()
    messages.success(request, "Task deleted successfully.")
    return redirect('my_tasks')



#edit task
@login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.priority = request.POST.get('priority')

    # ✅ Permission: must be the assigner (my task OR manager-assigned task)
    if not UserTask.objects.filter(
        task=task,
        assigned_by=request.user
    ).exists():
        return HttpResponseForbidden("You cannot edit this task.")

    # Subordinates (only for managers)
    subordinates = []
    if request.user.role == 'manager':
        subordinates = User.objects.filter(
            section=request.user.section,
            role='staff',
            is_active=True
        )

    # ✅ FIXED: Current assignees (exclude self)
    current_assignees = User.objects.filter(
        tasks_received__task=task,
        tasks_received__assigned_by=request.user
    ).exclude(id=request.user.id)

    if request.method == 'POST':
        task.title = request.POST.get('title')
        task.description = request.POST.get('description')
        task.due_date = request.POST.get('due_date')

        if not task.title or not task.due_date:
            messages.error(request, "Title and due date are required.")
            return redirect('edit_task', task_id=task.id)

        task.save()

        # 🔁 Handle reassignment (manager only)
        if request.user.role == 'manager':
            selected_user_ids = request.POST.getlist('assigned_to')

            # Remove old staff assignments (keep self-task if exists)
            UserTask.objects.filter(
                task=task,
                assigned_by=request.user
            ).exclude(assigned_to=request.user).delete()

            # Add new assignments
            for uid in selected_user_ids:
                UserTask.objects.get_or_create(
                    task=task,
                    assigned_by=request.user,
                    assigned_to_id=uid,
                    defaults={'status': 'pending'}
                )

        messages.success(request, "Task updated successfully.")
        return redirect('assigned_tasks')

    return render(request, 'tasks/edit_task.html', {
        'task': task,
        'subordinates': subordinates,
        'current_assignees': current_assignees,
        'PRIORITY_CHOICES': Task.PRIORITY_CHOICES,
    })


#edit subtask
@login_required
def ajax_save_subtask(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    subtask_id = request.POST.get('id')
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '')

    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)

    if subtask_id:
        subtask = get_object_or_404(SubTask, id=subtask_id)

        if subtask.created_by != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        subtask.title = title
        subtask.description = description
        subtask.save()
    else:
        SubTask.objects.create(
            task=task,
            title=title,
            description=description,
            created_by=request.user
        )

    return JsonResponse({'success': True})



#delete subtask
@login_required
def delete_subtask(request, subtask_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    subtask = get_object_or_404(SubTask, id=subtask_id)

    if subtask.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    subtask.delete()
    return JsonResponse({'success': True})




#review task
@login_required
def review_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # 🔐 Only the manager who assigned the task can review it
    if not UserTask.objects.filter(task=task, assigned_by=request.user).exists():
        return HttpResponseForbidden("You cannot review this task.")

    # Assigned staff (exclude manager)
    assigned_staff = (
        User.objects
        .filter(tasks_received__task=task)
        .exclude(id=request.user.id)
        .distinct()
    )

    # Attachments uploaded for this task
    attachments = task.attachments.all()

    # Fetch all major comments for this task (parent is None)
    major_comments = Comment.objects.filter(task=task, parent=None).order_by('-created_at')
    # Each major comment can access its replies via `comment.replies.all()`

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()

        if action == 'reject' and not reason:
            messages.error(request, "Rejection reason is required.")
            return redirect('review_task', task_id=task.id)

        elif action == 'accept':
            # UserTask.objects.filter(task=task, assigned_by=request.user).update(status='accepted')
            UserTask.objects.filter(task=task).update(review_status='accepted')
            messages.success(request, "Task accepted successfully.")

        elif action == 'reject':
            UserTask.objects.filter(task=task, assigned_by=request.user).update(review_status='rejected', status='pending')
            Comment.objects.create(
                user=request.user,
                task=task,
                comment=reason
            )
            messages.success(request, "Task rejected with reason.")

        return redirect('assigned_tasks')

    return render(request, 'tasks/review_task.html', {
        'task': task,
        'assigned_staff': assigned_staff,
        'attachments': attachments,
        'major_comments': major_comments,
    })



#reply to a comment
@login_required
def reply_comment(request, comment_id):
    parent_comment = get_object_or_404(Comment, id=comment_id)
    task = parent_comment.task

    # 🚫 Prevent replying to your own comment
    if parent_comment.user == request.user:
        return HttpResponseForbidden("You cannot reply to your own comment.")

    # Find task relationship
    user_task = UserTask.objects.filter(task=task).first()

    if not user_task:
        return HttpResponseForbidden("Task assignment not found.")

    is_staff = user_task.assigned_to == request.user
    is_manager = user_task.assigned_by == request.user

    # Only assigned staff or assigning manager can reply
    if not (is_staff or is_manager):
        return HttpResponseForbidden("You cannot reply on this task.")

    if request.method == 'POST':
        reply_text = request.POST.get('comment')
        if reply_text:
            Comment.objects.create(
                user=request.user,
                task=task,
                parent=parent_comment,
                comment=reply_text
            )

    # 🔁 Redirect based on role
    if is_manager:
        return redirect('review_task', task_id=task.id)

    return redirect('task_detail', task_id=task.id)




@login_required
@require_POST
def delete_task_cascade(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # Only managers can delete tasks they assigned
    if request.user.role != 'manager':
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if not UserTask.objects.filter(
        task=task,
        assigned_by=request.user
    ).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    task.delete()  # CASCADE deletes all UserTask rows
    return JsonResponse({'success': True})

@login_required
def overdue_tasks_report(request):
    if request.user.role != 'manager':
        return HttpResponseForbidden()

    import pytz
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    overdue_tasks = UserTask.objects.select_related('task', 'assigned_to').filter(
        task__due_date__lt=today,
        assigned_to__role='staff',
        assigned_to__section=request.user.section
    ).exclude(status__in=['completed', 'rejected'])

    return render(request, 'reports/overdue_tasks.html', {'overdue_tasks': overdue_tasks})

@login_required
def due_soon_report(request):
    if request.user.role != 'manager':
        return HttpResponseForbidden()

    import pytz
    from datetime import timedelta
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    days_ahead = 7
    due_date_limit = today + timedelta(days=days_ahead)

    tasks = UserTask.objects.select_related('task', 'assigned_to').filter(
        task__due_date__gte=today,
        task__due_date__lte=due_date_limit,
        assigned_to__role='staff',
        assigned_to__section=request.user.section
    ).exclude(status__in=['completed', 'rejected']).order_by('task__due_date')

    due_soon_tasks = []
    for ut in tasks:
        days_left = (ut.task.due_date - today).days
        due_soon_tasks.append({'user_task': ut, 'days_left': days_left})

    return render(request, 'reports/due_soon_tasks.html', {'due_soon_tasks': due_soon_tasks})


@login_required
def staff_performance_report(request):
    if request.user.role != 'manager':
        return HttpResponseForbidden()

    import pytz
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    # Get staff in manager's section
    staff_users = User.objects.filter(
        role__iexact='staff',
        section=request.user.section
    )

    performance_data = []

    for staff in staff_users:
        # Only tasks assigned by this manager
        tasks = UserTask.objects.filter(
            assigned_to=staff,
            assigned_by=request.user
        )

        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='completed').count()
        pending_tasks = tasks.filter(status__in=['pending', 'in_progress', 'accepted']).count()
        overdue_tasks = tasks.filter(
            task__due_date__lt=today
        ).exclude(status__in=['completed', 'rejected']).count()

        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        performance_data.append({
            'staff': staff,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'overdue_tasks': overdue_tasks,
            'completion_rate': round(completion_rate, 1),
        })

    # Prepare chart data
    labels = [
        f"{item['staff'].email}"
        for item in performance_data
    ]
    completed = [item['completed_tasks'] for item in performance_data]
    pending = [item['pending_tasks'] for item in performance_data]
    overdue = [item['overdue_tasks'] for item in performance_data]

    return render(request, 'reports/staff_performance.html', {
        'performance_data': performance_data,
        'chart_labels': json.dumps(labels),
        'chart_completed': json.dumps(completed),
        'chart_pending': json.dumps(pending),
        'chart_overdue': json.dumps(overdue),
    })

