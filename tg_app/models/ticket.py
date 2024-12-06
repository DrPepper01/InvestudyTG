from django.db import models

from django.utils import timezone

from .base import BaseModel
from .userprofile import UserProfile


class Ticket(BaseModel):
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('resolved', 'Решена'),
        ('closed', 'Закрыта'),
    ]

    ticket_id = models.CharField(max_length=8, unique=True, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='tickets')
    description = models.TextField()
    additional_info = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    page = models.CharField(max_length=100, null=True, blank=True)
    section = models.CharField(max_length=100, null=True, blank=True)
    is_suggestion = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            from uuid import uuid4
            self.ticket_id = str(uuid4())[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Ticket #{self.ticket_id} from {self.user}'
