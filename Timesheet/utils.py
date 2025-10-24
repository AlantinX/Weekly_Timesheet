from axes.models import AccessAttempt


def is_user_locked(username):
    """Check if a user account is locked due to too many failed login attempts."""
    return AccessAttempt.objects.filter(username=username).exists()