from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from .forms import EmployeeForm, TimesheetForm
from .models import Employee, Timesheet, TimesheetRow
from .utils import is_user_locked
from datetime import date, timedelta
from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied
from .forms import UserCreateForm, UserGroupForm, PasswordResetForm
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from datetime import datetime


def is_admin_or_accounting(user):
	return user.groups.filter(name__in=['Admin', 'Accounting']).exists()


def is_admin(user):
	return user.groups.filter(name='Admin').exists()


def timesheet_is_editable(ts):
	"""Return True if current date is before the Monday after ts.week_start."""
	# ts.week_start is a date for the Monday of the timesheet
	next_monday = ts.week_start + timedelta(days=7)
	today = date.today()
	return today < next_monday


def login_view(request):
	if request.method == 'POST':
		username = request.POST.get('username')
		password = request.POST.get('password')
		user = authenticate(request, username=username, password=password)
		if user is not None:
			login(request, user)
			return redirect('Timesheet:dashboard')
		messages.error(request, 'Invalid credentials')
	return render(request, 'Timesheet/login.html')


def logout_view(request):
	logout(request)
	return redirect('Timesheet:login')


@login_required
def dashboard(request):
	# Users see their own timesheets; Admin/Accounting can see all
	if is_admin_or_accounting(request.user):
		timesheets = Timesheet.objects.order_by('-week_start')
	else:
		timesheets = request.user.timesheets.order_by('-week_start')

	# Only users in the 'User' group should see the New Timesheet / Add Crew buttons
	is_user_group = request.user.groups.filter(name='User').exists()

	# handle admin delete via POST
	if request.method == 'POST' and 'delete_timesheet' in request.POST:
		# only Admins should be allowed to delete timesheets
		if not is_admin(request.user):
			messages.error(request, 'You do not have permission to delete this timesheet')
			return redirect('Timesheet:dashboard')

		# Expect a timesheet_id hidden field in the POST
		ts_id = request.POST.get('timesheet_id')
		if not ts_id:
			messages.error(request, 'No timesheet specified for deletion')
			return redirect('Timesheet:dashboard')

		try:
			ts_obj = Timesheet.objects.get(pk=int(ts_id))
		except (Timesheet.DoesNotExist, ValueError):
			messages.error(request, 'Timesheet not found')
			return redirect('Timesheet:dashboard')

		ts_obj.delete()
		messages.success(request, 'Timesheet deleted')
		return redirect('Timesheet:dashboard')
	# indicate if current user (owner) can edit
 
	# mark which timesheets are editable by their owner
	for ts in timesheets:
		ts.editable = (ts.owner == request.user and timesheet_is_editable(ts))

	return render(request, 'Timesheet/dashboard.html', {
		'timesheets': timesheets,
		'is_user_group': is_user_group,
        'is_admin': is_admin(request.user),
		'is_admin_or_accounting': is_admin_or_accounting(request.user)
	})


@login_required
def add_employee(request):
	if request.method == 'POST':
		# Two possible POST flows:
		# 1) create a new employee via the form (name must be unique)
		# 2) add an existing employee to your crew via 'add_existing' with employee_id
		if 'add_existing' in request.POST:
			# User clicked the 'Add' button on an available employee
			emp_id = request.POST.get('employee_id')
			try:
				emp = Employee.objects.get(pk=int(emp_id), is_active=True)
			except Exception:
				messages.error(request, 'Employee not found')
				return redirect('Timesheet:add_employee')
			# Attach current user as a manager if not already
			if not emp.managers.filter(pk=request.user.pk).exists():
				emp.managers.add(request.user)
				messages.success(request, 'Employee added to your crew')
			else:
				messages.info(request, 'Employee already on your crew')
			return redirect('Timesheet:crew_list')

		# Check for existing employee BEFORE form validation
		name = request.POST.get('name', '').strip()
		existing = None
		if name:
			try:
				existing = Employee.objects.get(name__iexact=name)
			except Employee.DoesNotExist:
				pass

		# If employee exists and user confirmed, add them to crew
		if existing and 'confirm_join' in request.POST:
			existing.managers.add(request.user)
			messages.success(request, 'Employee added to your crew')
			return redirect('Timesheet:crew_list')

		# If employee exists but user hasn't confirmed, show modal
		if existing:
			form = EmployeeForm(request.POST)
			confirm_existing = {'id': existing.id, 'name': existing.name}
			return render(request, 'Timesheet/add_employee.html', {
				'form': form,
				'available': Employee.objects.filter(is_active=True).exclude(managers=request.user).order_by('name'),
				'confirm_existing': confirm_existing
			})

		# No duplicate - validate and create new employee
		form = EmployeeForm(request.POST)
		if form.is_valid():
			emp = form.save()
			emp.managers.add(request.user)
			messages.success(request, 'Employee added')
			return redirect('Timesheet:dashboard')
	else:
		form = EmployeeForm()

	# Provide a list of all active crew members not already on this manager's crew
	available = Employee.objects.filter(is_active=True).exclude(managers=request.user).order_by('name')
	return render(request, 'Timesheet/add_employee.html', {'form': form, 'available': available})


@login_required
def crew_list(request):
	# Only users in 'User' group can manage their crew
	if not request.user.groups.filter(name='User').exists():
		raise PermissionDenied
	# Only show active employees in the crew list
	employees = request.user.employees.filter(is_active=True).order_by('name')
	return render(request, 'Timesheet/crew.html', {'employees': employees})


@login_required
def delete_employee(request, pk):
	emp = get_object_or_404(Employee, pk=pk)
	# Only a manager of the employee or admin/accounting can remove them from crew
	if not emp.managers.filter(pk=request.user.pk).exists() and not is_admin_or_accounting(request.user):
		messages.error(request, 'You do not have permission to delete this employee')
		return redirect('Timesheet:crew_list')
	if request.method == 'POST':
		# Ensure this is an explicit member delete action
		if 'delete_member' in request.POST:
			# If the requester is a manager, remove only that manager from the employee
			if emp.managers.filter(pk=request.user.pk).exists() and not is_admin_or_accounting(request.user):
				emp.managers.remove(request.user)
				messages.success(request, 'Removed from your crew')
				return redirect('Timesheet:crew_list')
		# Admin/Accounting can soft-delete the employee entirely (keep historical rows intact)
		# Admin/Accounting can soft-delete the employee entirely (keep historical rows intact)
		if is_admin_or_accounting(request.user):
			emp.is_active = False
			emp.save()
			messages.success(request, 'Employee removed')
			return redirect('Timesheet:user_management')
	# Redirect GETs back to crew list (we use inline-confirm forms)
	return redirect('Timesheet:crew_list')


@login_required
def new_timesheet(request):
	# default week_start = this week's Monday
	today = date.today()
	monday = today - timedelta(days=today.weekday())

	# Only Admin/Accounting should see other users in the dropdown. Regular users should not.
	if is_admin_or_accounting(request.user):
		user_group = Group.objects.get(name='User')
		# Exclude deactivated users
		user_group_members = user_group.user_set.filter(is_active=True).order_by('username')
	else:
		user_group_members = []

	if request.method == 'POST':
		form = TimesheetForm(request.POST)
		if form.is_valid():
			ts = form.save(commit=False)
			ts.owner = request.user
			ts.save()

			# parse posted rows. pattern: employee_{i}, hours_{i}_{d}, jobsite_name_{i}, jobsite_num_{i}
			rows_created = 0
			try:
				rows_count = int(request.POST.get('rows_count', '10'))
			except ValueError:
				rows_count = 10
			for i in range(0, rows_count):
				emp_field = f'employee_{i}'
				# determine employee or free text
				emp_val = request.POST.get(emp_field, '').strip()
				if not emp_val:
					# if no employee selected and no hours, skip
					# check for any hours
					any_hours = False
					for d in range(0, 7):
						if request.POST.get(f'hours_{i}_{d}', '').strip():
							any_hours = True
					if not any_hours:
						continue

				row = TimesheetRow(timesheet=ts)
				# employee handling
				if emp_val.isdigit():
					try:
						row.employee = Employee.objects.get(pk=int(emp_val), owner=request.user)
						row.employee_name = row.employee.name
					except Employee.DoesNotExist:
						row.employee_name = ''
				elif emp_val == 'self' or emp_val == request.user.username:
					row.employee_name = request.user.get_full_name() or request.user.username
				else:
					# Only Admin/Accounting may select other users from the 'User' group.
					# Regular users cannot pick other usernames as employees — treat as literal text.
					if is_admin_or_accounting(request.user):
						try:
							user_group = Group.objects.get(name='User')
							user = User.objects.get(username=emp_val, groups=user_group)
							row.employee_name = user.get_full_name() or user.username
						except (Group.DoesNotExist, User.DoesNotExist):
							row.employee_name = emp_val
					else:
						row.employee_name = emp_val

				# hours (store raw strings so values like 'Vaca' or 'Sick' are allowed)
				for d, fld in enumerate(['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun']):
					val = request.POST.get(f'hours_{i}_{d}', '').strip()
					# Save the entered text; empty -> empty string to avoid NULLs
					if val:
						setattr(row, fld, val)
					else:
						setattr(row, fld, '')

				row.jobsite_name = request.POST.get(f'jobsite_name_{i}', '').strip()
				row.jobsite_num = request.POST.get(f'jobsite_num_{i}', '').strip()

				# only save non-empty rows (any hours or jobsite or employee name)
				if row.employee_name or row.jobsite_name or row.jobsite_num or any([row.mon, row.tues, row.wed, row.thur, row.fri, row.sat, row.sun]):
					row.save()
					rows_created += 1

			messages.success(request, f'Timesheet saved ({rows_created} rows)')
			return redirect('Timesheet:dashboard')
	else:
		form = TimesheetForm(initial={'week_start': monday})
	# provide an ISO-formatted default string for the template date input (YYYY-MM-DD)
	week_start_default = monday.isoformat()
	rows_range = range(0, 10)
	day_range = range(0, 7)

	# Provide active employees to template (admins see all active employees;
	# regular users see only their own active crew members).
	if is_admin_or_accounting(request.user):
		active_employees = Employee.objects.filter(is_active=True).order_by('name')
	else:
		active_employees = request.user.employees.filter(is_active=True).order_by('name')

	return render(request, 'Timesheet/new_timesheet.html', {
		'form': form,
		'week_start_default': week_start_default,
		'rows_range': rows_range,
		'day_range': day_range,
		'user_group_members': user_group_members,
		'active_employees': active_employees,
		'is_admin_or_accounting': is_admin_or_accounting(request.user)
	})


@login_required
def view_timesheet(request, pk):
	ts = get_object_or_404(Timesheet, pk=pk)
	# Permission: owner, Admin/Accounting can view
	if ts.owner != request.user and not is_admin_or_accounting(request.user):
		messages.error(request, 'You do not have permission to view this timesheet')
		return redirect('Timesheet:dashboard')

	# handle admin delete via POST
	if request.method == 'POST' and 'delete_timesheet' in request.POST:
		# only Admins should be allowed to delete timesheets
		if is_admin(request.user):
			ts.delete()
			messages.success(request, 'Timesheet deleted')
			return redirect('Timesheet:dashboard')
		else:
			messages.error(request, 'You do not have permission to delete this timesheet')
			return redirect('Timesheet:view_timesheet', pk=ts.pk)
	# indicate if current user (owner) can edit
	editable = (ts.owner == request.user and timesheet_is_editable(ts))
	return render(request, 'Timesheet/view_timesheet.html', {'timesheet': ts, 'editable': editable, 'is_admin': is_admin(request.user)})


@login_required
def user_management(request):
	if not is_admin_or_accounting(request.user):
		raise PermissionDenied
	# Show only active users in the management list (deactivated users are hidden)
	users = User.objects.filter(is_active=True).order_by('username')
	# Check which users are locked
	for user in users:
		user.is_locked = is_user_locked(user.username)
	inactive_users = User.objects.filter(is_active=False).order_by('username')

	# Employees (crew members) for the current project: show active and inactive
	employees = Employee.objects.filter(is_active=True).order_by('name')
	inactive_employees = Employee.objects.filter(is_active=False).order_by('name')

	return render(request, 'Timesheet/user_management.html', {
		'users': users,
		'inactive_users': inactive_users,
		'employees': employees,
		'inactive_employees': inactive_employees,
		'is_admin': is_admin(request.user)
	})


@login_required
def create_user(request):
	if not is_admin_or_accounting(request.user):
		raise PermissionDenied

	if request.method == 'POST':
		form = UserCreateForm(request.POST, current_user=request.user)
		if form.is_valid():
			user = form.save(commit=False)
			user.set_password(form.cleaned_data['password'])
			user.save()
			groups = form.cleaned_data.get('groups', None)
			if groups:
				user.groups.set(groups)
			else:
				user.groups.clear()
			messages.success(request, 'User created')
			return redirect('Timesheet:user_management')
	else:
		form = UserCreateForm(current_user=request.user)
	return render(request, 'Timesheet/create_user.html', {'form': form})


@login_required
def reactivate_user(request, pk):
	if not is_admin_or_accounting(request.user):
		raise PermissionDenied
	user = get_object_or_404(User, pk=pk)
	if request.method == 'POST':
		user.is_active = True
		user.save()
		messages.success(request, 'User reactivated')
	return redirect('Timesheet:user_management')


@login_required
def reactivate_employee(request, pk):
	emp = get_object_or_404(Employee, pk=pk)
	# Only a manager or admin/accounting can reactivate
	if not emp.managers.filter(pk=request.user.pk).exists() and not is_admin_or_accounting(request.user):
		messages.error(request, 'You do not have permission to reactivate this employee')
		return redirect('Timesheet:user_management')
	if request.method == 'POST':
		emp.is_active = True
		emp.save()
		messages.success(request, 'Employee reactivated')
	return redirect('Timesheet:user_management')


@login_required
def edit_user(request, pk):
	if not is_admin_or_accounting(request.user):
		raise PermissionDenied
	user = get_object_or_404(User, pk=pk)
	if request.method == 'POST':
		form = UserGroupForm(request.POST, instance=user, current_user=request.user)
		password_form = PasswordResetForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'User updated')
			return redirect('Timesheet:user_management')
		if password_form.is_valid():
			user.set_password(password_form.cleaned_data['new_password'])
			user.save()
			messages.success(request, 'Password updated successfully')
			return redirect('Timesheet:user_management')
	else:
		form = UserGroupForm(instance=user, current_user=request.user)
		password_form = PasswordResetForm()

	return render(request, 'Timesheet/edit_user.html', {
		'form': form,
		'password_form': password_form,
		'user_obj': user,
		'is_admin': is_admin(request.user),
		'can_delete': is_admin_or_accounting(request.user)
	})

@login_required
def unlock_user(request, pk):
    if not is_admin_or_accounting(request.user):
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # Delete all access attempt records for this user
        from axes.models import AccessAttempt
        AccessAttempt.objects.filter(username=user.username).delete()
        messages.success(request, 'Account unlocked')
    return redirect('Timesheet:user_management')

@login_required
def edit_timesheet(request, pk):
	ts = get_object_or_404(Timesheet, pk=pk)
	# owner can edit within edit window; Admin/Accounting can always edit
	if ts.owner != request.user and not is_admin_or_accounting(request.user):
		messages.error(request, 'You do not have permission to edit this timesheet')
		return redirect('Timesheet:dashboard')
	if not is_admin_or_accounting(request.user) and not timesheet_is_editable(ts):
		messages.error(request, 'This timesheet is no longer editable')
		return redirect('Timesheet:view_timesheet', pk=ts.pk)

	if request.method == 'POST':
		# Remove existing rows and recreate from post inside a transaction
		rows_created = 0
		try:
			rows_count = int(request.POST.get('rows_count', '10'))
		except ValueError:
			rows_count = 10

		with transaction.atomic():
			ts.rows.all().delete()
			for i in range(0, rows_count):
				emp_val = request.POST.get(f'employee_{i}', '').strip()
				if not emp_val:
					any_hours = False
					for d in range(0, 7):
						if request.POST.get(f'hours_{i}_{d}', '').strip():
							any_hours = True
					if not any_hours:
						continue

				row = TimesheetRow(timesheet=ts)
				if emp_val.isdigit():
					try:
						# Admin/Accounting can select any employee; others only their own
						if is_admin_or_accounting(request.user):
							row.employee = Employee.objects.get(pk=int(emp_val))
						else:
							row.employee = Employee.objects.get(pk=int(emp_val), owner=request.user)
						row.employee_name = row.employee.name
					except Employee.DoesNotExist:
						row.employee_name = ''
				elif emp_val == 'self' or emp_val == ts.owner.username:
					row.employee_name = ts.owner.get_full_name() or ts.owner.username
				else:
					# Only Admin/Accounting may select other users from the 'User' group.
					# Regular users cannot pick other usernames as employees — treat as literal text.
					if is_admin_or_accounting(request.user):
						try:
							user_group = Group.objects.get(name='User')
							user = User.objects.get(username=emp_val, groups=user_group)
							row.employee_name = user.get_full_name() or user.username
						except (Group.DoesNotExist, User.DoesNotExist):
							row.employee_name = emp_val
					else:
						row.employee_name = emp_val

				for d, fld in enumerate(['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun']):
					val = request.POST.get(f'hours_{i}_{d}', '').strip()
					# Preserve raw input (text or numbers). Empty -> empty string to avoid NULLs
					if val:
						setattr(row, fld, val)
					else:
						setattr(row, fld, '')

				row.jobsite_name = request.POST.get(f'jobsite_name_{i}', '').strip()
				row.jobsite_num = request.POST.get(f'jobsite_num_{i}', '').strip()

				if row.employee_name or row.jobsite_name or row.jobsite_num or any([row.mon, row.tues, row.wed, row.thur, row.fri, row.sat, row.sun]):
					row.save()
					rows_created += 1

		messages.success(request, f'Timesheet updated ({rows_created} rows)')
		# save additional notes
		ts.additional_notes = request.POST.get('additional_notes', '').strip()
		ts.save()
		return redirect('Timesheet:view_timesheet', pk=ts.pk)

	# prepare form-like context
	rows = list(ts.rows.all())
	length = max(10, len(rows))
	rows_range = range(0, length)
	# build rows_by_index padded with None for missing entries so template access is simple
	rows_by_index = [rows[i] if i < len(rows) else None for i in range(0, length)]
	day_range = range(0, 7)
	user_display = request.user.get_full_name() or request.user.username
    
	# Admin/Accounting can see all employees; others see their own
	if is_admin_or_accounting(request.user):
		employees = Employee.objects.all().order_by('name')
	else:
		employees = request.user.employees.filter(is_active=True).order_by('name')

	# Add all users in the 'User' group as potential employees
	if is_admin_or_accounting(request.user):
		user_group = Group.objects.get(name='User')
		user_group_members = user_group.user_set.filter(is_active=True).order_by('username')
	else:
		user_group_members = []

	return render(request, 'Timesheet/edit_timesheet.html', {
		'user_group_members': user_group_members,
		'timesheet': ts,
		'additional_notes': ts.additional_notes,
		'rows_by_index': rows_by_index,
		'rows_range': rows_range,
		'day_range': day_range,
		'user_display': user_display,
		'employees': employees,
		'is_admin_or_accounting': is_admin_or_accounting(request.user)
	})