# type: ignore
from bz2 import compress
import logging
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.crypto import get_random_string
from django.contrib.auth import login, authenticate, logout
from django.db import IntegrityError, transaction
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.db.models import Model

from testpas.settings import *
from hashlib import sha256
from testpas.tasks import send_wave1_monitoring_email, send_wave1_code_entry_email, send_wave3_code_entry_email, send_confirmation_email_task, send_password_reset_email_task
# from testpas.settings import DEFAULT_FROM_EMAIL
from .models import *
from .utils import validate_token
import uuid
import os
import datetime
import pytz

from .models import Participant, SurveyProgress, Survey, UserSurveyProgress, Content
from .forms import CodeEntryForm, InterestForm, EligibilityForm, ConsentForm, UserRegistrationForm, PasswordResetForm, PasswordResetConfirmForm
import csv
from testpas.utils import get_current_time
from .timeline import get_timeline_day, get_study_day
from testpas.tasks import send_wave1_code_entry_email, send_wave3_code_entry_email


print(f"[DEBUG] Views module loaded")

def landing(request):
    """Landing page for unauthenticated users"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')

def _generate_next_participant_id():
    """Generate the next unique participant ID (P###), safe for concurrent signups."""
    last_participant = Participant.objects.select_for_update().order_by('-id').first()
    if last_participant and last_participant.participant_id:
        raw_id = last_participant.participant_id
        if raw_id.startswith('P') and raw_id[1:].isdigit():
            next_num = int(raw_id[1:]) + 1
            else:
            next_num = last_participant.id + 1
    else:
        next_num = 1
    return f"P{next_num:03d}"

def account_confirmation_pending(request):
    """Show confirmation pending message after account creation"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'account_confirmation_pending.html')

def test_all_challenges(request):
    """Test page with links to all challenges for quick testing"""
    return render(request, 'test_all_challenges.html')

@login_required
def home(request):
    """Home page - redirects authenticated users to dashboard"""
    return redirect('dashboard')

"""Information 2: Create Account"""
@csrf_exempt
def create_account(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Clear any existing session data to prevent user confusion
                request.session.flush()
                
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password']
                )
                    participant = None
                    for attempt in range(5):
                        try:
                            with transaction.atomic():
                                participant_id = _generate_next_participant_id()
                participant = Participant.objects.create(
                    user=user,
                    email=user.email,
                    phone_number=form.cleaned_data['phone_number'],
                                    full_name=form.cleaned_data['full_name'],
                                    address_line1=form.cleaned_data['address_line1'],
                                    address_line2=form.cleaned_data.get('address_line2', ''),
                                    city=form.cleaned_data['city'],
                                    state=form.cleaned_data['state'],
                                    zip_code=form.cleaned_data['zip_code'],
                    confirmation_token=str(uuid.uuid4()),
                                    participant_id=participant_id,
                    enrollment_date=timezone.now().date(),
                    is_confirmed=False
                )
                            break
                        except IntegrityError:
                            if attempt == 4:
                                raise

                    if participant is None:
                        user.delete()
                        raise Exception("Failed to create participant record. Please try again.")

                    # Send confirmation email asynchronously using Celery
                    try:
                        if not participant.is_confirmed and participant.email_status != 'confirmation_email_sent':
                            send_confirmation_email_task.delay(participant.id)
                            print(f"[SEND] Queued confirmation email for participant {participant.participant_id}")
                        else:
                            print(f"[SKIP] Skipping confirmation email for participant {participant.participant_id} - already confirmed or email already sent")
                except Exception as e:
                        # If Celery is not available, try synchronous sending as fallback
                        print(f"[ERROR] Celery task failed, trying synchronous email: {e}")
                        try:
                            if not participant.is_confirmed and participant.email_status != 'confirmation_email_sent':
                                print(f"[SEND] Sending confirmation email synchronously for participant {participant.participant_id}")
                                participant.send_confirmation_email()
                                print(f"[SEND] Successfully sent confirmation email to {participant.email}")
                            else:
                                print(f"[SKIP] Skipping synchronous confirmation email for participant {participant.participant_id} - already confirmed or email already sent")
                        except Exception as e2:
                            print(f"[ERROR] Failed to send account_confirmation email for participant {participant.participant_id}: {e2}")
                            import traceback
                            print(f"[ERROR] Traceback: {traceback.format_exc()}")
                            # Don't fail account creation if email fails - log it and continue

                    if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Account created. Please check your email to confirm.',
                            'redirect': '/account/confirmation-pending/'
                    })
                messages.success(request, "Account created. Please check your email to confirm.")
                    return redirect("account_confirmation_pending")
            except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    print(f"[ERROR] Error creating account for username {form.cleaned_data.get('username')}: {e}\n{error_trace}")
                    if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Failed to create account: {str(e)}"
                    }, status=500)
                    messages.error(request, f"Failed to create account: {str(e)}")
        else:
                print(f"[ERROR] Invalid form submission: {form.errors}")
                if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please correct the errors below.',
                    'errors': form.errors
                }, status=400)
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegistrationForm()

        if is_ajax:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
    return render(request, "create_account.html", {'form': form})

    except Exception as e:
        # Catch any unexpected errors and always return JSON for AJAX requests
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Unexpected error in create_account: {e}\n{error_trace}")
        if is_ajax:
            return JsonResponse({
                'status': 'error',
                'message': f"An unexpected error occurred: {str(e)}"
            }, status=500)
        # For non-AJAX requests, re-raise to show Django error page
        raise

"""Information 3: Email Confirmation to Activate Account"""
@csrf_exempt
def confirm_account(request, token):
    participant = Participant.objects.filter(confirmation_token=token).first()
    if not participant:
        messages.error(request, "Invalid or expired confirmation token.")
        return redirect("create_account")
    print(f"[DEBUG] Participant found: {participant.participant_id}")
    print(f"[DEBUG] Participant is confirmed: {participant.is_confirmed}")
    if participant.is_confirmed:
        messages.info(request, "Account already confirmed.")
    else:
        participant.is_confirmed = True
        participant.save()
        messages.success(request, "Account confirmed successfully.")
    
    return redirect("questionnaire_interest")

    
"""Information 3
Once participants create an account, they should be able to reset their password on the login page if they forget it."""
@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(f"[DEBUG] Login attempt for username: {username}")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            participant = Participant.objects.filter(user=user).first()
            if participant and not participant.is_confirmed:
                messages.error(request, "Please confirm your registration via the email link before logging in.")
                return render(request, 'login.html')
            survey_progress = SurveyProgress.objects.filter(user=user).first()
            if survey_progress and survey_progress.consent_submitted and survey_progress.consented is False:
                messages.error(request, "You declined consent and cannot log in.")
                return redirect('exit_screen_not_interested')
            if not survey_progress or not survey_progress.interest_submitted:
                messages.info(request, "Please complete the interest questionnaire before continuing.")
                login(request, user)
                return redirect('questionnaire_interest')
            print(f"[DEBUG] Authentication successful for user: {user.username}")
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')  # Redirect to next URL or dashboard
            print(f"[DEBUG] Redirecting to: {next_url}")
            return redirect(next_url)
            # return redirect('dashboard')  # Redirect to the dashboard after successful login
        else:
            print(f"[DEBUG] Authentication failed for username: {username}")
            messages.error(request, 'Invalid username or password.')
            return render(request, 'login.html')
    return render(request, 'login.html')

def password_reset(request):
    """Handle password reset request"""
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier'].strip()
            
            # Try to find user by email first, then by participant ID
            user = None
            email = None
            
            # Check if it looks like an email
            if '@' in identifier:
                try:
                    user = User.objects.get(email=identifier)
                    email = identifier
                except User.DoesNotExist:
                    pass
                except User.MultipleObjectsReturned:
                    # If multiple users with same email, take the first one
                    user = User.objects.filter(email=identifier).first()
                    email = identifier
            
            # If not found by email, try participant ID
            if not user:
                try:
                    participant = Participant.objects.get(participant_id=identifier)
                    user = participant.user
                    email = user.email
                except Participant.DoesNotExist:
                    pass
            
            if user and email:
                # Generate reset token
                token = Token.generate_token()
                Token.objects.create(recipient=user, token=token)
                
                # Send reset email asynchronously
                reset_link = f"{settings.BASE_URL}/password-reset-confirm/{token}/"
                try:
                    send_password_reset_email_task.delay(email, reset_link)
                    print(f"[SEND] Queued password reset email for {email}")
                except Exception as e:
                    # If Celery is not available, try synchronous sending as fallback
                    print(f"[ERROR] Celery task failed for password reset email, trying synchronous: {e}")
                    try:
                        send_mail(
                            'Password Reset Request - Confident Moves Intervention',
                            f'Click the following link to reset your password: {reset_link}\n\nIf you did not request this, please ignore this email.\n\nBest regards,\nThe Confident Moves Research Team',
                            settings.DEFAULT_FROM_EMAIL,
                            [email],
                            fail_silently=False,
                        )
                    except Exception as e2:
                        print(f"[ERROR] Failed to send password reset email to {email}: {e2}")
                        messages.error(request, 'Failed to send password reset email. Please try again later.')
                        return redirect('password_reset')
                
                messages.success(request, 'Password reset email sent. Please check your email.')
                return redirect('login')
            else:
                messages.error(request, 'No user found with that email address or participant ID.')
    else:
        form = PasswordResetForm()
    
    return render(request, 'password_reset.html', {'form': form})

def password_reset_confirm(request, token):
    """Handle password reset confirmation"""
    try:
        token_obj = Token.objects.get(token=token, used=False)
        user = token_obj.recipient
        
        if request.method == 'POST':
            form = PasswordResetConfirmForm(request.POST)
            if form.is_valid():
                user.set_password(form.cleaned_data['password'])
                user.save()
                token_obj.used = True
                token_obj.save()
                messages.success(request, 'Password reset successfully. You can now login with your new password.')
                return redirect('login')
        else:
            form = PasswordResetConfirmForm()
        
        return render(request, 'password_reset_confirm.html', {'form': form, 'token': token})
    except Token.DoesNotExist:
        messages.error(request, 'Invalid or expired reset link.')
        return redirect('login')

def questionnaire_interest(request):
    """Information 4: Interest Screening - Store IRB interest response"""
    if not request.user.is_authenticated:
        return redirect('login')

    participant = Participant.objects.filter(user=request.user).first()
    if participant and not participant.is_confirmed:
        messages.error(request, "Please confirm your registration via the email link before starting the survey.")
        return redirect('login')

    if request.method == 'GET':
        return render(request, 'questionnaire_interest.html')
    elif request.method == 'POST':
        # Check if user is authenticated before saving
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to submit your response.')
            return redirect('login')
        
        interested = request.POST.get('interested')
        reason = request.POST.get('reason', '')  # Get reason if provided
        
        # Save interest response to SurveyProgress model
        from .models import SurveyProgress
        survey_progress, created = SurveyProgress.objects.get_or_create(
            user=request.user,
            defaults={
                'interest_submitted': True,
                'interested': (interested == 'yes'),
            }
        )
        if not created:
            survey_progress.interest_submitted = True
            survey_progress.interested = (interested == 'yes')
            survey_progress.save()
        
        # Also save to Response model if Questions exist for interest screening
        # This provides detailed response tracking
        try:
            from .models import Survey, Question, Response
            interest_survey, _ = Survey.objects.get_or_create(
                title="Interest Screening",
                defaults={"description": "Information 4: Interest Screening Questionnaire"}
            )
            
            # Save the interest response
            question_interested, _ = Question.objects.get_or_create(
                survey=interest_survey,
                question_text="Are you interested in determining your eligibility?",
                defaults={}
            )
            Response.objects.create(
                user=request.user,
                question=question_interested,
                answer=interested
            )
            
            # Save reason if provided
            if interested == 'no' and reason:
                question_reason, _ = Question.objects.get_or_create(
                    survey=interest_survey,
                    question_text="If not interested, please provide a brief reason",
                    defaults={}
                )
                Response.objects.create(
                    user=request.user,
                    question=question_reason,
                    answer=reason
                )
        except Exception as e:
            print(f"[ERROR] Error saving interest response details: {e}")
        
        if interested == 'no':
            return redirect('exit_screen_not_interested')
        return redirect('questionnaire')

## Create Membership
def create_participant(request):
    if request.method == "POST":
        username = request.POST.get("username").strip()
        email = request.POST.get("email").strip()
        password = request.POST.get("password")
        phone_number = request.POST.get("phone_number").strip()

        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username already exists"}, status=400)
        if User.objects.filter(email=email).exists():
            return JsonResponse({"error": "Email already in use"}, status=400)

        # Create User only
        user = User.objects.create_user(username=username, email=email, password=password)
        return JsonResponse({"message": "User registered successfully! Please complete the eligibility questionnaire."})
    return render(request, "create_participant.html")

"""Information 4: Eligibility Questionnaire"""
@login_required
def questionnaire(request):
    survey_progress = SurveyProgress.objects.filter(user=request.user).first()
    if not survey_progress or not survey_progress.interest_submitted:
        messages.info(request, "Please complete the interest questionnaire before continuing.")
        return redirect('questionnaire_interest')
    if survey_progress.interest_submitted and survey_progress.interested is False:
        return redirect('exit_screen_not_interested')

    if request.method == "POST":
        user = request.user
        answers = request.POST
        print(f"Full POST Data: {answers}")

        age_value = answers.get("age", "0")
        if age_value == "lt18":
            age = 17
        elif age_value == "gt64":
            age = 65
        else:
            age = int(age_value)

        height_value = answers.get("height", "0")
        if height_value == "lt48":
            height = 47
        elif height_value == "gt83":
            height = 84
        else:
            height = int(height_value)
        
        weight_value = answers.get("weight", "0")
        if weight_value == "lt120":
            weight = 119
        elif weight_value == "gt500":
                weight = 501
        else:
            weight = int(weight_value)

        access_to_device = answers.get("has_device", "").strip().lower() == "yes"
        willing_no_other_study = answers.get("not_enroll_other", "").strip().lower() == "yes"
        willing_monitor = answers.get("comply_monitoring", "").strip().lower() == "yes"
        willing_contact = answers.get("respond_contacts", "").strip().lower() == "yes"
        dominant_hand = answers.get("dominant_hand", "").strip().lower()
        
        bmi = (weight / (height ** 2)) * 703 if height > 0 else 0
        print(f"Age: {age}, BMI: {bmi:.2f}, Device: {access_to_device}, No Other Study: {willing_no_other_study}")
        print(f"Monitor: {willing_monitor}, Contact: {willing_contact}, Dominant Hand: {dominant_hand}")

        # Eligibility logic: must agree to monitoring AND provide dominant hand if they agreed
        monitor_eligible = willing_monitor and (dominant_hand in ['left', 'right'] if willing_monitor else True)

        eligible = (
            (18 <= age <= 64) and
            (bmi >= 25) and
            access_to_device and
            willing_no_other_study and
            monitor_eligible and
            willing_contact
        )
        print(f"Eligibility Result: {eligible}")

        # Get or create the Eligibility Criteria survey
        survey, created = Survey.objects.get_or_create(
            title="Eligibility Criteria",
            defaults={"description": "Survey to determine participant eligibility"}
        )
        if created:
            print(f"[SEND] Created Eligibility Criteria survey automatically")
        
        # Save participant information including dominant hand
        try:
            participant = Participant.objects.get(user=user)
            # Add weight, height, and age to participant
            participant.weight = weight
            participant.height = height
            participant.age = age
            participant.bmi = bmi
            participant.willing_no_other_study = willing_no_other_study
            participant.willing_monitor = willing_monitor
            participant.willing_contact = willing_contact
            participant.dominant_hand = dominant_hand if dominant_hand in ['left', 'right'] else None
            participant.save()
        except Participant.DoesNotExist:
            pass  # Participant will be created later in the flow
        
        user_progress, created = UserSurveyProgress.objects.get_or_create(
            user=user,
            survey=survey,
            defaults={'eligible': eligible, 'consent_given': False}
        )
        if not created:
            user_progress.eligible = eligible
            user_progress.save()

        if eligible:
            return redirect("consent_form")
        else:
            return redirect(reverse("exit_screen_not_eligible"))
    return render(request, "questionnaire.html")

def send_wave_1_email(user):
    subject = "Wave 1 Online Survey Set - Ready"
    message = f"""
    Hi {user.username},

    Congratulations! You are now enrolled as a participant in the study.

    Your next task is to complete the Wave 1 Online Survey Set within 10 days. 
    Please check your email for further details.

    Best,  
    The Research Team
    """
    from_email = "vuleson59@gmail.com" 
    recipient_list = [user.email, "vuleson59@gmail.com"] 

    send_mail(subject, message, from_email, recipient_list)
    
"""Information 6: (Website) IRB Consent Form
Participants should be able to access the IRB consent form on the website."""
@login_required
def consent_form(request, survey_id=None):
    survey_progress = SurveyProgress.objects.filter(user=request.user).first()
    if survey_progress and survey_progress.consent_submitted and survey_progress.consented is False:
        return redirect('exit_screen_not_interested')
    if request.method == "POST":
        print(f"[DEBUG] Consent form POST data for {request.user.username}: {dict(request.POST)}")
        
        # Check if user declined consent
        consent_choice = request.POST.get('consent')
        if consent_choice == 'no':
            print(f"[ERROR] User {request.user.username} declined consent")
            consent_reason = request.POST.get('consent_reason', '').strip()
            # Track consent decision and reason (if provided)
            survey_progress, _ = SurveyProgress.objects.get_or_create(
                user=request.user,
                defaults={'consent_submitted': True, 'consented': False}
            )
            if survey_progress:
                survey_progress.consent_submitted = True
                survey_progress.consented = False
                survey_progress.save()

            try:
                consent_survey, _ = Survey.objects.get_or_create(
                    title="Consent Form",
                    defaults={"description": "Information 6: Consent to Participate"}
                )
                question_consent, _ = Question.objects.get_or_create(
                    survey=consent_survey,
                    question_text="I consent to participate in this study",
                    defaults={}
                )
                Response.objects.create(
                    user=request.user,
                    question=question_consent,
                    answer="no"
                )
                if consent_reason:
                    question_reason, _ = Question.objects.get_or_create(
                        survey=consent_survey,
                        question_text="If you do not consent, please provide a brief reason",
                        defaults={}
                    )
                    Response.objects.create(
                        user=request.user,
                        question=question_reason,
                        answer=consent_reason
                    )
            except Exception as e:
                print(f"[ERROR] Failed to save consent decline reason: {e}")
            return redirect('exit_screen_not_interested')
        
        form = ConsentForm(request.POST)
        if form.is_valid():
            user = request.user
            try:
                user_progress = UserSurveyProgress.objects.get(user=user, survey__title="Eligibility Criteria")
                if not user_progress.eligible:
                    print(f"[ERROR] User {user.username} not eligible")
                    messages.error(request, "You are not eligible to participate.")
                    return redirect("exit_screen_not_eligible")
            except UserSurveyProgress.DoesNotExist:
                print(f"[ERROR] No UserSurveyProgress found for {user.username}")
                messages.error(request, "No eligibility record found. Please contact support.")
                return render(request, "consent_form.html", {"form": form})

            participant, created = Participant.objects.get_or_create(user=user)
            if created:
                print(f"[SEND] Created Participant for {user.username}")

            # Set timeline for time compression testing
            current_time = timezone.now()
            user_progress.day_1 = current_time.date()  # Reset to today's date
            user_progress.timeline_reference_timestamp = current_time  # Set reference timestamp for time compression
            user_progress.consent_given = True
            user_progress.save()

            try:
                user_progress.save()
                print(f"[SEND] Saved progress for {user.username}: consent_given=True, day_1={user_progress.day_1}")
            except Exception as e:
                print(f"[ERROR] Failed to save progress for {user.username}: {e}")
                messages.error(request, "Failed to save consent data. Please try again.")
                return render(request, "consent_form.html", {"form": form})

            print(f"[SEND] Consent processed successfully for {user.username}")
            return redirect("dashboard")
        else:
            #logger.warning(f"Consent form invalid for {request.user.username}: {form.errors}")
            print(f"[ERROR] Consent form invalid for {request.user.username}: {form.errors}")
            messages.error(request, "Please correct the errors below.")
            return render(request, "consent_form.html", {"form": form})
    else:
        form = ConsentForm()
        return render(request, "consent_form.html", {'form': form})

# INFORMATION 10: Exit Screen for Not Eligible
def exit_screen_not_eligible(request):
    content, _ = Content.objects.get_or_create(
        content_type='exit_screen',
        defaults={
            'title': 'Exit Screen',
            'content': (
                '<h2>Thank You for Your Interest</h2>'
                '<p>Unfortunately, we are unable to enroll you at this time. Thank you for taking the time to learn more about the study.</p>'
                '<p>If you need any assistance or have any questions at any time, please contact Seungmin ("Seung") Lee (Principal Investigator) at '
                '<a href="mailto:seunglee@iastate.edu">seunglee@iastate.edu</a> or '
                '<a href="tel:517-898-0020">517-898-0020</a>.</p>'
                '<p>Sincerely,<br><br>The Confident Moves Research Team</p>'
            )
        }
    )
    return render(request, 'exit_screen_not_eligible.html', {'content': content})

@login_required
def survey_view(request, wave):
    """Handle survey views for different waves"""
    participant = get_object_or_404(Participant, user=request.user)
    
    # Check if participant is eligible for this survey
    if not participant.user.is_authenticated:
        return redirect('login')
    
    context = {
        'wave': wave,
        'participant': participant,
        'survey_title': f'Wave {wave} Survey',
    }   
    if wave == 1:
        context['survey_description'] = 'Wave 1 Online Survey Set - Complete this survey within 10 days to earn a $5 Amazon gift card.'
    elif wave == 2:
        context['survey_description'] = 'Wave 2 Online Survey Set - Complete this survey within 10 days to earn a $5 Amazon gift card.'
    elif wave == 3:
        context['survey_description'] = 'Wave 3 Online Survey Set - Complete this survey within 10 days to earn a $5 Amazon gift card.'
    else:
        context['survey_description'] = f'Wave {wave} Survey'
    return render(request, 'survey.html', context)

@login_required
def daily_log_view(request, wave):
    """Handle daily activity log views for different waves"""
    participant = get_object_or_404(Participant, user=request.user)
    
    context = {
        'wave': wave,
        'participant': participant,
        'log_title': f'Wave {wave} Daily Activity Log',
    }
    if wave == 1:
        context['log_description'] = 'Wave 1 Daily Activity Log - Record your physical activity for the past 7 days.'
    elif wave == 3:
        context['log_description'] = 'Wave 3 Daily Activity Log - Record your physical activity for the past 7 days.'
    else:
        context['log_description'] = f'Wave {wave} Daily Activity Log'
    return render(request, 'daily_log.html', context)

@login_required
def dashboard(request):
    # Clear any stored messages to prevent them from showing on dashboard
    storage = messages.get_messages(request)
    storage.used = True
    
    # Add debugging information
    print(f"[DEBUG] Dashboard accessed by user: {request.user.username}")
    print(f"[DEBUG] User ID: {request.user.id}")
    print(f"[DEBUG] User is authenticated: {request.user.is_authenticated}")
    
    survey_progress = SurveyProgress.objects.filter(user=request.user).first()
    if survey_progress and survey_progress.consent_submitted and survey_progress.consented is False:
        return redirect('exit_screen_not_interested')
    
    user_progress = UserSurveyProgress.objects.filter(user=request.user, survey__title="Eligibility Criteria").first()
    participant = Participant.objects.filter(user=request.user).first()
    progress_percentage = 0  # Default if not eligible or study_day not set
    code_error = request.GET.get('code_error')
    code_error_wave = request.GET.get('code_error_wave')
    
    # Fix data inconsistency: if randomization_completed is True but randomized_group is None
    if participant and participant.randomization_completed and participant.randomized_group is None:
        print(f"[FIX] Participant {participant.participant_id} has randomization_completed=True but randomized_group=None. Resetting randomization_completed.")
        participant.randomization_completed = False
        participant.save()
    
    # Add more debugging
    if participant:
        print(f"[DEBUG] Participant found: {participant.participant_id}")
        print(f"[DEBUG] Participant user: {participant.user.username}")
        print(f"[DEBUG] Participant randomized_group: {participant.randomized_group} (type: {type(participant.randomized_group)})")
    else:
        print(f"[DEBUG] No participant found for user {request.user.username}")
    
    # Add enrollment status debugging
    if user_progress:
        print(f"[DEBUG] User progress found:")
        print(f"[DEBUG] - Eligible: {user_progress.eligible}")
        print(f"[DEBUG] - Consent given: {user_progress.consent_given}")
        print(f"[DEBUG] - Day 1: {user_progress.day_1}")
    else:
        print(f"[DEBUG] No user progress found for user {request.user.username}")
    
    # Initialize variables for display
    current_date = get_current_time().date()
    within_wave1_period = False
    within_wave3_period = False
    days_until_start_wave1 = 0
    days_until_end_wave1 = 0
    start_date_wave1 = None
    end_date_wave1 = None
    study_day = 0
    day_11 = None
    day_21 = None
    day_95 = None
    day_104 = None
    day_120 = None
    day_133 = None
    # Use compressed timeline calculation consistently
    if user_progress and user_progress.eligible and user_progress.consent_given and participant:
        if not participant.enrollment_date:
            participant.enrollment_date = user_progress.day_1 or current_date
            participant.save()
        if user_progress.day_1 is not None:
            # Use compressed timeline calculation
            study_day = get_study_day(
                user_progress.day_1,
                now=get_current_time(),
                compressed=settings.TIME_COMPRESSION,
                seconds_per_day=settings.SECONDS_PER_DAY,
                reference_timestamp=user_progress.timeline_reference_timestamp
            )
            print(f"[DEBUG] Study day calculated: {study_day}")
            if participant:
                print(f"[DEBUG] Intervention button check: participant.randomized_group={participant.randomized_group}, study_day={study_day}, should_show={participant.randomized_group == 1 and 29 <= study_day <= 56}")
            
            # Calculate compressed timeline milestones
            # In compressed mode, these are study days, not calendar dates
            if settings.TIME_COMPRESSION:
                # For compressed timeline, we work with study days directly
                day_11_study_day = 8
                day_21_study_day = 21
                day_120_study_day = 120  # Wave 3 code entry starts on Day 120
                day_133_study_day = 133  # Wave 3 code entry ends on Day 133
                
                # Set day_120 and day_133 for display (using study day numbers as strings for TIME_COMPRESSION)
                day_120 = day_120_study_day
                day_133 = day_133_study_day
                
                # Calculate days until milestones based on study day difference
                days_until_start_wave1 = max(0, day_11_study_day - study_day)
                days_until_end_wave1 = max(0, day_21_study_day - study_day)
                days_until_start_wave3 = max(0, day_120_study_day - study_day)
                days_until_end_wave3 = max(0, day_133_study_day - study_day)
                
                # For display purposes, convert to approximate real time
                seconds_until_start_wave1 = days_until_start_wave1 * settings.SECONDS_PER_DAY
                seconds_until_end_wave1 = days_until_end_wave1 * settings.SECONDS_PER_DAY
                
                print(f"[DEBUG] Study Day: {study_day}")
                print(f"[DEBUG] Days until start wave 1: {days_until_start_wave1} (study days)")
                print(f"[DEBUG] Days until end wave 1: {days_until_end_wave1} (study days)")
                print(f"[DEBUG] Seconds until start wave 1: {seconds_until_start_wave1}")
                print(f"[DEBUG] Seconds until end wave 1: {seconds_until_end_wave1}")
            else:
                # For real timeline, use calendar dates
                # Start of Wave 1 code entry is Day 8 => +7 days from Day 1
                day_11 = user_progress.day_1 + timedelta(days=7)
                # End of Wave 1 code entry is Day 21 => +20 days from Day 1
            day_21 = user_progress.day_1 + timedelta(days=20)
            day_95 = user_progress.day_1 + timedelta(days=94)
            day_104 = user_progress.day_1 + timedelta(days=103)
                day_120 = user_progress.day_1 + timedelta(days=119)
                day_133 = user_progress.day_1 + timedelta(days=132)
                
                days_until_start_wave1 = max(0, (day_11 - current_date).days)
                days_until_end_wave1 = max(0, (day_21 - current_date).days)
                days_until_start_wave3 = max(0, (day_120 - current_date).days)
                days_until_end_wave3 = max(0, (day_133 - current_date).days)
                
            print(f"[DEBUG] Day 11: {day_11}")
            print(f"[DEBUG] Day 21: {day_21}")
            print(f"[DEBUG] Day 95: {day_95}")
            print(f"[DEBUG] Day 104: {day_104}")
            print(f"[DEBUG] Day 120: {day_120}")
            print(f"[DEBUG] Day 133: {day_133}")
            print(f"[DEBUG] Days until start wave 1: {days_until_start_wave1}")
            print(f"[DEBUG] Days until end wave 1: {days_until_end_wave1}")

            # ----  Study progress percentage ----
            total_study_days = 134  # Set this to your full study duration (Day 134 is when Information 27 is sent)
            progress_percentage = min(int((study_day / total_study_days) * 100), 100)
            print(f"[DEBUG] Progress percentage: {progress_percentage}")

            # Wave 1 code entry window: Days 8-21 inclusive
            within_wave1_period = study_day is not None and 8 <= study_day <= 21 and participant and not participant.code_entered
            print(f"[DEBUG] Within wave 1 period: {within_wave1_period}")
            # Wave 3 code entry window: Days 120-133 inclusive
            within_wave3_period = study_day is not None and 120 <= study_day <= 133 and participant and not participant.wave3_code_entered
            print(f"[DEBUG] Within wave 3 period: {within_wave3_period} (study_day={study_day}, participant={participant is not None}, wave3_code_entered={participant.wave3_code_entered if participant else 'N/A'})")
            
            # Set display dates for template
            if settings.TIME_COMPRESSION:
                start_date_wave1 = f"Study Day {day_11_study_day}"
                end_date_wave1 = f"Study Day {day_21_study_day}"
                start_date_wave3 = f"Study Day 120"
                end_date_wave3 = f"Study Day 133"
            else:
            start_date_wave1 = day_11
            end_date_wave1 = day_21
                start_date_wave3 = day_120
                end_date_wave3 = day_133

    # Check if Wave 1 survey should be shown (Days 1-7)
    show_wave1_survey = False
    wave1_survey_content = None
    if study_day and 1 <= study_day <= 7:
        show_wave1_survey = True
        wave1_survey_content, created = Content.objects.update_or_create(
            content_type='wave1_survey',
            defaults={
                'title': 'Wave 1 Online Survey',
                'content': (
                    '<a href="https://s.surveyplanet.com/u1ecju7x" '
                    'class="btn btn-primary" '
                    'target="_blank" '
                    'style="margin-top: 0.5rem;">'
                    'Open Survey 1'
                    '</a>'
                )
            }
    )

    # Check if Information 16 should be shown for Group 0 (Days 29-56)
    # Information 16: Control group sees this message from Day 29 to Day 56, removed on Day 57
    show_information_16 = False
    information_16_content = None
    if (study_day and 29 <= study_day <= 56 and 
        participant and participant.randomized_group == 0):
        show_information_16 = True
        print(f"[DEBUG] Showing Information 16 for Group 0 participant on Day {study_day}")

    # Check if Information 17 should be shown for Group 1 (Days 29-56)
    # Information 17: Intervention group sees this message from Day 29 to Day 56, removed on Day 57
    show_information_17 = False
    information_17_content = None
    if (study_day and 29 <= study_day <= 56 and 
        participant and participant.randomized_group is not None and participant.randomized_group == 1):
        show_information_17 = True
        print(f"[DEBUG] Showing Information 17 for Group 1 participant on Day {study_day}")

    # Check if Wave 2 survey should be shown (Days 57-63)
    show_wave2_survey = False
    wave2_survey_content = None
    if study_day and 57 <= study_day <= 63:
        show_wave2_survey = True
        # Create default content if it doesn't exist
        wave2_survey_content, _ = Content.objects.get_or_create(
            content_type='wave2_survey',
            defaults={
                'title': 'Wave 2 Online Survey',
                'content': (
                    '<a href="https://s.surveyplanet.com/rh37ybo5" '
                    'class="btn btn-primary" '
                    'target="_blank" '
                    'style="margin-top: 0.5rem;">'
                    'Open Survey 2'
                    '</a>'
                )
            }
        )

    # Wave 2 Status Tracking
    wave2_survey_status = "Not Available"
    wave2_survey_completed = False
    
    if study_day:
        if study_day < 57:
            wave2_survey_status = "Not Yet Available"
        elif 57 <= study_day <= 63:
            # Check if participant has completed Wave 2 survey
            # For now, we'll assume it's not completed (can be enhanced later with actual completion tracking)
            wave2_survey_status = "Available - Complete within 7 days"
        elif study_day > 63:
            # Check if participant completed it during the window
            # For now, we'll show as expired (can be enhanced with actual completion tracking)
            wave2_survey_status = "Window Expired"
    
    # Wave 2 Monitoring Status (if applicable)
    wave2_monitoring_status = "Not Applicable"
    if study_day and study_day >= 57:
        # Wave 2 has no physical activity monitoring according to the requirements
        wave2_monitoring_status = "No Monitoring Required"

    # Information 20: No Wave 2 Physical Activity Monitoring (Days 64-112)
    show_information_20 = False
    information_20_content = None
    if study_day and 64 <= study_day <= 112:
        show_information_20 = True

    # Check if Wave 3 survey should be shown (Days 113-119)
    show_wave3_survey = False
    wave3_survey_content = None
    if study_day and 113 <= study_day <= 119:
        show_wave3_survey = True
        # Create default content if it doesn't exist
        wave3_survey_content, _ = Content.objects.get_or_create(
            content_type='wave3_survey',
            defaults={
                'title': 'Wave 3 Online Survey',
                'content': (
                    '<a href="https://s.surveyplanet.com/tv3uouft" '
                    'class="btn btn-primary" '
                    'target="_blank" '
                    'style="margin-top: 0.5rem;">'
                    'Open Survey 3'
                    '</a>'
                )
            }
        )
    
    # Information 12: Show message after Wave 1 code entry (same as email)
    show_information_12 = False
    information_12_content = None
    if participant and participant.code_entered and participant.code_entry_date:
        show_information_12 = True
        code_date = participant.code_entry_date
        start_date = code_date + timedelta(days=1)
        end_date = code_date + timedelta(days=7)
        information_12_content = {
            'code_date': code_date.strftime('%m/%d/%Y'),
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
        }

    # Information 25: Show message after Wave 3 code entry (same as email)
    show_information_25 = False
    information_25_content = None
    if participant and participant.wave3_code_entered and participant.wave3_code_entry_date:
        show_information_25 = True
        # Format dates for display
        code_date = participant.wave3_code_entry_date
        start_date = code_date + timedelta(days=1)
        end_date = code_date + timedelta(days=7)
        information_25_content = {
            'code_date': code_date.strftime('%m/%d/%Y'),
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
        }
    
    # Information 27: Show message on Day 134 if code not entered
    show_information_27 = False
    information_27_content = None
    if study_day and study_day >= 134 and participant and not participant.wave3_code_entered:
        show_information_27 = True

    context = {
        'user': request.user,  # Explicitly pass the current user
        'progress': user_progress,
        'participant': participant,
        'within_wave1_period': within_wave1_period,
        'within_wave3_period': within_wave3_period,
        'days_until_start_wave1': days_until_start_wave1,
        'days_until_end_wave1': days_until_end_wave1,
        'start_date_wave1': start_date_wave1,
        'end_date_wave1': end_date_wave1,
        'days_until_start_wave3': days_until_start_wave3 if 'days_until_start_wave3' in locals() else 0,
        'days_until_end_wave3': days_until_end_wave3 if 'days_until_end_wave3' in locals() else 0,
        'start_date_wave3': start_date_wave3 if 'start_date_wave3' in locals() else None,
        'end_date_wave3': end_date_wave3 if 'end_date_wave3' in locals() else None,
        'study_day': study_day if user_progress else 0,  # For debugging
        'needs_consent': user_progress and user_progress.eligible and not user_progress.consent_given,  # New flag
        'progress_percentage': progress_percentage,
        'time_compression': settings.TIME_COMPRESSION,  # Add this for template debugging
        'intervention_points': participant.intervention_points if participant else 0,  # Add intervention points
        'show_test_intervention_button': settings.TEST_MODE,
        'show_wave1_survey': show_wave1_survey,
        'wave1_survey_content': wave1_survey_content,
        'show_information_16': show_information_16,
        'information_16_content': information_16_content,
        'show_information_17': show_information_17,
        'information_17_content': information_17_content,
        'show_wave2_survey': show_wave2_survey,
        'wave2_survey_content': wave2_survey_content,
        'wave2_survey_status': wave2_survey_status,
        'wave2_survey_completed': wave2_survey_completed,
        'wave2_monitoring_status': wave2_monitoring_status,
        'show_information_20': show_information_20,
        'information_20_content': information_20_content,
        'show_wave3_survey': show_wave3_survey,
        'wave3_survey_content': wave3_survey_content,
        'show_information_12': show_information_12,
        'information_12_content': information_12_content,
        'show_information_25': show_information_25,
        'information_25_content': information_25_content,
        'show_information_27': show_information_27,
        'information_27_content': information_27_content,
        'code_error': code_error,
        'code_error_wave': code_error_wave,
        # Debug info for intervention button visibility
        'debug_intervention': {
            'randomized_group': participant.randomized_group if participant else None,
            'study_day': study_day if user_progress else 0,
            'randomization_completed': participant.randomization_completed if participant else False,
            'should_show': participant and participant.randomized_group == 1 and 29 <= study_day <= 56 if (participant and user_progress) else False,
        } if participant else None,
    }
    return render(request, "dashboard.html", context)
# INFORMATION 11 & 22: Enter Code
@login_required
def enter_code(request, wave):
    """Handle code entry for Wave 1 or Wave 3"""
    participant = get_object_or_404(Participant, user=request.user)
    user_progress = UserSurveyProgress.objects.filter(user=request.user, survey__title="Eligibility Criteria").first()
    if not user_progress or not user_progress.day_1:
        messages.error(request, "Enrollment date not set. Contact support.")
        return redirect('home')

    # Use compressed timeline calculation consistently
    now = get_current_time()
    if user_progress and user_progress.day_1:
        study_day = get_study_day(
            user_progress.day_1,
            now=now,
            compressed=settings.TIME_COMPRESSION,
            seconds_per_day=settings.SECONDS_PER_DAY,
            reference_timestamp=user_progress.timeline_reference_timestamp
        )
    else:
        study_day = 1  # Default to day 1 if no day_1 set
    
    # Add debugging
    print(f"[DEBUG] Enter code - Wave: {wave}")
    print(f"[DEBUG] Study day: {study_day}")
    print(f"[DEBUG] Day 1: {user_progress.day_1}")
    print(f"[DEBUG] Current time: {now}")
    print(f"[DEBUG] Time compression: {settings.TIME_COMPRESSION}")
    print(f"[DEBUG] Seconds per day: {settings.SECONDS_PER_DAY}")
    
    if wave == 1:
        # Check if within Wave 1 window (Days 8-21)
        print(f"[DEBUG] Wave 1 check: 8 <= {study_day} <= 21 = {8 <= study_day <= 21}")
        if not (8 <= study_day <= 21):
            messages.error(request, f"Code entry is not available at this time. Current study day: {study_day}, required: 8-21")
            return redirect('home')
        if participant.code_entered:
            messages.info(request, "You have already entered the code for Wave 1.")
            return redirect('home')
    elif wave == 3:
        # Check if within Wave 3 window (Days 120-133)
        print(f"[DEBUG] Wave 3 check: 120 <= {study_day} <= 133 = {120 <= study_day <= 133}")
        if not (120 <= study_day <= 133):
            messages.error(request, f"Code entry is not available at this time. Current study day: {study_day}, required: 120-133")
            return redirect('home')
        if participant.wave3_code_entered:
            messages.info(request, "You have already entered the code for Wave 3.")
            return redirect('home')
    
    if request.method == 'POST':
        form = CodeEntryForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code'].strip().lower()
            # if code == settings.REGISTRATION_CODE.lower():
            if code == 'wavepa':
                if wave == 1:
                    # Jun 25: Add in store timeline day instead of date 
                    participant.code_entered = True
                    # Use compressed timeline calculation for code_entry_day
                    if user_progress and user_progress.day_1:
                        participant.code_entry_day = get_study_day(
                            user_progress.day_1,
                            now=now,
                            compressed=settings.TIME_COMPRESSION,
                            seconds_per_day=settings.SECONDS_PER_DAY,
                            reference_timestamp=user_progress.timeline_reference_timestamp
                        )
                    else:
                        participant.code_entry_day = 1
                    
                    # Set code entry date for email task
                    participant.code_entry_date = timezone.now().date()
                    participant.save()
                    
                    # Send Information 12 email asynchronously - use participant.id (database ID)
                    try:
                        send_wave1_code_entry_email.delay(participant.id)
                        print(f"[SEND] Queued Wave 1 code entry email for participant {participant.participant_id}")
                    except Exception as e:
                        # If Celery is not available, try synchronous sending as fallback
                        print(f"[ERROR] Celery task failed for Wave 1 code entry email, trying synchronous: {e}")
                        try:
                            send_wave1_code_entry_email(participant.id)
                        except Exception as e2:
                            print(f"[ERROR] Failed to send Wave 1 code entry email for participant {participant.participant_id}: {e2}")
                    
                    messages.success(request, "Code entered successfully!")
                    return redirect('code_success', wave=wave)
                    
                elif wave == 3:
                    participant.wave3_code_entered = True
                    participant.wave3_code_entry_date = timezone.now().date()
                    # Set Wave 3 code entry day using compressed timeline
                    if user_progress and user_progress.day_1:
                        participant.wave3_code_entry_day = get_study_day(
                            user_progress.day_1,
                            now=now,
                            compressed=settings.TIME_COMPRESSION,
                            seconds_per_day=settings.SECONDS_PER_DAY,
                            reference_timestamp=user_progress.timeline_reference_timestamp
                        )
                    else:
                        participant.wave3_code_entry_day = 1
                    participant.save()
                    
                    # Send Information 25 email - use participant.id (database ID)
                    # Try async first, fallback to sync if Celery is unavailable
                    try:
                        send_wave3_code_entry_email.delay(participant.id)
                        print(f"[SEND] Queued wave3_code_entry email for participant {participant.participant_id}")
                    except Exception as e:
                        print(f"[ERROR] Celery task failed, trying synchronous email: {e}")
                        try:
                            send_wave3_code_entry_email(participant.id)
                            print(f"[SEND] Sent wave3_code_entry email synchronously for participant {participant.participant_id}")
                        except Exception as e2:
                            print(f"[ERROR] Failed to send wave3_code_entry email for participant {participant.participant_id}: {e2}")
                    # # Send Information 25 email asynchronously - use participant.id (database ID)
                    # try:
                    #     send_wave3_code_entry_email.delay(participant.id)
                    #     print(f"[SEND] Queued Wave 3 code entry email for participant {participant.participant_id}")
                    # except Exception as e:
                    #     # If Celery is not available, try synchronous sending as fallback
                    #     print(f"[ERROR] Celery task failed for Wave 3 code entry email, trying synchronous: {e}")
                    #     try:
                    #         send_wave3_code_entry_email(participant.id)
                    #     except Exception as e2:
                    #         print(f"[ERROR] Failed to send Wave 3 code entry email for participant {participant.participant_id}: {e2}")
                    
                    messages.success(request, "Code entered successfully!")
                    return redirect('code_success', wave=wave)
                
                messages.success(request, "Code entered successfully!")
                return redirect('code_success', wave=wave)
            else:
                # Incorrect code - show warning under the code entry box
                error_message = "Incorrect code entered. Please try again."
                return redirect(f"{reverse('dashboard')}?code_error={error_message}&code_error_wave={wave}")
    else:
        form = CodeEntryForm()
    context = {
        'form': form,
        'wave': wave,
        'days_remaining': 20 - study_day if wave == 1 else 104 - study_day,
    }
    return render(request, 'enter_code.html', context)

def download_data(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pas_data.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Participant ID', 'Username', 'Email', 'Phone Number', 'Registration Code',
        'Confirmation Date', 'Interest Submitted', 'Interested', 'Eligibility Submitted',
        'Is Eligible', 'Consent Submitted', 'Consented', 'Wave 1 Code Entered',
        'Wave 1 Code Date', 'Group', 'Wave 3 Code Entered', 'Wave 3 Code Date'
    ])
    participants = Participant.objects.all()
    for p in participants:
        survey_progress = SurveyProgress.objects.filter(user=p.user).first()
        writer.writerow([
            p.participant_id, p.user.username, p.email, p.phone_number, 'wavepa',
            p.is_confirmed and p.token_expiration or '', survey_progress and survey_progress.interest_submitted or False,
            survey_progress and survey_progress.interested or False, survey_progress and survey_progress.eligibility_submitted or False,
            survey_progress and survey_progress.is_eligible or False, survey_progress and survey_progress.consent_submitted or False,
            survey_progress and survey_progress.consented or False, p.code_entered, p.code_entry_date,
            p.group, p.wave3_code_entered, p.wave3_code_entry_date
        ])
    return response

def code_success(request, wave):
    # return render(request, 'code_success.html', {'wave': wave})
    participant = Participant.objects.get(user=request.user)
    current_date = timezone.now().date()
    day_21 = participant.enrollment_date + timedelta(days=20)
    days_remaining = (day_21 - current_date).days
    return render(request, 'code_success.html', {'days_remaining': days_remaining})

def code_failure(request):
    participant = Participant.objects.get(user=request.user)
    current_date = timezone.now().date()
    day_21 = participant.enrollment_date + timedelta(days=20)
    days_remaining = (day_21 - current_date).days
    return render(request, 'code_failure.html', {'days_remaining': days_remaining})

def exit_screen_not_interested(request):
    content, _ = Content.objects.get_or_create(
        content_type='exit_screen',
        defaults={
            'title': 'Exit Screen',
            'content': (
                '<h2>Thank You for Your Interest</h2>'
                '<p>Unfortunately, we are unable to enroll you at this time. Thank you for taking the time to learn more about the study.</p>'
                '<p>If you need any assistance or have any questions at any time, please contact Seungmin ("Seung") Lee (Principal Investigator) at '
                '<a href="mailto:seunglee@iastate.edu">seunglee@iastate.edu</a> or '
                '<a href="tel:517-898-0020">517-898-0020</a>.</p>'
                '<p>Sincerely,<br><br>The Confident Moves Research Team</p>'
            )
        }
    )
    return render(request, 'exit_screen_not_interested.html', {'content': content})
def waiting_screen(request):
    try:
        content = Content.objects.get(content_type='waiting_screen')
        return render(request, "waiting_screen.html", {'content': content})
    except Content.DoesNotExist:
    return render(request, "waiting_screen.html")

def logout_view(request):
    print(f"[DEBUG] Logging out user: {request.user.username}")
    logout(request)
    # Clear all session data
    request.session.flush()
    print(f"[DEBUG] Session cleared, redirecting to landing")
    return redirect('landing')  # Redirect to the landing page after logout

def mark_challenge_completed(user, challenge_number, challenge_name):
    """Helper function to mark a challenge as completed for a user"""
    from .models import ChallengeCompletion, Participant, InterventionResponse
    
    try:
        participant = Participant.objects.get(user=user)
        # Record in ChallengeCompletion
        ChallengeCompletion.objects.get_or_create(
            user=user,
            participant=participant,
            challenge_number=challenge_number,
            defaults={'challenge_name': challenge_name}
        )
        
        # Also record in InterventionResponse for Group 1 participants
        if participant.randomized_group == 1:
            InterventionResponse.objects.create(
                user=user,
                participant=participant,
                challenge_number=challenge_number,
                challenge_name=challenge_name,
                response_type='challenge_completion',
                response_data={'action': 'completed', 'challenge_number': challenge_number}
            )
    except Participant.DoesNotExist:
        pass  # Skip if participant doesn't exist

def record_intervention_response(user, response_type, challenge_number=None, challenge_name=None, response_data=None, notes=None, request=None):
    """Helper function to record any intervention response for Group 1 participants"""
    from .models import Participant, InterventionResponse
    
    try:
        participant = Participant.objects.get(user=user)
        # Only record for Group 1 (intervention group)
        if participant.randomized_group == 1:
            ip_address = None
            if request:
                ip_address = request.META.get('REMOTE_ADDR')
            
            InterventionResponse.objects.create(
                user=user,
                participant=participant,
                challenge_number=challenge_number,
                challenge_name=challenge_name,
                response_type=response_type,
                response_data=response_data or {},
                notes=notes,
                ip_address=ip_address
            )
            return True
    except Participant.DoesNotExist:
        pass
    return False

@login_required
def intervention_access(request):
    """Handle intervention access for participants"""
    try:
        participant = Participant.objects.get(user=request.user)
        user_progress = UserSurveyProgress.objects.filter(user=request.user, survey__title="Eligibility Criteria").first()
        
        if not user_progress or not user_progress.consent_given:
            messages.error(request, "You must complete enrollment before accessing the intervention.")
            return redirect('dashboard')
        
        # Calculate study day using compressed timeline
        study_day = get_study_day(
            user_progress.day_1,
            now=get_current_time(),
            compressed=settings.TIME_COMPRESSION,
            seconds_per_day=settings.SECONDS_PER_DAY,
            reference_timestamp=user_progress.timeline_reference_timestamp
        )
        
        # Check if participant should have access
        # Information 16: Group 0 (control group) does NOT get intervention access during the study period.
        # Information 17: Only Group 1 (intervention group) gets access during Days 29-56
        has_access = False
        access_message = ""
        if participant.randomized_group == 1:  # Intervention group (Information 17)
            if 29 <= study_day <= 56:
                has_access = True
                access_message = "You have access to the intervention from Day 29 to Day 56."
                if not participant.intervention_access_granted:
                    participant.intervention_access_granted = True
                    participant.intervention_access_date = get_current_time()
                    participant.save()
            elif study_day < 29:
                access_message = "Intervention access will be available starting on Day 29."
            else:
                access_message = "Your intervention access period has ended (Days 29-56)."
        elif participant.randomized_group == 0:  # Control group (Information 16)
            # Control group does NOT get intervention access
            has_access = False
            access_message = "You are in the control group (Group 0). You do not have access to the intervention during the study period. Please maintain your usual daily routines. We will email you again in approximately 4 weeks for the next task."
        else:
            access_message = "You have not been assigned to a group yet."
        
        # Count completed challenges using the new tracking system
        from .models import ChallengeCompletion
        challenges_completed = ChallengeCompletion.objects.filter(user=request.user).count()
        total_challenges = 32  # Total number of challenges (1-32)
        
        # Calculate progress percentage
        progress_percent = (challenges_completed / total_challenges) * 100 if total_challenges > 0 else 0
        remaining_challenges = total_challenges - challenges_completed
        
        context = {
            'participant': participant,
            'study_day': study_day,
            'has_access': has_access,
            'access_message': access_message,
            'challenges_completed': challenges_completed,
            'total_challenges': total_challenges,
            'intervention_login_count': participant.intervention_login_count,
            'progress_percent': progress_percent,
            'remaining_challenges': remaining_challenges,
        }
        
        return render(request, 'intervention_access.html', context)  
    except Participant.DoesNotExist:
        messages.error(request, "Participant record not found.")
        return redirect('dashboard')

@login_required
def intervention_challenge_25(request):
    """Render Challenge 25: Leisure-Related Physical Activity demo."""
    participant = get_object_or_404(Participant, user=request.user)
    context = {
        'participant': participant,
        'current_points': participant.intervention_points,
    }
    return render(request, 'interventions/challenge_25.html', context)

@login_required
def intervention_challenge_1(request):
    """Render Challenge 1: Introduction."""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 101, "Introduction")
    context = {
        'participant': participant,
    }
    return render(request, 'interventions/challenge_1.html', context)

@login_required
@csrf_exempt
def record_commitment_click(request):
    """Record when a participant clicks the commitment button (AJAX endpoint)"""
    if request.method == 'POST':
        challenge_number = request.POST.get('challenge_number')
        challenge_name = request.POST.get('challenge_name', '')
        
        success = record_intervention_response(
            user=request.user,
            response_type='commitment_click',
            challenge_number=int(challenge_number) if challenge_number else None,
            challenge_name=challenge_name,
            response_data={'action': 'commitment_acknowledged'},
            request=request
        )
        
        return JsonResponse({'success': success})
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@login_required
def intervention_challenge_2(request):
    """Render Introductory Challenge 2: Contents."""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 102, "Contents")
    context = {
        'participant': participant,
    }
    return render(request, 'interventions/challenge_2.html', context)

@login_required
def intervention_challenge_3(request):
    """Render Introductory Challenge 3: Importance."""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 103, "Importance")
    context = {
        'participant': participant,
    }
    return render(request, 'interventions/challenge_3.html', context)

@login_required
def intervention_challenge_4(request):
    """Render Introductory Challenge 4: How to do (Part 1)."""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 104, "How to do (Part 1)")
    context = {
        'participant': participant,
    }
    return render(request, 'interventions/challenge_4.html', context)

@login_required
def intervention_challenge_5(request):
    """Render Introductory Challenge 5: How to do (Part 2)."""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 105, "How to do (Part 2)")
    context = {
        'participant': participant,
    }
    return render(request, 'interventions/challenge_5.html', context)

@login_required
def intervention_challenge_6(request):
    """Render Introductory Challenge 6: How to do (Part 3)."""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 106, "How to do (Part 3)")
    context = {
        'participant': participant,
    }
    return render(request, 'interventions/challenge_6.html', context)

@staff_member_required
def export_challenge_5_csv(request):
    """Export Challenge 5 responses as CSV (staff only)."""
    from .models import Challenge5Response
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="challenge5_responses.csv"'
    writer = csv.writer(response)
    writer.writerow(['username', 'participant_id', 'created_at', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7'])
    for r in Challenge5Response.objects.select_related('user', 'participant').all():
        writer.writerow([
            r.user.username,
            r.participant.participant_id,
            r.created_at.isoformat(),
            r.q1, r.q2, r.q3, r.q4, r.q5, r.q6, r.q7
        ])
    return response

@login_required
def ge_challenge_1(request):
    """General Education - Challenge 1: Introduction"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 1, "General Education 1")
    context = { 'participant': participant }
    return render(request, 'interventions/orientation_challenge_1.html', context)

@login_required
def ge_challenge_2(request):
    """General Education - Challenge 2: Contents"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 2, "General Education 2")
    context = { 'participant': participant }
    return render(request, 'interventions/orientation_challenge_2.html', context)

@login_required
def ge_challenge_3(request):
    """General Education - Challenge 3: Game"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 3, "General Education 3")
    context = { 'participant': participant }
    return render(request, 'interventions/orientation_challenge_3_game.html', context)

@login_required
def ge_challenge_4(request):
    """General Education - Challenge 4: Review"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 4, "General Education 4")
    context = { 'participant': participant }
    return render(request, 'interventions/orientation_challenge_4.html', context)

@login_required
def ge_challenge_5(request):
    """General Education - Challenge 5: Self-efficacy Survey"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 5, "General Education 5")
    if request.method == 'POST':
        try:
            q1 = int(request.POST.get('q1'))
            q2 = int(request.POST.get('q2'))
            q3 = int(request.POST.get('q3'))
            q4 = int(request.POST.get('q4'))
            q5 = int(request.POST.get('q5'))
            q6 = int(request.POST.get('q6'))
            q7 = int(request.POST.get('q7'))
        except (TypeError, ValueError):
            messages.error(request, 'Please answer all questions before submitting.')
            return redirect('orientation_challenge_5')

        from .models import Challenge5Response
        Challenge5Response.objects.create(
            user=request.user,
            participant=participant,
            q1=q1, q2=q2, q3=q3, q4=q4, q5=q5, q6=q6, q7=q7
        )
        messages.success(request, 'Responses saved. Thank you!')
        return redirect('intervention_access')

    context = { 'participant': participant }
    return render(request, 'interventions/orientation_challenge_5.html', context)

@login_required
def wr_challenge_6(request):
    """Work-Related Physical Activity - Challenge 6: Learning"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 6, "Work-Related Learning")
    context = { 'participant': participant }
    return render(request, 'interventions/wr_challenge_6.html', context)

@login_required
def wr_challenge_7(request):
    """Work-Related Physical Activity - Challenge 7: Easy Task"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 7, "Work-Related Easy Task")
    
    if request.method == 'POST':
        from .models import WorkRelatedChallenge7Response
        
        # Save responses
        WorkRelatedChallenge7Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
        )
        messages.success(request, "Your responses have been recorded. Thank you!")
        return redirect('intervention_access')
    
    context = { 'participant': participant }
    return render(request, 'interventions/wr_challenge_7.html', context)
@login_required
def wr_challenge_8(request):
    """Work-Related Physical Activity - Challenge 8: Story"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 8, "Work-Related Story")
    context = { 'participant': participant }
    return render(request, 'interventions/wr_challenge_8.html', context)

@login_required
def wr_challenge_9(request):
    """Work-Related Physical Activity - Challenge 9: Game"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 9, "Work-Related Game")
    context = { 'participant': participant }
    return render(request, 'interventions/wr_challenge_9_game.html', context)

@login_required
def wr_challenge_10(request):
    """Work-Related Physical Activity - Challenge 10: Technique"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 10, "Work-Related Technique")
    
    if request.method == 'POST':
        from .models import WorkRelatedChallenge10Response
        
        # Save responses
        WorkRelatedChallenge10Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
            answer5=request.POST.get('answer5', ''),
            answer6=request.POST.get('answer6', ''),
        )
        messages.success(request, "Your technique responses have been recorded. Thank you!")
        return redirect('intervention_access')
    context = { 'participant': participant }         
    return render(request, 'interventions/wr_challenge_10.html', context)

@login_required
def tr_challenge_11(request):
    """Transport-Related Physical Activity - Challenge 11: Learning"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 11, "Transport-Related Learning")
    context = { 'participant': participant }
    return render(request, 'interventions/tr_challenge_11.html', context)

@login_required
def tr_challenge_12(request):
    """Transport-Related Physical Activity - Challenge 12: Easy Task"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 12, "Transport-Related Easy Task")
    if request.method == 'POST':
        from .models import TransportRelatedChallenge12Response
        
        # Save responses
        TransportRelatedChallenge12Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
        )
        messages.success(request, "Your graded task responses have been recorded. Thank you!")
        return redirect('intervention_access')
    context = { 'participant': participant }
    return render(request, 'interventions/tr_challenge_12.html', context)

@login_required
def tr_challenge_13(request):
    """Transport-Related Physical Activity - Challenge 13: Story"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 13, "Transport-Related Story")
    context = { 'participant': participant }
    return render(request, 'interventions/tr_challenge_13.html', context)

@login_required
def tr_challenge_14(request):
    """Transport-Related Physical Activity - Challenge 14: Transport Game"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 14, "Transport-Related Game")
    context = { 
        'participant': participant,
        'current_points': participant.intervention_points if participant else 0
    }
    return render(request, 'interventions/tr_challenge_14_game.html', context)

@login_required
def tr_challenge_15(request):
    """Transport-Related Physical Activity - Challenge 15: Technique"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 15, "Transport-Related Technique")
    if request.method == 'POST':
        from .models import TransportRelatedChallenge15Response
        
        # Save responses
        TransportRelatedChallenge15Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
            answer5=request.POST.get('answer5', ''),
            answer6=request.POST.get('answer6', ''),
        )
        messages.success(request, "Your transport technique responses have been recorded. Thank you!")
        return redirect('intervention_access')
    context = {'participant': participant}
    return render(request, 'interventions/tr_challenge_15.html', context)

@login_required
def dom_challenge_16(request):
    """Domestic-Related Physical Activity - Challenge 16: Learning"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 16, "Domestic Learning")
    context = { 'participant': participant }
    return render(request, 'interventions/dom_challenge_16.html', context)

# Domestic-Related Physical Activity Challenges
@login_required
def dom_challenge_17(request):
    """Domestic-Related Physical Activity - Challenge 17: Easy Task"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 17, "Domestic Easy Task")

    if request.method == 'POST':
        from .models import DomesticRelatedChallenge17Response
        
        # Save responses
        DomesticRelatedChallenge17Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
        )
        messages.success(request, "Your domestic graded task responses have been recorded. Thank you!")
        return redirect('intervention_access')
    context = { 'participant': participant }
    return render(request, 'interventions/dom_challenge_17.html', context)

@login_required
def dom_challenge_18(request):
    """Domestic-Related Physical Activity - Challenge 18: Story"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 18, "Domestic Story")
    context = { 'participant': participant }
    return render(request, 'interventions/dom_challenge_18.html', context)

@login_required
def dom_challenge_19(request):
    """Domestic-Related Physical Activity - Challenge 19: Game"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 19, "Domestic Game")
    context = { 
        'participant': participant,
        'current_points': participant.intervention_points if participant else 0
    }
    return render(request, 'interventions/dom_challenge_19_game.html', context)

@login_required
def dom_challenge_20(request):
    """Domestic-Related Physical Activity - Challenge 20: Technique"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 20, "Domestic Technique")

    if request.method == 'POST':
        from .models import DomesticRelatedChallenge20Response
        
        # Save responses
        DomesticRelatedChallenge20Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
            answer5=request.POST.get('answer5', ''),
            answer6=request.POST.get('answer6', ''),
        )
        messages.success(request, "Your domestic technique responses have been recorded. Thank you!")
        return redirect('intervention_access')
    context = { 'participant': participant}
    return render(request, 'interventions/dom_challenge_20.html', context)

@login_required
def leisure_challenge_21(request):
    """Leisure-Related Physical Activity - Challenge 21: Learning"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 21, "Leisure Learning")
    context = { 'participant': participant }
    return render(request, 'interventions/leisure_challenge_21.html', context)

# Leisure-Related Physical Activity Challenges
@login_required
def leisure_challenge_22(request):
    """Leisure-Related Physical Activity - Challenge 22: Easy Task"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 22, "Leisure Easy Task")
    if request.method == 'POST':
        from .models import LeisureRelatedChallenge22Response
        
        # Save responses
        LeisureRelatedChallenge22Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
        )
        messages.success(request, "Your leisure graded task responses have been recorded. Thank you!")
        return redirect('intervention_access')
    context = { 'participant': participant }
    return render(request, 'interventions/leisure_challenge_22.html', context)

@login_required
def leisure_challenge_23(request):
    """Leisure-Related Physical Activity - Challenge 23: Learning Yoga"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 23, "Learning Yoga")
    context = { 'participant': participant }
    return render(request, 'interventions/leisure_challenge_23.html', context)

@login_required
def leisure_challenge_24(request):
    """Leisure-Related Physical Activity - Challenge 24: Yoga Practice 1"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 24, "Yoga Practice 1")
    context = { 'participant': participant }
    return render(request, 'interventions/leisure_challenge_24.html', context)

@login_required
def leisure_challenge_25(request):
    """Leisure-Related Physical Activity - Challenge 25: Yoga Practice 2"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 25, "Yoga Practice 2")
    context = { 'participant': participant }
    return render(request, 'interventions/leisure_challenge_25.html', context)

@login_required
def leisure_challenge_26(request):
    """Leisure-Related Physical Activity - Challenge 26: Game"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 26, "Leisure Game")
    context = { 
        'participant': participant,
        'current_points': participant.intervention_points if participant else 0
    }
    return render(request, 'interventions/leisure_challenge_26_game.html', context)

@login_required
def leisure_challenge_27(request):
    """Leisure-Related Physical Activity - Challenge 27: Technique"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 27, "Technique")
    
    if request.method == 'POST':
        from .models import LeisureRelatedChallenge27Response
        
        # Save responses
        LeisureRelatedChallenge27Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
            answer5=request.POST.get('answer5', ''),
            answer6=request.POST.get('answer6', ''),
        )
        messages.success(request, "Your leisure technique responses have been recorded. Thank you!")
        return redirect('intervention_access')
    
    context = { 'participant': participant }
    return render(request, 'interventions/leisure_challenge_27.html', context)

# Mindfulness Challenges (28–32)
@login_required
def mindfulness_challenge_28(request):
    """Mindfulness - Challenge 28: Learning"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 28, "Mindfulness Learning")
    context = {'participant': participant}
    return render(request, 'interventions/mindfulness_challenge_28.html', context)

@login_required
def mindfulness_challenge_29(request):
    """Mindfulness - Challenge 29: Easy Task"""
    participant = get_object_or_404(Participant, user=request.user)
    
    if request.method == 'POST':
        from .models import MindfulnessRelatedChallenge29Response
    # Save responses
        MindfulnessRelatedChallenge29Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
        )
        messages.success(request, "Your mindfulness responses have been recorded. Thank you!")
        return redirect('intervention_access')
    
    mark_challenge_completed(request.user, 29, "Mindfulness Easy Task")
    context = {'participant': participant}
    return render(request, 'interventions/mindfulness_challenge_29.html', context)

@login_required
def mindfulness_challenge_30(request):
    """Mindfulness - Challenge 30: Mindfulness Practice"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 30, "Mindfulness Practice")
    context = {'participant': participant}
    return render(request, 'interventions/mindfulness_challenge_30.html', context)

@login_required
def mindfulness_challenge_31(request):
    """Mindfulness - Challenge 31: Game"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 31, "Mindfulness Game")
    context = { 
        'participant': participant,
        'current_points': participant.intervention_points if participant else 0
    }
    return render(request, 'interventions/mindfulness_challenge_31.html', context)

@login_required
def mindfulness_challenge_32(request):
    """Mindfulness - Challenge 32: Technique"""
    participant = get_object_or_404(Participant, user=request.user)
    if request.method == 'POST':
        from .models import MindfulnessRelatedChallenge32Response
    # Save responses
        MindfulnessRelatedChallenge32Response.objects.create(
            user=request.user,
            participant=participant,
            answer1=request.POST.get('answer1', ''),
            answer2=request.POST.get('answer2', ''),
            answer3=request.POST.get('answer3', ''),
            answer4=request.POST.get('answer4', ''),
        )
        messages.success(request, "Your mindfulness responses have been recorded. Thank you!")
        return redirect('intervention_access')
    
    mark_challenge_completed(request.user, 32, "Mindfulness Technique")
    context = {'participant': participant}
    return render(request, 'interventions/mindfulness_challenge_32.html', context)

# Yoga Challenges
@login_required
def yoga_challenge_33(request):
    """Leisure-Related Physical Activity - Challenge 23: Learning Yoga"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 23, "Leisure Learning Yoga")
    context = { 'participant': participant }
    return render(request, 'interventions/yoga_challenge_33.html', context)

@login_required
def yoga_challenge_34(request):
    """Leisure-Related Physical Activity - Challenge 24: Yoga Practice 1"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 24, "Leisure Yoga Practice 1")
    context = { 'participant': participant }
    return render(request, 'interventions/yoga_challenge_34.html', context)

@login_required
def yoga_challenge_35(request):
    """Leisure-Related Physical Activity - Challenge 25: Yoga Practice 2"""
    participant = get_object_or_404(Participant, user=request.user)
    mark_challenge_completed(request.user, 25, "Leisure Yoga Practice 2")
    context = { 'participant': participant }
    return render(request, 'interventions/yoga_challenge_35.html', context)

@login_required
def update_intervention_points(request):
    """Handle AJAX requests to update intervention points."""
    if request.method == 'POST':
        try:
            participant = Participant.objects.get(user=request.user)
            points_to_add = int(request.POST.get('points', 0))
            
            # Update points
            participant.intervention_points += points_to_add
            participant.save()
            
            return JsonResponse({
                'success': True,
                'new_total': participant.intervention_points,
                'points_added': points_to_add
            })
        except (Participant.DoesNotExist, ValueError) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@login_required
def intervention_access_test(request):
    """Test Intervention Access: bypass study-day and group gating for developer testing."""
    try:
        participant = Participant.objects.get(user=request.user)
        user_progress = UserSurveyProgress.objects.filter(user=request.user, survey__title="Eligibility Criteria").first()
        
        if not user_progress or not user_progress.consent_given:
            messages.error(request, "You must complete enrollment before accessing the intervention.")
            return redirect('dashboard')
        has_access = True
        access_message = "TEST MODE: Intervention access granted for testing purposes."
        from .models import ChallengeCompletion
        challenges_completed = ChallengeCompletion.objects.filter(user=request.user).count()
        total_challenges = 32
        progress_percent = (challenges_completed / total_challenges) * 100 if total_challenges > 0 else 0
        remaining_challenges = total_challenges - challenges_completed
        
        context = {
            'participant': participant,
            'study_day': 50,
            'has_access': has_access,
            'access_message': access_message,
            'challenges_completed': challenges_completed,
            'total_challenges': total_challenges,
            'intervention_login_count': participant.intervention_login_count,
            'progress_percent': progress_percent,
            'remaining_challenges': remaining_challenges,
        }
        
        return render(request, 'intervention_access.html', context)
        
    except Participant.DoesNotExist:
        messages.error(request, "Participant record not found.")
        return redirect('dashboard')
