# apps/chat/models.py
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Dialogue(models.Model):
    participant1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dialogues_as_1")
    participant2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dialogues_as_2")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"
        # одна пара = один диалог (в любом порядке)
        constraints = [
            models.UniqueConstraint(
                fields=["participant1", "participant2"],
                name="%(app_label)s_%(class)s_unique_pair",
            ),
            models.CheckConstraint(
                check=~models.Q(participant1=models.F("participant2")),
                name="%(app_label)s_%(class)s_no_self_talk",
            ),
        ]


class Message(models.Model):
    """Сообщение внутри диалога."""
    dialogue = models.ForeignKey(
        Dialogue, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField("Текст сообщения")
    is_read = models.BooleanField("Прочитано", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}"