import random
# from bz2 import compress
from datetime import timedelta
import wave
from celery import shared_task
from django.core.mail import send_mail
from django.core.management import call_command
from testpas import settings
from django.utils import timezone
from testpas.models import Participant, EmailTemplate, UserSurveyProgress
from testpas.management.commands.seed_email_template import EMAIL_TEMPLATES
from testpas.utils import get_current_time
from .models import User
from .timeline import get_study_day
import logging

survey1_link = "https://s.surveyplanet.com/yuy9vvug"
survey2_link = "https://s.surveyplanet.com/jvbpp9rs"
survey3_link = "https://s.surveyplanet.com/oai3qp0z"

from .timeline import get_timeline_day
@shared_task
def run_daily_timeline_checks():
    print(f"[CELERY TASK] run_daily_timeline_checks started")
    users = User.objects.all()
    print(f"[CELERY TASK] Processing {users.count()} users")
    for user in users:
        try:
            daily_timeline_check(user)
        except Exception as e:
            print(f"[CELERY TASK] ERROR processing user {user.username}: {str(e)}")
    print(f"[CELERY TASK] run_daily_timeline_checks completed")

def daily_timeline_check(user):
    seconds_per_day = getattr(settings, 'SECONDS_PER_DAY', 86400)
    compressed = getattr(settings, 'TIME_COMPRESSION', False)

    """----------------------This is real time. Turn this one ON in production----------------------------------"""
    # today = get_timeline_day(user, compressed=settings.TIME_COMPRESSION, seconds_per_day=settings.SECONDS_PER_DAY)
    """---------------------------------------------------------------------------------------------------------"""
    
    """----------------------This is TIME COMPRESSION TESTING. Turn this one OFF in production------------------"""
    now = get_current_time()
    
    # Get user progress to use the same day_1 as frontend
    user_progress = UserSurveyProgress.objects.filter(
        user=user, 
        survey__title="Eligibility Criteria"
    ).first()
    ##
    ## Commented out previous code
    """
    if user_progress and user_progress.day_1:
        today = get_study_day(
            user_progress.day_1,
            now=now,
            compressed=compressed,
            seconds_per_day=seconds_per_day,
            reference_timestamp=user_progress.timeline_reference_timestamp
        )
    else:
        # Fallback to user.date_joined if no progress found
        today = get_timeline_day(
            user, 
            now=now,
            compressed=compressed,
            seconds_per_day=seconds_per_day,
            )"""
    # CRITICAL: Only proceed if user has completed eligibility and consent
    if not user_progress:
        print(f"[SKIP] User {user.id} has no UserSurveyProgress (not completed eligibility)")
        return
    
    if not user_progress.eligible:
        print(f"[SKIP] User {user.id} is not eligible")
        return
    
    if not user_progress.consent_given:
        print(f"[SKIP] User {user.id} has not given consent")
        return
    
    if not user_progress.day_1:
        print(f"[SKIP] User {user.id} has no day_1 set (consent not completed)")
        return
    
    # Calculate study day based on day_1 (which is set when consent is given)
    # CRITICAL: Use get_study_day with day_1, not get_timeline_day with user.date_joined
    # today = get_timeline_day(
    #     user, 
    today = get_study_day(
        user_progress.day_1,
        now=now,
        compressed=compressed,
        seconds_per_day=seconds_per_day,
        reference_timestamp=user_progress.timeline_reference_timestamp
    )
    """---------------------------------------------------------------------------------------------------------"""
    participant = getattr(user, 'participant', None)
    if not participant:
        print(f"[SKIP] No participant for user {user.id}")
        return
    
    # Skip participants who have completed the study (Day 134+)
    # Note: Information 24 is sent on Day 120, Information 27 is sent on Day 134
    if today and today > 140: # Skips users that are past the end of the study 
        print(f"[SKIP] User {user.id} completed study (Day {today} > 134)")
        return
    
    # CRITICAL: Refresh participant from database to get latest status
    # This prevents stale data issues when multiple Celery workers are running
    participant.refresh_from_db()
    print(f"[CHECK] User {user.id}, Day {today}, Status: {participant.email_status}")

    # Info 9 – Day 1: Wave 1 Online Survey Ready
    # Send on Day 1, allow catch-up only during Wave 1 period (Days 1-7)
    # Don't send on Day 57+ when Wave 2 is sent, as email_status gets overwritten
    # if today and 1 <= today <= 7 and participant.email_status != 'sent_wave1_survey':
    #     # Use atomic database update to prevent race condition with multiple workers
    #     # Only update if status is NOT already 'sent_wave1_survey'
    #     from django.db.models import F
    #     updated_count = Participant.objects.filter(
    #         id=participant.id
    #     ).exclude(
    #         email_status='sent_wave1_survey'
    #     ).update(email_status='sent_wave1_survey')
        
    #     if updated_count > 0:
    #         # Status was successfully updated (wasn't already sent) - safe to send email
    #         participant.refresh_from_db()  # Refresh to get updated status
    #         print(f"[EMAIL] Sending Wave 1 survey email to {participant.participant_id} (Day {today})")
    #         try:
    #             participant.send_email(
    #                 "wave1_survey_ready", 
    #                 extra_context={'username': user.username, 'participant_id': participant.participant_id},
    #                 mark_as='sent_wave1_survey'
    #             )
    #         except Exception as e:
    #             # If email fails, send_email will set status to 'failed', so we can retry later
    #             print(f"[EMAIL] Failed to send Wave 1 survey email to {participant.participant_id}: {str(e)}")
    #             # Re-raise to let Celery know the task failed
    #             raise
    #     else:
    #         # Another worker already set the status - skip sending to prevent duplicate
    #         participant.refresh_from_db()
    #         print(f"[EMAIL] SKIP - Wave 1 survey email already sent to {participant.participant_id} (status: {participant.email_status})")
    if today and 1 <= today <= 7 and participant.email_status not in ['sent_wave1_survey', 'sending']:
        # send_email() will handle atomic status updates internally
        print(f"[EMAIL] Sending Wave 1 survey email to {participant.participant_id} (Day {today})")
        try:
            participant.send_email(
                "wave1_survey_ready", 
                extra_context={'username': user.username, 'participant_id': participant.participant_id, 'survey_link': survey1_link},
                mark_as='sent_wave1_survey'
            )
            participant.wave1_survey_email_sent = True
            participant.save()
            print(f"[EMAIL] ✓ Successfully sent Wave 1 survey email to {participant.participant_id}")
        except Exception as e:
            # If email fails, send_email will set status to 'failed', so we can retry later
            print(f"[EMAIL] Failed to send Wave 1 survey email to {participant.participant_id}: {str(e)}")
            # Re-raise to let Celery know the task failed
            raise

    # Info 10 – Day 8: Wave 1 Physical Activity Monitoring – Ready
    # CRITICAL: Only send during Wave 1 period (Days 8-28). After Day 29 (randomization), don't send Wave 1 emails.
    # After randomization, email_status may be overwritten to 'sent_intervention_access', so we check if randomization_completed
    if (today and 8 <= today < 29 and  # Only during Wave 1 period, before randomization
        participant.wave1_survey_email_sent and
        not participant.wave1_monitor_email_sent and
        not participant.code_entry_date and 
        not participant.randomization_completed and  # Don't send if already randomized (past Day 29)
        participant.email_status not in ['sent_wave1_monitor', 'sent_wave1_missing', 'sending']):
        # send_email() will handle atomic status updates internally
        print(f"[INFO 10] Sending Wave 1 monitoring email to {participant.participant_id} (Day {today})")
        
        try:
            participant.send_email(
                "wave1_monitor_ready", 
                extra_context={'username': user.username, 'participant_id': participant.participant_id},
                mark_as='sent_wave1_monitor'
            )
            participant.wave1_monitor_email_sent = True
            participant.save()
            print(f"[INFO 10] ✓ Successfully sent Wave 1 monitoring email to {participant.participant_id}")
        except Exception as e:
            print(f"[INFO 10] ERROR: Failed to send Wave 1 monitoring email to {participant.participant_id}: {str(e)}")
            raise
    elif today and today >= 8:
        if participant.code_entry_date:
            print(f"[INFO 10] Skipped for {participant.participant_id}: code already entered on {participant.code_entry_date}")
        elif participant.email_status in ['sent_wave1_monitor', 'sent_wave1_missing']:
            print(f"[INFO 10] Skipped for {participant.participant_id}: email already sent (status: {participant.email_status})")
    #########################################################################################################################       
    # Info 14 – Day 22: Missing Code Entry (Wave 1)
    # IMPORTANT: Only send ONCE on Day 22 if code NOT entered. Then stop checking.
    # Whether they enter code or not, they move to randomization (Info 15) on Day 29.
    # CRITICAL: Only send during Wave 1 period (Days 22-28). After Day 29 (randomization), don't send Wave 1 emails.
    if (today and 22 <= today < 29 and  # Only during Wave 1 period, before randomization
        not participant.code_entered and
        not participant.wave1_missing_code_email_sent and
        not participant.randomization_completed and  # Don't send if already randomized (past Day 29)
        participant.email_status not in ['sent_wave1_missing', 'sending']):
        # send_email() will handle atomic status updates internally
        # Note: We only check for 'sent_wave1_missing' - NOT 'sent_wave1_monitor' 
        # because Info 10 (Day 8) and Info 14 (Day 22) are independent
        print(f"[INFO 14] Sending Wave 1 missing code email to {participant.participant_id} (Day {today}) - code NOT entered by Day 22")
        try:
            participant.send_email(
                "wave1_missing_code", 
                extra_context={'username': user.username, 'participant_id': participant.participant_id},
                mark_as='sent_wave1_missing'
            )
            participant.wave1_missing_code_email_sent = True
            participant.save()
            print(f"[INFO 14] Successfully sent Wave 1 missing code email to {participant.participant_id}")
        except Exception as e:
            print(f"[INFO 14] ERROR: Failed to send Wave 1 missing code email: {str(e)}")
            raise
    elif today and today >= 22:
        # Logging only - don't send after Day 29
        if participant.randomization_completed:
            print(f"[INFO 14] SKIP - User {user.id} already randomized (Day {today} >= 29), Wave 1 missing code email period has passed")
        elif participant.code_entered:
            print(f"[INFO 14] SKIP - User {user.id} already entered code, no missing code email needed")
        elif participant.email_status == 'sent_wave1_missing':
            print(f"[INFO 14] SKIP - Missing code email already sent to {participant.participant_id} (status: {participant.email_status})")

    #########################################################################################################################
    # Info 13 – 7 days after code entry: Return Monitor (Wave 1)
    # """ Commented out previous code
    #     if today == code_day + 7 and participant.email_status != 'sent_wave1_survey_return':
    #         print(f"[SEND] Info 13 (Return Monitor) to user {user.id}")
    #         participant.send_email("wave1_survey_return")
    #         participant.email_status = 'sent_wave1_survey_return'
    #         participant.save()
    #     """
    #     # if today and today >= target_day and participant.email_status != 'sent_wave1_survey_return':
    #     #     # Use atomic database update to prevent race condition with multiple workers
    #     #     # Only update if status is NOT already 'sent_wave1_survey_return'
    #     #     updated_count = Participant.objects.filter(
    #     #         id=participant.id
    #     #     ).exclude(
    #     #         email_status='sent_wave1_survey_return'
    #     #     ).update(email_status='sent_wave1_survey_return')
            
    #     #     if updated_count > 0:
    #     #         # Status was successfully updated (wasn't already sent) - safe to send email
    #     #         participant.refresh_from_db()  # Refresh to get updated status
    #     #         print(f"[SEND] Info 13 (Return Monitor) to user {user.id} (Day {today}, code entered on Day {code_day})")
    #     #         try:
    #     #             participant.send_email(
    #     #                 "wave1_survey_return", 
    #     #                 extra_context={'username': user.username, 'participant_id': participant.participant_id},
    #     #                 mark_as='sent_wave1_survey_return'
    #     #             )
    #     #         except Exception as e:
    #     #             print(f"[SEND] ERROR: Failed to send Return Monitor email to {participant.participant_id}: {str(e)}")
    #     #             raise
    #     #     else:
    #     #         # Another worker already set the status - skip sending to prevent duplicate
    #     #         participant.refresh_from_db()
    #     #         print(f"[SEND] SKIP - Return Monitor email already sent to {participant.participant_id} (status: {participant.email_status})")
    #########################################################################################################################       
    #     if today and today >= target_day and participant.email_status not in ['sent_wave1_survey_return', 'sending']:
    # IMPORTANT: Check code_entry_day (not code_entered flag) and only send if NOT already sent
    if participant.code_entry_day is not None and participant.email_status not in ['sent_wave1_survey_return', 'sending'] and not participant.wave1_survey_return_email_sent:
        code_day = participant.code_entry_day  # Use stored timeline day directly
        target_day = code_day + 7
        
        # Only send on the exact target day, not every day after
        if today and today == target_day:
            # send_email() will handle atomic status updates internally
            print(f"[SEND] Info 13 (Return Monitor) to user {user.id} (Day {today}, code entered on Day {code_day}, target day {target_day})")
            try:
                participant.send_email(
                    "wave1_survey_return", 
                    extra_context={'username': user.username, 'participant_id': participant.participant_id},
                    mark_as='sent_wave1_survey_return'
                )
                participant.wave1_survey_return_email_sent = True
                participant.save()
                print(f"[SEND] ✓ Successfully sent Return Monitor email to {participant.participant_id}")
            except Exception as e:
                print(f"[SEND] ERROR: Failed to send Return Monitor email to {participant.participant_id}: {str(e)}")
                raise
        else:
            print(f"[INFO 13] Waiting for target day {target_day} (currently Day {today}, code entered Day {code_day})")

    # Info 15 – Day 29: Randomization
    """
    The following Python code is checking if today is the 29th day of the month and if the participant's
    # randomized_group is None. If these conditions are met, it then randomizes the participant, sets
    # the randomized_group, and saves the changes.
    Information 15: (Website) Double-Blind Randomization
 	On Day 29, randomize (i.e., equal chance of being assigned to either group) the participants into either Group 0 (usual care group [i.e., control group]) or Group 1 (intervention group) at 7 AM Central Time (CT).
 
	    Group 0 (i.e., the usual care group) will be given the access to the intervention after the data collection is done from Day 113. 
    There will be no expiration date for the access for Group 0. We will not track their engagement with the intervention (e.g., the number of challenges completed) from Group 0.

    	Group 1 (i.e., the intervention group) will be given the access to the intervention from Day 29 to Day 56. We will track their engagement with the intervention (e.g., the number of challenges completed) from Group 1.
    """
    # This can happen if there was a bug or manual data change
    if participant.randomization_completed and participant.randomized_group is None:
        print(f"[FIX] Participant {participant.participant_id} has randomization_completed=True but randomized_group=None. Resetting randomization_completed.")
        participant.randomization_completed = False
        participant.save()
    
    # Info 15 – 2-Block Randomization
    # Only randomize on Day 29+ (catch-up if missed)
    if today and today >= 29 and not participant.randomization_completed:
        print(f"[RANDOMIZATION] Participant {participant.participant_id} on Day {today}, checking for randomization...")
        # Check if we need to assign this participant to a pair
        if participant.randomization_pair_id is None:
            # Find the next available pair or create a new one
            last_pair = Participant.objects.filter(
                randomization_pair_id__isnull=False
            ).order_by('-randomization_pair_id').first()
            
            if last_pair is None:
                # First participant ever
                pair_id = 1
                position = 1
            else:
                # Check if the last pair is complete (has 2 participants)
                pair_participants = Participant.objects.filter(
                    randomization_pair_id=last_pair.randomization_pair_id
                ).count()
                
                if pair_participants < 2:
                    # Join the existing incomplete pair
                    pair_id = last_pair.randomization_pair_id
                    position = 2
                else:
                    # Create a new pair
                    pair_id = last_pair.randomization_pair_id + 1
                    position = 1
            
            participant.randomization_pair_id = pair_id
            participant.randomization_position = position
            participant.save()
        
        # The 2-block randomization procedure starts here
        pair_participants = Participant.objects.filter(
            randomization_pair_id=participant.randomization_pair_id
        ).order_by('id')  # Order by enrollment time (earlier ID = earlier enrollment)
        
        if len(pair_participants) == 2:
            # Both participants in the pair are ready for randomization
            # First participant (earlier enrollment) gets random assignment
            first_participant = pair_participants[0]
            second_participant = pair_participants[1]
            
            # Check if first participant is already randomized (from when they were alone)
            if first_participant.randomization_completed and first_participant.randomized_group is not None:
                # First participant already randomized, assign second participant to opposite group
                first_group = first_participant.randomized_group
                second_group = 1 - first_group  # Opposite group
                # Assign groups to second participant
                second_participant.randomized_group = second_group
                second_participant.group = second_group
                second_participant.group_assigned = True
                second_participant.randomization_completed = True
                second_participant.save()
                # Log the randomization result
                print(f"[2-BLOCK RANDOMIZE] Pair {participant.randomization_pair_id}: "
                      f"First participant (ID {first_participant.participant_id}) already in Group {first_group}, "
                      f"Second participant (ID {second_participant.participant_id}) -> Group {second_group}")
                
                # Send email to second participant only (first already received theirs)
                try:
                    if second_participant.randomized_group == 0:
                        second_participant.send_email("intervention_access_later", extra_context={
                            "username": second_participant.user.username
                        }, mark_as='sent_intervention_access')
                        second_participant.randomization_email_sent = True
                        second_participant.randomization_email_sent_date = timezone.now().date()
                        second_participant.save()
                        print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_later email to {second_participant.participant_id}")
                    elif second_participant.randomized_group == 1:
                        second_participant.send_email("intervention_access_immediate", extra_context={
                            "username": second_participant.user.username,
                            "login_link": settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "https://your-login-page.com"
                        }, mark_as='sent_intervention_access')
                        second_participant.randomization_email_sent = True
                        second_participant.randomization_email_sent_date = timezone.now().date()
                        second_participant.save()
                        print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_immediate email to {second_participant.participant_id}")
                except Exception as e:
                    print(f"[2-BLOCK RANDOMIZE] ERROR: Failed to send email to second participant {second_participant.participant_id}: {str(e)}")
            else:
                # Neither participant is randomized yet - do full 2-block randomization
                # Fair coin flip for first participant
                first_group = random.choice([0, 1])
                second_group = 1 - first_group  # Opposite group
                
                # Assign groups
                first_participant.randomized_group = first_group
                first_participant.group = first_group
                first_participant.group_assigned = True
                first_participant.randomization_completed = True
                first_participant.save()
                
                second_participant.randomized_group = second_group
                second_participant.group = second_group
                second_participant.group_assigned = True
                second_participant.randomization_completed = True
                second_participant.save()
                
                print(f"[2-BLOCK RANDOMIZE] Pair {participant.randomization_pair_id}: "
                      f"First participant (ID {first_participant.participant_id}) -> Group {first_group}, "
                      f"Second participant (ID {second_participant.participant_id}) -> Group {second_group}")
                
                # Send notification emails to both
                try:
                    if first_participant.randomized_group == 0:
                        first_participant.send_email("intervention_access_later", extra_context={
                            "username": first_participant.user.username
                        }, mark_as='sent_intervention_access')
                        first_participant.randomization_email_sent = True
                        first_participant.randomization_email_sent_date = timezone.now().date()
                        first_participant.save()
                        print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_later email to {first_participant.participant_id}")
                    elif first_participant.randomized_group == 1:
                        first_participant.send_email("intervention_access_immediate", extra_context={
                            "username": first_participant.user.username,
                            "login_link": settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "https://your-login-page.com"
                        }, mark_as='sent_intervention_access')
                        first_participant.randomization_email_sent = True
                        first_participant.randomization_email_sent_date = timezone.now().date()
                        first_participant.save()
                        print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_immediate email to {first_participant.participant_id}")
                except Exception as e:
                    print(f"[2-BLOCK RANDOMIZE] ERROR: Failed to send email to first participant {first_participant.participant_id}: {str(e)}")
                
                try:
                    if second_participant.randomized_group == 0:
                        second_participant.send_email("intervention_access_later", extra_context={
                            "username": second_participant.user.username
                        }, mark_as='sent_intervention_access')
                        second_participant.randomization_email_sent = True
                        second_participant.randomization_email_sent_date = timezone.now().date()
                        second_participant.save()
                        print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_later email to {second_participant.participant_id}")
                    elif second_participant.randomized_group == 1:
                        second_participant.send_email("intervention_access_immediate", extra_context={
                            "username": second_participant.user.username,
                            "login_link": settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "https://your-login-page.com"
                        }, mark_as='sent_intervention_access')
                        second_participant.randomization_email_sent = True
                        second_participant.randomization_email_sent_date = timezone.now().date()
                        second_participant.save()
                        print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_immediate email to {second_participant.participant_id}")
                except Exception as e:
                    print(f"[2-BLOCK RANDOMIZE] ERROR: Failed to send email to second participant {second_participant.participant_id}: {str(e)}")
        elif len(pair_participants) == 1:
            # Only one participant in pair - randomize them now, second participant will get opposite when they join
            single_participant = pair_participants[0]
            
            # Random assignment for the single participant
            assigned_group = random.choice([0, 1])
            single_participant.randomized_group = assigned_group
            single_participant.group = assigned_group
            single_participant.group_assigned = True
            single_participant.randomization_completed = True
            single_participant.save()
            
            print(f"[2-BLOCK RANDOMIZE] Single participant in Pair {participant.randomization_pair_id}: "
                  f"Participant (ID {single_participant.participant_id}) -> Group {assigned_group} (waiting for pair)")
            
            # Send notification email to the single participant
            try:
                if single_participant.randomized_group == 0:
                    single_participant.send_email("intervention_access_later", extra_context={
                        "username": single_participant.user.username
                    }, mark_as='sent_intervention_access')
                    single_participant.randomization_email_sent = True
                    single_participant.randomization_email_sent_date = timezone.now().date()
                    single_participant.save()
                    print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_later email to {single_participant.participant_id}")
                elif single_participant.randomized_group == 1:
                    single_participant.send_email("intervention_access_immediate", extra_context={
                        "username": single_participant.user.username,
                        "login_link": settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "https://your-login-page.com"
                    }, mark_as='sent_intervention_access')
                    single_participant.randomization_email_sent = True
                    single_participant.randomization_email_sent_date = timezone.now().date()
                    single_participant.save()
                    print(f"[2-BLOCK RANDOMIZE] Sent intervention_access_immediate email to {single_participant.participant_id}")
            except Exception as e:
                print(f"[2-BLOCK RANDOMIZE] ERROR: Failed to send email to single participant {single_participant.participant_id}: {str(e)}")
        else:
            print(f"[2-BLOCK RANDOMIZE] Pair {participant.randomization_pair_id} has unexpected number of participants: {len(pair_participants)}")
    ############### NEW DOUBLE BLIND RANDOMIZATION MECHANICS ENDS HERE ######################
    """
    Information 18: Day 57: Wave 2 Survey Ready
    (Email) Wave 2 Online Survey Set – Ready. On Day 57, send this email to every participant from any group.
    Allow catch-up if missed (send if on Day 57 or later but not sent yet).
    """
    if today and today >= 57 and not participant.wave2_survey_email_sent:
        # Use atomic database update to prevent race condition with multiple workers
        # Only update if wave2_survey_email_sent is NOT already True
        updated_count = Participant.objects.filter(
            id=participant.id,
            wave2_survey_email_sent=False
        ).update(wave2_survey_email_sent=True)
        
        if updated_count > 0:
            # Status was successfully updated (wasn't already sent) - safe to send email
            participant.refresh_from_db()  # Refresh to get updated status
            """
            # Use mark_as to set specific status that won't conflict with Wave 1 status
            participant.send_email(
                "wave2_survey_ready",
                mark_as='sent_wave2_survey',  # Set specific status to avoid overwriting Wave 1 status
                extra_context={
                    # "participant_id": participant.participant_id,
                    "username": participant.user.username,
                }
            )
            participant.wave2_survey_email_sent = True
            participant.save()
            print(f"[INFO 18] Successfully sent Wave 2 survey email to {participant.participant_id}")
        except Exception as e:
            print(f"[INFO 18] ERROR: Failed to send Wave 2 survey email to {participant.participant_id}: {str(e)}")
            # Don't set wave2_survey_email_sent = True if email failed, so it can be retried"""
            print(f"[INFO 18] Sending Wave 2 survey email to {participant.participant_id} (Day {today})")
            try:
                # Use mark_as to set specific status that won't conflict with Wave 1 status
                participant.send_email(
                    "wave2_survey_ready",
                    mark_as='sent_wave2_survey',  # Set specific status to avoid overwriting Wave 1 status
                    extra_context={
                        # "participant_id": participant.participant_id,
                        "username": participant.user.username,
                        "survey_link": survey2_link,
                    }
                )
                participant.wave2_survey_email_sent = True
                participant.save()
                print(f"[INFO 18] Successfully sent Wave 2 survey email to {participant.participant_id}")
            except Exception as e:
                # If email fails, reset the flag so it can be retried
                Participant.objects.filter(id=participant.id).update(wave2_survey_email_sent=False)
                print(f"[INFO 18] ERROR: Failed to send Wave 2 survey email to {participant.participant_id}: {str(e)}")
                raise
        else:
            # Another worker already set the flag - skip sending to prevent duplicate
            participant.refresh_from_db()
            print(f"[INFO 18] SKIP - Wave 2 survey email already sent to {participant.participant_id}")

    """
    Information 20: Day 64 – No Wave 2 Physical Activity Monitoring
    (Email) From Day 64 to Day 112, send this email to every participant from any group (i.e., both control and intervention group).
    Same information should appear on the website.
    """
    # Information 20: Send No Wave 2 Monitoring Email on Day 64
    if today and today == 64 and not participant.wave2_monitoring_notice_sent:
        participant.send_email(
            "wave2_no_monitoring",
            extra_context={
                # "participant_id": participant.participant_id,
                "username": participant.user.username,
            }
        )
        participant.wave2_monitoring_notice_sent = True
        participant.save()

    """
    Information 21: Day 113: Wave 3 Survey Ready
    (Email) Wave 3 Online Survey Set – Ready. On Day 113, send this email to every participant from any group.  
    """
    if today and today == 113 and not participant.wave3_survey_email_sent:
        participant.send_email(
            "wave3_survey_ready", 
            extra_context={
                "username": participant.user.username,
                "survey_link": survey3_link,})
        participant.wave3_survey_email_sent = True
        participant.save()

    """
    Information 23: Day 120: Wave 3 Monitoring Ready
    (Email) Wave 3 Physical Activity Monitoring Ready. On Day 120, send this email to every participant from any group.
    Allow catch-up if missed (send if on Day 120 or later but not sent yet).
    """
    if today and today >= 120 and not participant.wave3_monitor_ready_sent and participant.wave3_survey_email_sent:
        try:
            print(f"[INFO 23] Sending Wave 3 Monitoring Ready email to {participant.participant_id} (Day {today})")
            participant.send_email("wave3_monitoring_ready", extra_context={"username": user.username})
            participant.wave3_monitor_ready_sent = True
            participant.save()
            print(f"[INFO 23] Successfully sent Wave 3 Monitoring Ready email to {participant.participant_id}")
        except Exception as e:
            print(f"[INFO 23] ERROR: Failed to send Wave 3 Monitoring Ready email to {participant.participant_id}: {str(e)}")
            # Don't set wave3_monitor_ready_sent = True if email failed, so it can be retried

    # Info 27 – Day 134: Missed Wave 3 Code Entry (Study End)
    if today and today == 134 and not participant.wave3_code_entered and not participant.wave3_missing_code_sent:
        participant.send_email("wave3_missing_code")
        participant.wave3_missing_code_sent = True
        participant.save()

    """
    Study End Survey & Monitor Return Email
    Send 8 days after Wave 3 code entry (if code was entered).
    Note: Information 24 is the website display for Wave 3 code entry (Days 120-133), not an email.
    """
    if participant.wave3_code_entered and participant.wave3_code_entry_day:
        # Calculate target day: code entry day + 7 days
        target_day = participant.wave3_code_entry_day + 7
        if today and today >= target_day and not participant.wave3_survey_monitor_return_sent:
            try:
                print(f"[STUDY END] Sending Study End Survey & Monitor Return email to {participant.participant_id} (Day {today}, code entered on Day {participant.wave3_code_entry_day})")
                participant.send_email("study_end", extra_context={"username": user.username})
                participant.wave3_survey_monitor_return_sent = True
                participant.wave3_survey_monitor_return_date = timezone.now().date()
                participant.save()
                print(f"[STUDY END] Successfully sent Study End Survey & Monitor Return email to {participant.participant_id}")
            except Exception as e:
                print(f"[STUDY END] ERROR: Failed to send Study End Survey & Monitor Return email to {participant.participant_id}: {str(e)}")
                # Don't set wave3_survey_monitor_return_sent = True if email failed, so it can be retried

@shared_task
def send_confirmation_email_task(participant_id):
    """Send account confirmation email asynchronously"""
    try:
        participant = Participant.objects.get(id=participant_id)
        participant.send_confirmation_email()
        print(f"[SEND] Sent confirmation email to {participant.email}")
    except Participant.DoesNotExist:
        print(f"[ERROR] Participant {participant_id} not found for confirmation email")
        pass
    except Exception as e:
        print(f"[ERROR] Error sending confirmation email for participant {participant_id}: {str(e)}")
        pass

@shared_task
def send_password_reset_email_task(email, reset_link):
    """Send password reset email asynchronously"""  
    try:
        send_mail(
            'Password Reset Request - Confident Moves Intervention',
            f'Click the following link to reset your password: {reset_link}\n\nIf you did not request this, please ignore this email.\n\nBest regards,\nThe Confident Moves Research Team',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        print(f"[SEND] Sent password reset email to {email}")
    except Exception as e:
        print(f"[ERROR] Error sending password reset email to {email}: {str(e)}")
        pass

@shared_task
def send_wave1_survey_return_email(participant_id):
    """Information 13: Survey by Today & Return Monitor (Wave 1)"""
    try:
        participant = Participant.objects.get(id=participant_id)
        if participant.email_status == 'sent_wave1_survey_return':
            print(f"[SKIP] Skipping wave1_survey_return for {participant.email}: already sent")
            return
        # Schedule 8 days after code_entry_date at 7 AM CT
        now = timezone.now()
        send_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now.hour >= 7:
            send_time += timedelta(days=1)
        participant.send_email('wave1_survey_return', extra_context={'username': participant.user.username})
        participant.email_status = 'sent_wave1_survey_return'
        participant.save()
        print(f"[SEND] Sent wave1_survey_return to {participant.email}")
    except Participant.DoesNotExist:
        print(f"[ERROR] Participant {participant_id} not found for wave1_survey_return")
        pass
    except Exception as e:
        print(f"[ERROR] Error sending wave1_survey_return for participant {participant_id}: {str(e)}")
        pass

@shared_task
def send_wave1_code_entry_email(participant_id):
    """Information 12: Physical Activity Monitoring Tomorrow (Wave 1)"""
    from django.db import connections
    try:
        # Ensure fresh database connection
        connections.close_all()
        
        participant = Participant.objects.get(id=participant_id)
        # Check email_status to prevent duplicates
        if participant.email_status == 'sent_wave1_code':
            print(f"[SKIP] Skipping wave1_code_entry for {participant.email}: already sent")
            return
        
        code_date = participant.code_entry_date
        if not code_date:
            print(f"[ERROR] No code entry date for participant {participant_id}")
            return
        
        start_date = code_date + timedelta(days=1)
        end_date = code_date + timedelta(days=7)
        
        participant.send_email(
            'wave1_code_entry',
            extra_context={
                'username': participant.user.username,
                'code_date': code_date.strftime('%m/%d/%Y'),
                'start_date': start_date.strftime('%m/%d/%Y'),
                'end_date': end_date.strftime('%m/%d/%Y'),
            }
        )
        participant.email_status = 'sent_wave1_code'
        participant.save()
        print(f"[SEND] Sent wave1_code_entry to {participant.email}")
    except Participant.DoesNotExist:
        print(f"[ERROR] Participant {participant_id} not found for wave1_code_entry")
        pass
    except Exception as e:
        pass
    finally:
        # Close database connections
        connections.close_all()

@shared_task
def send_wave1_monitoring_email(participant_id):
    """Send Wave 1 Physical Activity Monitoring email to participant."""
    """Information 10: Wave 1 Physical Activity Monitoring Ready"""
    try:
        participant = Participant.objects.get(id=participant_id)
        participant.send_email(
            'wave1_monitor_ready',
            extra_context={
                'username': participant.user.username,
                'participant_id': participant.participant_id,
            }
        )
        participant.email_status = 'sent'
        participant.email_send_date = timezone.now().date()
        participant.save()
        print(f"[SEND] Sent Wave 1 monitoring email to {participant.participant_id}")
    except Participant.DoesNotExist:
        print(f"[ERROR] Participant {participant_id} not found")
        pass
    except EmailTemplate.DoesNotExist:  
        print(f"[ERROR] Wave 1 monitor ready email template not found")
        pass
    except Exception as e:
        print(f"[ERROR] Failed to send Wave 1 monitoring email to {participant_id}: {e}")
        pass

@shared_task
def send_wave3_code_entry_email(participant_id):
    """Information 25: Physical Activity Monitoring Tomorrow (Wave 3)"""
    from django.db import connections
    try:
        # Ensure fresh database connection
        connections.close_all()
        
        participant = Participant.objects.get(id=participant_id)
        
        # Calculate dates
        code_date = participant.wave3_code_entry_date
        if not code_date:
            print(f"[ERROR] No Wave 3 code entry date for participant {participant_id}")
            return
        # Plus 1 day since it is tomorrow
        start_date = code_date + timedelta(days=1)
        end_date = code_date + timedelta(days=7)
        
        participant.send_email(
            'wave3_code_entry',
            extra_context={
                'code_date': code_date.strftime('%m/%d/%Y'),
                'start_date': start_date.strftime('%m/%d/%Y'),
                'end_date': end_date.strftime('%m/%d/%Y'),
            }
        )
        print(f"[SEND] Sent Wave 3 code entry email to {participant.participant_id}")
    except Participant.DoesNotExist:
        print(f"[ERROR] Participant {participant_id} not found for wave3_code_entry")
        pass
    except Exception as e:
        pass
    finally:
        # Close database connections
        connections.close_all()

@shared_task
def send_study_end_email(participant_id):
    """Information 24: Survey and Monitor Return Email (Study End)"""
    try:
        participant = Participant.objects.get(id=participant_id)
        
        # Check if already sent
        if participant.wave3_survey_monitor_return_sent:
            print(f"[SKIP] Study end email already sent for participant {participant_id}")
            return
        print(f"[SEND] Sending study end email to {participant.participant_id}")
        participant.send_email('study_end')
        participant.wave3_survey_monitor_return_sent = True
        participant.wave3_survey_monitor_return_date = timezone.now().date()
        participant.save()
        
        print(f"[SEND] Sent study end email to {participant.participant_id}")
    except Exception as e:
        print(f"[ERROR] Error sending study end email: {str(e)}")
        pass

@shared_task
def send_wave3_missing_code_email(participant_id):
    """Information 27: Missing Code Entry Email (Study End)"""
    try:
        participant = Participant.objects.get(id=participant_id)
        
        # Check if already sent
        if participant.wave3_missing_code_sent:
            print(f"[SKIP] Wave 3 missing code email already sent for participant {participant_id}")
            return
            
        participant.send_email('wave3_missing_code')
        participant.wave3_missing_code_sent = True
        participant.save()
        
        print(f"[SEND] Sent Wave 3 missing code email to {participant.participant_id}")
    except Exception as e:
        print(f"[ERROR] Error sending Wave 3 missing code email: {str(e)}")
        pass

@shared_task
def run_randomization():
    call_command('randomize_participants')
