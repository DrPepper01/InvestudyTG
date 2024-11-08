from django.db import models

from .base import BaseModel

class UserProfile(BaseModel):
    telegram_id = models.IntegerField(unique=True)
    username = models.CharField(max_length=150, null=True, blank=True)
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self):
        return self.username or f'User {self.telegram_id}'