# Intranet Timesheet

This is a small Django project for managing weekly timesheets.

Quick start (development):

1. Create a virtualenv and install dependencies:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create DB schema (only after models are finalized):

```powershell
python manage.py makemigrations
python manage.py migrate
```

3. Create groups and superuser:

```powershell
python manage.py create_groups
python manage.py createsuperuser
```

4. Run server:

```powershell
python manage.py runserver
```

Notes:
- Account lockouts are handled by `django-axes` (configured in `Intranet_Project/settings.py`).
- Timesheets store rows in `Timesheet` and `TimesheetRow` models.

