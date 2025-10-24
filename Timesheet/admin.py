from django.contrib import admin
from .models import Employee, Timesheet


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'manager_list', 'is_active')
	filter_horizontal = ('managers',)

	def manager_list(self, obj):
		return ', '.join([m.username for m in obj.managers.all()])
	manager_list.short_description = 'Managers'


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
	list_display = ('id', 'owner', 'week_start', 'created_at')
	readonly_fields = ('created_at',)
	inlines = []


from .models import TimesheetRow


class TimesheetRowInline(admin.TabularInline):
	model = TimesheetRow
	extra = 0


TimesheetAdmin.inlines = [TimesheetRowInline]

