"""
URL configuration for testPAS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os, sys
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from testpas import views, settings
from testpas.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    # Landing page and authentication
    path('', views.landing, name='landing'),
    path('account/confirmation-pending/', views.account_confirmation_pending, name='account_confirmation_pending'),
    path('home/', views.home, name='home'),
    path('test-challenges/', views.test_all_challenges, name='test_all_challenges'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Information 2: Create Account
    path('create-account/', views.create_account, name='create_account'),
    path('create-participant/', views.create_account, name='create_participant'),  # Alias for compatibility
    
    # Information 3: Email Confirmation
    path('confirm/<str:token>/', views.confirm_account, name='confirm_account'),
    path('confirm-account/<str:token>/', views.confirm_account, name='confirm_account_alt'),  # Alias
    
    # Questionnaire flow
    path('questionnaire/', views.questionnaire, name='questionnaire'),
    
    # Information 4: Interest Screening
    path('questionnaire/interest/', views.questionnaire_interest, name='questionnaire_interest'),  # type: ignore
    
    # Information 6: Consent Form
    path('questionnaire/consent/', views.consent_form, name='consent_form'),
    path('questionnaire/consent/<int:survey_id>/', views.consent_form, name='consent_form_with_survey'),
    # path('consent/download/', views.download_consent, name='download_consent'),
    
    # Information 7: Exit Screens
    path('exit/not-interested/', views.exit_screen_not_interested, name='exit_screen_not_interested'),
    path('exit/not-eligible/', views.exit_screen_not_eligible, name='exit_screen_not_eligible'),

    
    # Information 8: Waiting Screen
    path('waiting_screen/', views.waiting_screen, name='waiting_screen'),
    
    # Information 11 & 22: Code Entry
    path('enter-code/<int:wave>/', views.enter_code, name='enter_code'),
    path('enter-wave3-code/', views.enter_code, {'wave': 3}, name='enter_wave3_code'),
    path('code-success/<int:wave>/', views.code_success, name='code_success'),
    path('code-failure/', views.code_failure, name='code_failure'),
    path('password-reset/', views.password_reset, name='password_reset'),
    path('password-reset-confirm/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('intervention/', views.intervention_access, name='intervention_access'),
    path('intervention/test/', views.intervention_access_test, name='intervention_access_test'),
    path('intervention/preview/', views.intervention_preview, name='intervention_preview'),
    path('intervention/challenge-25/', views.intervention_challenge_25, name='intervention_challenge_25'),
    path('intervention/challenge-2/', views.intervention_challenge_2, name='intervention_challenge_2'),
    path('intervention/challenge-3/', views.intervention_challenge_3, name='intervention_challenge_3'),
    path('intervention/challenge-4/', views.intervention_challenge_4, name='intervention_challenge_4'),
    path('intervention/challenge-5/', views.intervention_challenge_5, name='intervention_challenge_5'),
    path('intervention/challenge-6/', views.intervention_challenge_6, name='intervention_challenge_6'),
    path('intervention/challenge-7/', views.intervention_challenge_7, name='intervention_challenge_7'),
    path('intervention/challenge-1/export/', views.export_challenge_1_csv, name='export_challenge_1_csv'),
    path('intervention/challenge-5/export/', views.export_challenge_5_csv, name='export_challenge_5_csv'),
    path('intervention/ge/challenge-1/', views.ge_challenge_1, name='ge_challenge_1'),
    path('intervention/ge/challenge-2/', views.ge_challenge_2, name='ge_challenge_2'),
    path('intervention/ge/challenge-3/', views.ge_challenge_3, name='ge_challenge_3'),
    path('intervention/ge/challenge-4/', views.ge_challenge_4, name='ge_challenge_4'),
    path('intervention/orientation/challenge-1/', views.ge_challenge_1, name='orientation_challenge_1'),
    path('intervention/orientation/challenge-2/', views.ge_challenge_2, name='orientation_challenge_2'),
    path('intervention/orientation/challenge-3/', views.ge_challenge_3, name='orientation_challenge_3'),
    path('intervention/orientation/challenge-4/', views.ge_challenge_4, name='orientation_challenge_4'),
    path('intervention/wr/challenge-6/', views.wr_challenge_6, name='wr_challenge_6'),
    path('intervention/wr/challenge-7/', views.wr_challenge_7, name='wr_challenge_7'),
    path('intervention/wr/challenge-8/', views.wr_challenge_8, name='wr_challenge_8'),
    path('intervention/wr/challenge-9/', views.wr_challenge_9, name='wr_challenge_9'),
    path('intervention/wr/challenge-10/', views.wr_challenge_10, name='wr_challenge_10'),
    path('intervention/tr/challenge-11/', views.tr_challenge_11, name='tr_challenge_11'),
    path('intervention/tr/challenge-12/', views.tr_challenge_12, name='tr_challenge_12'),
    path('intervention/tr/challenge-13/', views.tr_challenge_13, name='tr_challenge_13'),
    path('intervention/tr/challenge-14/', views.tr_challenge_14, name='tr_challenge_14'),
    path('intervention/tr/challenge-15/', views.tr_challenge_15, name='tr_challenge_15'),
    # Domestic-Related Physical Activity Challenges

    path('intervention/dom/challenge-16/', views.dom_challenge_16, name='dom_challenge_16'),
    path('intervention/dom/challenge-17/', views.dom_challenge_17, name='dom_challenge_17'),
    path('intervention/dom/challenge-18/', views.dom_challenge_18, name='dom_challenge_18'),
    path('intervention/dom/challenge-19/', views.dom_challenge_19, name='dom_challenge_19'),
    path('intervention/dom/challenge-20/', views.dom_challenge_20, name='dom_challenge_20'),
    # Leisure-Related Physical Activity Challenges
    path('intervention/leisure/challenge-21/', views.leisure_challenge_21, name='leisure_challenge_21'),
    path('intervention/leisure/challenge-22/', views.leisure_challenge_22, name='leisure_challenge_22'),
    path('intervention/leisure/challenge-23/', views.leisure_challenge_23, name='leisure_challenge_23'),
    path('intervention/leisure/challenge-24/', views.leisure_challenge_24, name='leisure_challenge_24'),
    path('intervention/leisure/challenge-25/', views.leisure_challenge_25, name='leisure_challenge_25'),
    path('intervention/leisure/challenge-26/', views.leisure_challenge_26, name='leisure_challenge_26'),
    path('intervention/leisure/challenge-27/', views.leisure_challenge_27, name='leisure_challenge_27'),
    # Mindfulness Challenges
    path('intervention/mindfulness/challenge-28/', views.mindfulness_challenge_28, name='mindfulness_challenge_28'),
    path('intervention/mindfulness/challenge-29/', views.mindfulness_challenge_29, name='mindfulness_challenge_29'),
    path('intervention/mindfulness/challenge-30/', views.mindfulness_challenge_30, name='mindfulness_challenge_30'),
    path('intervention/mindfulness/challenge-31/', views.mindfulness_challenge_31, name='mindfulness_challenge_31'),
    path('intervention/mindfulness/challenge-32/', views.mindfulness_challenge_32, name='mindfulness_challenge_32'),
    path('intervention/challenge-1/', views.intervention_challenge_1, name='intervention_challenge_1'),
    path('intervention/update-points/', views.update_intervention_points, name='update_intervention_points'),
    path('intervention/record-commitment/', views.record_commitment_click, name='record_commitment_click'),
    # path('dev/time-controls/', views.dev_time_controls, name='dev_time_controls'),
    
    # Surveys (Information 9, 18, 20)
    path('survey/wave<int:wave>/', views.survey_view, name='survey'),
    
    # Daily Activity Logs (Information 13, 24)
    path('survey/daily-log/wave<int:wave>/', views.daily_log_view, name='daily_log'),
]
