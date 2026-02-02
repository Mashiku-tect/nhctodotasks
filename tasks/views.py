from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib import messages
from django.utils.timezone import now

from django.contrib.auth import get_user_model
from .models import Task, UserTask,SubTask,Comment,TaskAttachment


from django.utils import timezone
from datetime import timedelta

from django.http import HttpResponseForbidden,JsonResponse

from django.db.models import Q
from collections import defaultdict
from django.views.decorators.http import require_POST
from django.db.models import Prefetch
import os




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
        due_date = request.POST.get('due_date')
        priority = request.POST.get('priority', 'normal')

        if not title or not due_date:
            return JsonResponse(
                {'error': 'Title and due date are required.'},
                status=400
            )

        assigned_users = [user]  # default assignment: self

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
            priority=priority
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

    # Fetch UserTask entries where the user assigned the task to themselves
    my_usertasks = UserTask.objects.filter(
        assigned_by=user,
        assigned_to=user
    ).select_related('task').order_by('-created_at')

    # Extract the tasks from the usertasks
    tasks = [ut.task for ut in my_usertasks]

    return render(request, 'tasks/my_tasks.html', {
        'tasks': tasks
    })


# get assigned tasks for staff and managers
@login_required
def assigned_tasks(request):
    user = request.user

    if user.role == 'staff':
        # Tasks assigned TO the user, but NOT by themselves
        visible_qs = (
            UserTask.objects
            .select_related('task', 'assigned_by', 'assigned_to')
            .filter(assigned_to=user)
            .exclude(assigned_by=user)  # 🚫 remove self-assigned
        )

    else:  # manager
        # Tasks assigned BY the user, but NOT to themselves
        visible_qs = (
            UserTask.objects
            .select_related('task', 'assigned_by', 'assigned_to')
            .filter(assigned_by=user)
            .exclude(assigned_to=user)  # 🚫 remove self-assigned
        )

    grouped_tasks = defaultdict(list)
    for ut in visible_qs:
        grouped_tasks[ut.task].append(ut)

    task_list = []
    for task in grouped_tasks.keys():
        # Fetch ALL assignments for this task
        all_usertasks = (
            task.user_tasks
            .select_related('assigned_to', 'assigned_by')
            .exclude(
                Q(assigned_to=user) & Q(assigned_by=user)
            )  # 🚫 exclude self-assigned from list
        )

        # Staff's own assignment (safe)
        own_usertask = all_usertasks.filter(assigned_to=user).first()

        task_list.append({
            "task": task,
            "usertasks": all_usertasks,
            "own_usertask": own_usertask,
            "computed_status": compute_task_status(all_usertasks),
        })

    return render(request, 'tasks/assigned_tasks.html', {
        'task_list': task_list
    })





#dashboard view
@login_required
def dashboard(request):
    user = request.user
    today = timezone.now().date()

    # ================= KPI CARDS =================
    # My Open Tasks (assigned to self and not completed)
    my_open_tasks_count = UserTask.objects.filter(
        assigned_to=user,
        assigned_by=user,
        status='in_progress',
    ).exclude(status='completed').count()

    # Assigned to Me (tasks assigned by others to this user)
    assigned_to_me_count = UserTask.objects.filter(
        assigned_to=user
    ).exclude(assigned_by=user).count()

    # Overdue Tasks (assigned to self, due date past and not completed)
    overdue_count = UserTask.objects.filter(
        assigned_to=user,
        assigned_by=user,
        task__due_date__lt=today
    ).exclude(status='completed').count()

    # Completed this week (tasks assigned to self, completed in last 7 days)
    week_ago = today - timedelta(days=7)
    completed_this_week_count = UserTask.objects.filter(
        assigned_to=user,
        assigned_by=user,
        status='completed',
        task__updated_at__date__gte=week_ago
    ).count()

    # ================= Tasks Due Soon =================
    tasks_due_soon = UserTask.objects.filter(
        assigned_to=user,
        assigned_by=user,
        task__due_date__gte=today,
    ).exclude(status='completed').order_by('task__due_date')[:5]

    # ================= Recently Assigned =================
    recently_assigned = UserTask.objects.filter(
        assigned_to=user
    ).exclude(assigned_by=user).order_by('-created_at')[:5]

    return render(request, 'tasks/dashboard.html', {
        'my_open_tasks_count': my_open_tasks_count,
        'assigned_to_me_count': assigned_to_me_count,
        'overdue_count': overdue_count,
        'completed_this_week_count': completed_this_week_count,
        'tasks_due_soon': tasks_due_soon,
        'recently_assigned': recently_assigned,
    })

# view task details function
@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    user_task = UserTask.objects.filter(
        task=task,
        assigned_to=request.user
    ).first()

    if not user_task:
        return HttpResponseForbidden("You are not assigned to this task.")

    is_my_task = (
        user_task.assigned_by == request.user and
        user_task.assigned_to == request.user
    )

    is_assigned_task = (
        user_task.assigned_to == request.user and
        user_task.assigned_by != request.user
    )

    # ✅ TASK COMPLETION FLAG (from UserTask)
    task_completed = user_task.status == 'completed'
    task_accepted=user_task.status=='accepted'

    # SUBTASKS
    subtasks = task.subtasks.all()

    # ✅ Add completion flag per subtask
    for subtask in subtasks:
        subtask.is_completed = subtask.status == 'completed'

    # ✅ Used to disable "Mark Task Completed"
    incomplete_subtasks = subtasks.exclude(status='completed').exists()

    comments = []
    if is_assigned_task:
        comments = (
            Comment.objects
            .filter(task=task, parent__isnull=True)
            .select_related('user')
            .prefetch_related('replies')
        )

    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'task_completed': task_completed,
        'subtasks': subtasks,
        'incomplete_subtasks': incomplete_subtasks,
        'is_my_task': is_my_task,
        'is_assigned_task': is_assigned_task,
        'comments': comments,
        'task_accepted':task_accepted,
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
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    task = get_object_or_404(Task, id=task_id)

    if not UserTask.objects.filter(
        task=task,
        assigned_by=request.user
    ).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    task.delete()
    return JsonResponse({'success': True})



#edit task
@login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

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

        if action == 'accept':
            UserTask.objects.filter(task=task, assigned_by=request.user).update(status='accepted')
            messages.success(request, "Task accepted successfully.")

        elif action == 'reject':
            UserTask.objects.filter(task=task, assigned_by=request.user).update(status='rejected')
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
