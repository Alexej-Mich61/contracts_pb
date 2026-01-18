# apps/audit/utils.py
from apps.audit.models import Event

def add_event(contract, user, event_type, old_value="", new_value=""):
    """Создаёт Event и возвращает строку, которую можно сразу отправить в чат / e-mail."""
    return Event.objects.create(
        contract=contract,
        user=user,
        event_type=event_type,
        old_value=str(old_value),
        new_value=str(new_value),
    ).__str__()