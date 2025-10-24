from .views import is_admin_or_accounting


def admin_status(request):
    """Add is_admin_or_accounting and is_user_group booleans to template context."""
    is_admin_acc = is_admin_or_accounting(request.user) if request.user.is_authenticated else False
    is_user_grp = request.user.groups.filter(name='User').exists() if request.user.is_authenticated else False
    return {
        'is_admin_or_accounting': is_admin_acc,
        'is_user_group': is_user_grp,
    }