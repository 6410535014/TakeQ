from django.apps import apps

def invite_counts(request):
    """
    Return pending invitation count for the logged-in user.

    Use apps.get_model(...) inside the function to avoid importing app modules
    at import time (prevents AppRegistryNotReady during Django startup).
    """
    if not request.user.is_authenticated:
        return {'room_invitation_count': 0}

    RoomInvitation = apps.get_model('room', 'RoomInvitation')
    if RoomInvitation is None:
        return {'room_invitation_count': 0}

    pending = RoomInvitation.objects.filter(invited_user=request.user, status='pending').count()
    return {'room_invitation_count': pending}
