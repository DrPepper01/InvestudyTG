from django.contrib import admin
from .models import UserProfile, Ticket, Attachment

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'first_name', 'last_name')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'user', 'status', 'created_at')
    search_fields = ('ticket_id', 'user__username')
    list_filter = ('status',)

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'file_name', 'uploaded_at', 'image_tag')
    search_fields = ('ticket__ticket_id',)
    readonly_fields = ('image_tag',)