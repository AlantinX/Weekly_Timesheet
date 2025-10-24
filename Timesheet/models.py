from django.db import models
from django.conf import settings


class Employee(models.Model):
	# Allow multiple managers for a single Employee. Keep related_name 'employees'
	# so existing access patterns like `request.user.employees` keep working.
	managers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='employees')
	# Employee names must be unique across the system so managers can share crew members
	name = models.CharField(max_length=200, unique=True)

	# Soft-delete flag: when False, employee is hidden from lists but kept for historical
	# integrity so old TimesheetRows referencing this Employee remain valid.
	is_active = models.BooleanField(default=True)

	def __str__(self):
		mgr_ids = ','.join(str(m.pk) for m in self.managers.all()) if self.pk else '(new)'
		return f"{self.name} (managers={mgr_ids})"


class Timesheet(models.Model):
	owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timesheets')
	created_at = models.DateTimeField(auto_now_add=True)
	week_start = models.DateField(help_text='Date of the Monday for this timesheet')
	data_json = models.JSONField(blank=True, null=True)
	additional_notes = models.TextField(blank=True, default='')

	def __str__(self):
		return f"Timesheet {self.pk} by {self.owner} for {self.week_start}"


class TimesheetRow(models.Model):
	timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='rows')
	employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
	employee_name = models.CharField(max_length=200, blank=True)
	mon = models.CharField(max_length=50, blank=True)
	tues = models.CharField(max_length=50, blank=True)
	wed = models.CharField(max_length=50, blank=True)
	thur = models.CharField(max_length=50, blank=True)
	fri = models.CharField(max_length=50, blank=True)
	sat = models.CharField(max_length=50, blank=True)
	sun = models.CharField(max_length=50, blank=True)
	jobsite_name = models.CharField(max_length=255, blank=True)
	jobsite_num = models.CharField(max_length=100, blank=True)



	def __str__(self):
		return f"Row {self.pk} for Timesheet {self.timesheet_id} - {self.employee_name or (self.employee.name if self.employee else 'Unknown')}"


