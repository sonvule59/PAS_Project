# type: ignore
import datetime
from django.db import models, migrations
from django.contrib.auth.models import User, AbstractUser
from django.utils import timezone
from datetime import datetime, timedelta
from testpas import settings
import string
import random
import uuid
from django.core.mail import send_mail
from django.conf import settings

class Survey(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    # created_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return self.title

class Question(models.Model):
    survey = models.ForeignKey(Survey, related_name='questions', on_delete=models.CASCADE)
    question_text = models.CharField(max_length=255)
    # created_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.question_text

class CustomUser(AbstractUser):
    middle_name = models.CharField(max_length=30, null=True, blank=True)
    registration_code = models.CharField(max_length=15, null=True, blank=True)
    consented = models.BooleanField(null=True, blank=True)
    consent_response = models.TextField(null=True, blank=True)

    # Avoid conflicts with default 'User' model by adding related_name
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="customuser_set",
        blank=True,
        help_text="The groups this user belongs to.",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="customuser_set",
        blank=True,
        help_text="Specific permissions for this user.",
    )
class Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.CharField(max_length=255)
    # created_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"{self.user} - {self.question}"
class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Use {participant_id} as placeholder.")
    def __str__(self):
        return self.name
class UserSurveyProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    progress = models.IntegerField(default=0)
    day_1 = models.DateField(null=True, blank=True)  # Represents Day 1 (date of consent)
    survey_completed = models.BooleanField(default=False)
    eligible = models.BooleanField(default=False)
    eligibility_reason = models.TextField(null=True, blank=True)  # Reason for eligibility or ineligibility
    consent_given = models.BooleanField(default=False)  # Whether consent has been provided
    progress_percentage = models.IntegerField(null=True, blank=True)  # Percentage of survey completed

    ### Jun 25: Add in email log
    email_log = models.TextField(default="", blank=True) 
    ### Jun 25: Add in email log date
    date_joined = models.DateTimeField(auto_now_add=True)
    
    # Timeline reference for time compression testing
    timeline_reference_timestamp = models.DateTimeField(null=True, blank=True)
    
    # def __str__(self):
    #     return f"{self.user} - {self.survey} - {self.progress}%"

    def __str__(self):
        return self.user.username
    
def generate_confirmation_token():
    return uuid.uuid4().hex

class Participant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # user = models.ForeignKey(User, on_delete=models.CASCADE)
    age = models.IntegerField(null=True, blank=True, default=None)
    weight = models.IntegerField(null=True, blank=True, default=None)  # weight in pounds
    height = models.IntegerField(null=True, blank=True, default=None)  # height in inches
    bmi = models.FloatField(null=True, blank=True, default=None)
    willing_no_other_study = models.BooleanField(null=True, blank=True, default=None)
    willing_monitor = models.BooleanField(null=True, blank=True, default=None)
    willing_contact = models.BooleanField(null=True, blank=True, default=None)
    enrollment_date = models.DateField(default=timezone.now)
    code_entered = models.BooleanField(default=False)
    code_entry_date = models.DateField(null=True, blank=True)
    ### Jun 25: Add in code entry day
    code_entry_day = models.IntegerField(null=True, blank=True)
    email_send_date = models.DateField(null=True, blank=True)  # store email send date
    email_status = models.CharField(max_length=50, default='pending')
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    address_line1 = models.CharField(max_length=255, null=True, blank=True)
    address_line2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    dominant_hand = models.CharField(max_length=10, null=True, blank=True, choices=[('left', 'Left'), ('right', 'Right')], help_text="Non-dominant hand for physical activity monitoring")
    confirmation_token = models.CharField(max_length=255, unique=True)
    is_confirmed = models.BooleanField(default=False)
    token_expiration = models.DateTimeField(default=timezone.now)
    phase = models.CharField(max_length=100, blank=True, null=True)
    monitoring_start_date = models.DateField(blank=True, null=True)
    # Double-blind Randomization
    participant_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    group = models.IntegerField(null=True, blank=True)
    group_assigned = models.BooleanField(default=False)
    intervention_start_date = models.DateTimeField(null=True, blank=True)
    intervention_end_date = models.DateTimeField(null=True, blank=True)
    
    randomization_pair_id = models.IntegerField(null=True, blank=True, help_text="Pair ID for 2-block randomization (1, 2, 3, etc.)")
    randomization_position = models.IntegerField(null=True, blank=True, choices=[(1, 'First in pair'), (2, 'Second in pair')], help_text="Position within the randomization pair")
    randomization_completed = models.BooleanField(default=False, help_text="Whether 2-block randomization has been completed")
    randomization_email_sent = models.BooleanField(default=False, help_text="Whether randomization email was sent to this participant")
    randomization_email_sent_date = models.DateField(null=True, blank=True, help_text="Date when randomization email was sent")
    engagement_tracked = models.BooleanField(default=False)
    email = models.EmailField(null=True, blank=True)  
    wave1_survey_email_sent = models.BooleanField(default=False)
    wave2_survey_email_sent = models.BooleanField(default=False)
    wave2_monitoring_notice_sent = models.BooleanField(default=False)
    ## Wave 3
    wave3_survey_email_sent = models.BooleanField(default=False)
    wave3_code_entered = models.BooleanField(default=False)  # New field for Wave 3
    wave3_code_entry_date = models.DateField(null=True, blank=True)
    wave3_code_entry_day = models.IntegerField(null=True, blank=True)  # Add missing field
    wave3_monitor_ready_sent = models.BooleanField(default=False)
    wave3_missing_code_sent = models.BooleanField(default=False)
    wave3_survey_monitor_return_sent = models.BooleanField(default=False)
    wave3_survey_monitor_return_date = models.DateField(null=True, blank=True)
    randomized_group = models.IntegerField(null=True, blank=True)
    
    # Intervention tracking fields
    intervention_access_granted = models.BooleanField(default=False)
    intervention_access_date = models.DateTimeField(null=True, blank=True)
    intervention_login_count = models.IntegerField(default=0)
    challenges_completed = models.IntegerField(default=0)
    intervention_completion_date = models.DateTimeField(null=True, blank=True)
    
    # Intervention game tracking
    intervention_points = models.IntegerField(default=0)
    challenge_25_completed = models.BooleanField(default=False)
    challenge_25_completion_date = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.confirmation_token:
            self.confirmation_token = uuid.uuid4().hex
            while Participant.objects.filter(confirmation_token=self.confirmation_token).exists():
                self.confirmation_token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def send_email(self, template, extra_context=None, mark_as=None):
        # Use atomic database operation to prevent duplicate emails
        # This ensures only one worker/thread can send the email
        from django.db import transaction
        from collections import defaultdict

        # Resolve template
        if isinstance(template, str):
            template_name = template
            try:
                template_obj = EmailTemplate.objects.get(name=template_name)
            except EmailTemplate.DoesNotExist:
                raise Exception(f"EmailTemplate '{template_name}' not found in database. Run: python manage.py seed_email_template")
        else:
            template_obj = template
            template_name = getattr(template_obj, "name", None) or "<template>"

        # Build a safe formatting context for templates
        context = {
            "username": getattr(self.user, "username", "") if hasattr(self, 'user') and self.user else "",
            "participant_id": getattr(self, "participant_id", ""),
            "email": (self.email or (getattr(self.user, "email", "") if hasattr(self, 'user') and self.user else "")),
        }
        if extra_context:
            context.update(extra_context)

        # Use SafeFormatter to handle missing keys gracefully
        class SafeFormatter(dict):
            def __missing__(self, key):
                return f"{{{key}}}"  # Return the placeholder if key is missing
        
        safe_context = SafeFormatter(context)
        try:
            subject = (template_obj.subject or "").format_map(safe_context)
            body = (template_obj.body or "").format_map(safe_context)
        except (KeyError, ValueError) as e:
            # Fallback: if format_map still fails, use format with **kwargs
            # This handles cases where format_map doesn't work as expected
            try:
                subject = (template_obj.subject or "").format(**context)
                body = (template_obj.body or "").format(**context)
            except KeyError as ke:
                raise Exception(f"Missing required template variable: {ke}. Available: {list(context.keys())}")
        
        # If mark_as is provided, check if email was already sent with that status
        # Use atomic update to prevent race conditions - try to claim the task
        if mark_as:
            # Refresh from DB to get latest status
            self.refresh_from_db()
            
            # Check if email was already sent
            if self.email_status == mark_as:
                # logger.info(f"Email '{template_name}' already sent for participant {self.participant_id} (status: {mark_as}), skipping duplicate")
                return
            
            # Try to atomically claim the task by updating status to 'sending'
            # This prevents multiple workers from processing the same email
            updated_count = Participant.objects.filter(
                id=self.id,
            ).exclude(
                email_status=mark_as
            ).update(
                email_status='sending'  # Temporary status to claim the task
            )
            
            if updated_count == 0:
                self.refresh_from_db()
                return # Another worker already claimed this task or email was already sent - skip
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [self.email or self.user.email, 'svu23@iastate.edu', 'vuleson59@gmail.com', 'projectpas2024@gmail.com'],
                fail_silently=False,
            )
            # Update status after successful send
            if mark_as:
                self.email_status = mark_as
            else:
                self.email_status = 'sent'
            self.email_send_date = timezone.now().date()
            self.save()
        except Exception as e:
            # On failure, set status back from 'sending' to allow retry
            if mark_as and self.email_status == 'sending':
                self.email_status = 'failed'
            else:
                self.email_status = 'failed'
            self.save()
            raise Exception(f"Failed to send email: {str(e)}")

    def send_confirmation_email(self):
        # Prevent duplicate confirmation emails
        # Only send if account is not yet confirmed and confirmation email hasn't been sent
        if self.is_confirmed:
            #logger.info(f"Account already confirmed for participant {self.participant_id}, skipping confirmation email")
            return
        if self.email_status == 'confirmation_email_sent':
            #logger.info(f"Confirmation email already sent for participant {self.participant_id}, skipping duplicate")
            return
        
        confirmation_link = f"{settings.BASE_URL}/confirm-account/{self.confirmation_token}/"
        self.send_email(
            'account_confirmation',
            extra_context={'confirmation_link': confirmation_link},
            mark_as='confirmation_email_sent'
        )
    def __str__(self):
        return self.user.username
    
    """Info 12"""
    def send_code_entry_email(self):
        template = EmailTemplate.objects.get(name='wave1_code_entry')
        message = template.body.format(
            username=self.user.username,
            code_date=self.code_entry_date.strftime('%m/%d/%Y') if self.code_entry_date else '',
            start_date=(self.code_entry_date + timedelta(days=1)).strftime('%m/%d/%Y') if self.code_entry_date else '',
            end_date=(self.code_entry_date + timedelta(days=7)).strftime('%m/%d/%Y') if self.code_entry_date else ''
        )
    
        
    def send_wave1_survey_return_email(self):
        template = EmailTemplate.objects.get(name='wave1_survey_return')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(
            template.subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.user.email, 'vuleson59@gmail.com', 'projectpas2024@gmail.com'],
            fail_silently=False,
        )
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

    #Info 14 - Day 22: Missing Code Entry (Wave 1)
    # IMPORTANT: Only send ONCE on Day 22 if code NOT entered. Then stop checking.
    # Whether they enter code or not, they move to randomization (Info 15) on Day 29.
    # CRITICAL: Only send during Wave 1 period (Days 22-28). After Day 29 (randomization), don't send Wave 1 emails.
    def send_missing_code_email(self): 
        template = EmailTemplate.objects.get(name='wave1_missing_code')
        message = template.body.format(username=self.user.username)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

    #Info 16 & 19 - Day 29: No Monitoring Access (Wave 2)
    # IMPORTANT: Only send ONCE on Day 29 if no monitoring access. Then stop checking.
    # Whether they have access or not, they move to randomization (Info 15) on Day 29.
    # CRITICAL: Only send during Wave 2 period (Days 29-35). After Day 35 (randomization), don't send Wave 2 emails.
    def send_wave2_no_monitoring_email(self):  # Info 16 & 19
        template = EmailTemplate.objects.get(name='intervention_access_later' if self.group == 0 else 'wave2_no_monitoring')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

    #Info 17 & 18 - Day 57: Survey Ready (Wave 2)
    # IMPORTANT: Only send ONCE on Day 57 if survey is ready. Then stop checking.
    # Whether they have access or not, they move to randomization (Info 15) on Day 29.
    # CRITICAL: Only send during Wave 2 period (Days 29-35). After Day 35 (randomization), don't send Wave 2 emails.
    def send_wave2_survey_email(self): 
        template = EmailTemplate.objects.get(name='intervention_access_immediate' if self.group == 1 and self.intervention_start_date == timezone.now().date() else 'wave2_survey_ready')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

    def send_wave3_survey_email(self):  # Info 20
        template = EmailTemplate.objects.get(name='wave3_survey_ready')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()
    def send_wave3_monitoring_email(self):  # Info 21
        template = EmailTemplate.objects.get(name='wave3_monitoring_ready')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

    def send_wave3_code_entry_email(self):  # Info 23
        try:
            template = EmailTemplate.objects.get(name='wave3_code_entry')
            message = template.body.format(
                participant_id=self.participant_id, 
                code_date=self.wave3_code_entry_date.strftime('%m/%d/%Y') if self.wave3_code_entry_date else '', 
                start_date=(self.wave3_code_entry_date + timezone.timedelta(days=1)).strftime('%m/%d/%Y') if self.wave3_code_entry_date else '', 
                end_date=(self.wave3_code_entry_date + timezone.timedelta(days=7)).strftime('%m/%d/%Y') if self.wave3_code_entry_date else ''
            )
            send_mail(
                template.subject, 
                message, 
                settings.DEFAULT_FROM_EMAIL, 
                [self.user.email, 'vuleson59@gmail.com'], 
                fail_silently=False
            )
            self.email_status = 'sent'
            self.email_send_date = timezone.now().date()
            self.save()
            return True
        except Exception as e:
            print(f"Wave 3 code entry email error: {str(e)}")
            self.email_status = 'failed'
            self.save()
            return False

    def send_study_end_email(self):  # Info 24
        template = EmailTemplate.objects.get(name='study_end')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

    def send_wave3_missing_code_email(self):  # Info 25
        template = EmailTemplate.objects.get(name='wave3_missing_code')
        message = template.body.format(participant_id=self.participant_id)
        send_mail(template.subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email, 'vuleson59@gmail.com'], fail_silently=False)
        self.email_status = 'sent'
        self.email_send_date = timezone.now().date()
        self.save()

#Testing
class ParticipantEntry(models.Model):
    participant_id = models.CharField(max_length=100)
    entry_date = models.DateTimeField(default=timezone.now)
    email = models.EmailField()

    def __str__(self):
        return self.participant_id

class EmailContent(models.Model):
    subject = models.CharField(max_length=255)
    body = models.TextField()

    def __str__(self):
        return self.subject

class MessageContent(models.Model):
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sms_body = models.TextField()

    def __str__(self):
        return self.subject
    
class Challenge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField()
    code = models.CharField(max_length=255, null=True, blank=True)  # For challenges requiring a code
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    completed = models.BooleanField(default=False)

class SurveyProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    interest_submitted = models.BooleanField(default=False)
    interested = models.BooleanField(null=True, blank=True)

    eligibility_submitted = models.BooleanField(default=False)
    is_eligible = models.BooleanField(null=True, blank=True)

    consent_submitted = models.BooleanField(default=False)
    consented = models.BooleanField(null=True, blank=True)

    def __str__(self):
        return f"SurveyProgress for {self.user.username}"
    
class Token(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"Token for {self.recipient.username}"

    @staticmethod
    def generate_token(length=25):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)

class Content(models.Model):
    """Model for researcher-editable website content"""
    CONTENT_TYPES = [
        ('exit_screen', 'Exit Screen Content'),
        ('waiting_screen', 'Waiting Screen Content'),
        ('consent_form', 'Consent Form Content'),
        ('eligibility_interest', 'Eligibility Interest Page'),
        ('home_page', 'Home Page Content'),
        ('wave1_survey', 'Wave 1 Survey Content'),
        ('wave2_survey', 'Wave 2 Survey Content'),
        ('wave3_survey', 'Wave 3 Survey Content'),
        ('information_16', 'Information 16 - Control Group Message'),
        ('information_20', 'Information 20 - No Wave 2 Physical Activity Monitoring'),
    ]
    
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPES, unique=True)
    title = models.CharField(max_length=255)
    content = models.TextField(help_text="HTML content that can be edited by researchers")
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_content_type_display()} - {self.title}"



class Challenge5Response(models.Model):
    """Stores responses to Introductory Challenge 5 (Self-efficacy, 7 items, 0-4)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge5_responses')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='challenge5_responses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    q1 = models.PositiveSmallIntegerField()
    q2 = models.PositiveSmallIntegerField()
    q3 = models.PositiveSmallIntegerField()
    q4 = models.PositiveSmallIntegerField()
    q5 = models.PositiveSmallIntegerField()
    q6 = models.PositiveSmallIntegerField()
    q7 = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Challenge5Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class WorkRelatedChallenge7Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Easy-to-perform task
    answer2 = models.TextField(blank=True, null=True)  # Increasingly difficult task
    answer3 = models.TextField(blank=True, null=True)  # Specific plan
    answer4 = models.TextField(blank=True, null=True)  # Flexible habit

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"WorkRelatedChallenge7Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class WorkRelatedChallenge10Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Past success experiences
    answer2 = models.TextField(blank=True, null=True)  # Mental rehearsal factors
    answer3 = models.TextField(blank=True, null=True)  # Prompts and cues plan
    answer4 = models.TextField(blank=True, null=True)  # General behavior goal
    answer5 = models.TextField(blank=True, null=True)  # Outcome goal
    answer6 = models.TextField(blank=True, null=True)  # Social support plan

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"WorkRelatedChallenge10Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class TransportRelatedChallenge12Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Easy-to-perform task
    answer2 = models.TextField(blank=True, null=True)  # Increasingly difficult task
    answer3 = models.TextField(blank=True, null=True)  # Specific plan
    answer4 = models.TextField(blank=True, null=True)  # Flexible habit

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TransportRelatedChallenge12Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class TransportRelatedChallenge15Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Past success experiences
    answer2 = models.TextField(blank=True, null=True)  # Mental rehearsal factors
    answer3 = models.TextField(blank=True, null=True)  # Prompts and cues plan
    answer4 = models.TextField(blank=True, null=True)  # General behavior goal
    answer5 = models.TextField(blank=True, null=True)  # Outcome goal
    answer6 = models.TextField(blank=True, null=True)  # Social support plan

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TransportRelatedChallenge15Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class DomesticRelatedChallenge17Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Easy-to-perform task
    answer2 = models.TextField(blank=True, null=True)  # Increasingly difficult task
    answer3 = models.TextField(blank=True, null=True)  # Specific plan
    answer4 = models.TextField(blank=True, null=True)  # Flexible habit

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"DomesticRelatedChallenge17Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class DomesticRelatedChallenge20Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Past success experiences
    answer2 = models.TextField(blank=True, null=True)  # Mental rehearsal factors
    answer3 = models.TextField(blank=True, null=True)  # Prompts and cues plan
    answer4 = models.TextField(blank=True, null=True)  # General behavior goal
    answer5 = models.TextField(blank=True, null=True)  # Outcome goal
    answer6 = models.TextField(blank=True, null=True)  # Social support plan

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"DomesticRelatedChallenge20Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class LeisureRelatedChallenge22Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Easy-to-perform task
    answer2 = models.TextField(blank=True, null=True)  # Increasingly difficult task
    answer3 = models.TextField(blank=True, null=True)  # Specific plan
    answer4 = models.TextField(blank=True, null=True)  # Flexible habit

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"LeisureRelatedChallenge22Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class LeisureRelatedChallenge27Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    answer1 = models.TextField(blank=True, null=True)  # Past success experiences
    answer2 = models.TextField(blank=True, null=True)  # Mental rehearsal factors
    answer3 = models.TextField(blank=True, null=True)  # Prompts and cues plan
    answer4 = models.TextField(blank=True, null=True)  # General behavior goal
    answer5 = models.TextField(blank=True, null=True)  # Outcome goal
    answer6 = models.TextField(blank=True, null=True)  # Social support plan

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"LeisureRelatedChallenge27Response(user={self.user.username}, created_at={self.created_at:%Y-%m-%d %H:%M})"

class ChallengeCompletion(models.Model):
    """Track which challenges each user has completed"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    challenge_number = models.IntegerField(help_text="Challenge number (1-35)")
    challenge_name = models.CharField(max_length=100, help_text="Name of the challenge")
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'challenge_number']
        ordering = ['challenge_number']
    
    def __str__(self):
        return f"Challenge {self.challenge_number}: {self.challenge_name} - {self.user.username}"

class InterventionResponse(models.Model):
    """Comprehensive model to store all intervention responses from Group 1 participants"""
    RESPONSE_TYPES = [
        ('commitment_click', 'Commitment Box Clicked'),
        ('challenge_completion', 'Challenge Completed'),
        ('form_submission', 'Form Submission'),
        ('game_interaction', 'Game Interaction'),
        ('video_watched', 'Video Watched'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    challenge_number = models.IntegerField(null=True, blank=True, help_text="Challenge number if applicable")
    challenge_name = models.CharField(max_length=200, null=True, blank=True, help_text="Name of the challenge")
    response_type = models.CharField(max_length=50, choices=RESPONSE_TYPES, help_text="Type of response")
    response_data = models.JSONField(default=dict, help_text="Structured response data (answers, selections, etc.)")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes or context")
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'challenge_number']),
            models.Index(fields=['participant', 'response_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_response_type_display()} - {self.user.username} - Challenge {self.challenge_number or 'N/A'} - {self.created_at:%Y-%m-%d %H:%M}"

