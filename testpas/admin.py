# testpas/admin.py
from django.contrib import admin
from django.http import HttpResponse
import csv
from .models import Participant, UserSurveyProgress, Response, EmailTemplate, Survey, Question, ParticipantEntry, EmailContent, MessageContent, Challenge, SurveyProgress, Token, Content, Challenge1Response
from django.utils import timezone

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('participant_id', 'user', 'enrollment_date', 'code_entered', 'wave3_code_entered', 'group')
    actions = ['export_study_data']

    def export_study_data(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pas_study_data.csv"'
        writer = csv.writer(response)

        
        writer.writerow([
            'Participant ID', 'Username', 'Email', 'Phone Number', 'Enrollment Date', 'Eligible', 'Consent Given',
            'Decline Reason', 'Survey Progress (%)', 'Survey Responses', 'Day 1 Date', 'Current Study Day', 'Wave 1 Code Entered', 'Wave 1 Code Entry Date',
            'Group', 'Intervention Start', 'Intervention End', 'Wave 3 Code Entered', 'Wave 3 Code Entry Date'
        ])
        for participant in queryset:
            progress = UserSurveyProgress.objects.filter(user=participant.user).first()
            responses = Response.objects.filter(user=participant.user).values_list('question', 'answer')
            response_str = '; '.join([f"{q}: {a}" for q, a in responses]) if responses else 'N/A'
            progress_percentage = progress.progress if progress and progress.progress is not None else 'N/A'

            day_1 = progress.day_1 if progress and progress.day_1 else 'N/A'
            study_day = (timezone.now().date() - progress.day_1).days + 1 if progress and progress.day_1 else 'N/A'
    
            writer.writerow([
                participant.participant_id,
                participant.user.username,
                participant.user.email,
                participant.phone_number,
                participant.enrollment_date,
                progress.eligible if progress else 'N/A',
                progress.consent_given if progress else 'N/A',
                '',  # Remove decline_reason since it doesn't exist in the model
                progress_percentage,  # New column for survey progress
                response_str,         # Survey answers
                participant.code_entered,
                participant.code_entry_date,
                participant.group,
                participant.intervention_start_date,
                participant.intervention_end_date,
                participant.wave3_code_entered,
                participant.wave3_code_entry_date
            ])
        return response

    export_study_data.short_description = "Export PAS study data (Info 2-6, 11, 15, 22)" # type: ignore

admin.site.register(UserSurveyProgress)
admin.site.register(Response)
admin.site.register(EmailTemplate)
admin.site.register(Survey)
admin.site.register(Question)
admin.site.register(ParticipantEntry)
admin.site.register(EmailContent)
admin.site.register(MessageContent)
admin.site.register(Challenge)
admin.site.register(SurveyProgress)
admin.site.register(Token)

@admin.register(Challenge1Response)
class Challenge1ResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'participant_id_display', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'participant__participant_id')
    actions = ['export_csv']

    def participant_id_display(self, obj):
        return obj.participant.participant_id
    participant_id_display.short_description = 'Participant ID'

    def export_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="challenge1_responses.csv"'
        writer = csv.writer(response)
        writer.writerow(['username', 'participant_id', 'created_at', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7'])
        for r in queryset.select_related('user', 'participant'):
            writer.writerow([
                r.user.username, r.participant.participant_id, r.created_at.isoformat(),
                r.q1, r.q2, r.q3, r.q4, r.q5, r.q6, r.q7
            ])
        return response
    export_csv.short_description = 'Export selected responses as CSV'


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'title', 'last_updated')
    list_filter = ('content_type', 'last_updated')
    search_fields = ('title', 'content')
    readonly_fields = ('last_updated',)
    
    fieldsets = (
        ('Content Information', {
            'fields': ('content_type', 'title')
        }),
        ('Content', {
            'fields': ('content',),
            'description': 'Enter HTML content. You can use basic HTML tags like <p>, <strong>, <em>, <ul>, <li>, etc.'
        }),
        ('Metadata', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

