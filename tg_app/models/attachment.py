from django.db import models

from django.utils import timezone
from django.utils.html import mark_safe

from .ticket import Ticket
from .base import BaseModel



class Attachment(BaseModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    file_name = models.CharField(max_length=255)
    file_data = models.TextField()  # Base64 encoded data
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'Attachment {self.file_name} for Ticket #{self.ticket.ticket_id}'

    def image_tag(self):
        if self.file_data:
            return mark_safe(f'<img src="data:image/png;base64,{self.file_data}" width="200"/>')
        else:
            return "Нет изображения"

    image_tag.short_description = 'Изображение'