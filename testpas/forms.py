from django import forms
from django.contrib.auth.models import User
from .models import Participant
from django.contrib.auth.forms import UserCreationForm

class UserRegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, required=True, label="Username")
    email = forms.EmailField(required=True, label="Email Address")
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")
    phone_number = forms.CharField(max_length=15, required=True, label="Phone Number")
    registration_code = forms.CharField(max_length=50, required=True, label="Registration Code")
    full_name = forms.CharField(max_length=255, required=True, label="Full Name")
    address_line1 = forms.CharField(max_length=255, required=True, label="Address Line 1")
    address_line2 = forms.CharField(max_length=255, required=False, label="Address Line 2 (Optional)")
    city = forms.CharField(max_length=100, required=True, label="City")
    state = forms.CharField(max_length=50, required=True, label="State")
    zip_code = forms.CharField(max_length=10, required=True, label="ZIP Code")
    # Validate unique username
    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    # Validate unique email to prevent duplicates
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        """NOTE: Uncomment the following lines if you want to check for existing emails.
        This will be used in production to prevent duplicate email registrations."""
        # # Check if email is already in use
        # if User.objects.filter(email=email).exists():
        #     raise forms.ValidationError("This email is already in use.")
        return email

    # Validate registration code
    def clean_registration_code(self):
        code = self.cleaned_data.get('registration_code', '').strip().lower()
        if code != 'wavepa':
            raise forms.ValidationError("Invalid registration code.")
        return code

    # FIX 4: Validate password confirmation
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class InterestForm(forms.Form):
    interested = forms.ChoiceField(
        choices=[('yes', 'Interested'), ('no', 'Not Interested')],
        widget=forms.RadioSelect,
        required=True,
        label="Are you interested in determining your eligibility?"
    )
    reason = forms.CharField(
        max_length=255,
        required=False,
        label="If not interested, please provide a brief reason",
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 40})
    )

    def clean(self):
        cleaned_data = super().clean()
        interested = cleaned_data.get('interested')
        reason = cleaned_data.get('reason')
        if interested == 'no' and not reason:
            raise forms.ValidationError("Please provide a reason if you are not interested.")
        return cleaned_data

class EligibilityForm(forms.ModelForm):
    age = forms.ChoiceField(
        choices=[('lt18', 'Less than 18')] + [(i, str(i)) for i in range(18, 65)] + [('gt64', 'More than 64')],
        label="What is your age?"
    )
    height_inches = forms.ChoiceField(
        choices=[('lt48', 'Less than 4 feet 0 inches')] + [(i, f"{i//12}'{i%12}\" ({i} inches)") for i in range(48, 84)] + [('gt83', 'More than 6 feet 11 inches')],
        label="Height in Inches"
    )
    weight_lbs = forms.ChoiceField(
        choices=[('lt100', 'Less than 100 lbs')] + [(i, f"{i} lbs") for i in range(100, 501)] + [('gt500', 'More than 500 lbs')],
        label="Weight in lbs"
    )
    has_device_access = forms.ChoiceField(
        choices=[('yes', 'Yes'), ('no', 'No')],
        widget=forms.RadioSelect,
        label="Will you have access to a technological device throughout this study?"
    )
    agrees_no_other_study = forms.ChoiceField(
        choices=[('yes', 'Yes, I agree not to enroll in another program'), ('no', 'No, I do not agree')],
        widget=forms.RadioSelect,
        label="Do you agree not to enroll in another research-based intervention program?"
    )
    agrees_monitoring = forms.ChoiceField(
        choices=[('yes', 'Yes'), ('no', 'No')],
        widget=forms.RadioSelect,
        label="Do you agree to comply with physical activity monitoring instructions?"
    )
    agrees_contact = forms.ChoiceField(
        choices=[('yes', 'Yes'), ('no', 'No')],
        widget=forms.RadioSelect,
        label="Do you agree to respond to study-related contacts?"
    )
    dominant_hand = forms.ChoiceField(
        choices=[('left', 'My non-dominant hand is left'), ('right', 'My non-dominant hand is right')],
        widget=forms.RadioSelect,
        label="Which is your non-dominant hand (the hand you use less often)?",
        required=False
    )

    class Meta:
        model = Participant
        fields = ['age', 'height_inches', 'weight_lbs', 'has_device_access',
                  'agrees_no_other_study', 'agrees_monitoring', 'agrees_contact', 'dominant_hand']

    def clean_age(self):
        age = self.cleaned_data['age']
        if age == 'lt18' or age == 'gt64':
            return None
        return int(age)

    def clean_height_inches(self):
        height = self.cleaned_data['height_inches']
        if height == 'lt48' or height == 'gt83':
            return None
        return int(height)

    def clean_weight_lbs(self):
        weight = self.cleaned_data['weight_lbs']
        if weight == 'lt100' or weight == 'gt500':
            return None
        return int(weight)

    def clean_has_device_access(self):
        return self.cleaned_data['has_device_access'] == 'yes'

    def clean_agrees_no_other_study(self):
        return self.cleaned_data['agrees_no_other_study'] == 'yes'

    def clean_agrees_monitoring(self):
        return self.cleaned_data['agrees_monitoring'] == 'yes'

    def clean_agrees_contact(self):
        return self.cleaned_data['agrees_contact'] == 'yes'
    
class CodeEntryForm(forms.Form):
    code = forms.CharField(label='Enter Code', max_length=100)

class UserLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class ConsentForm(forms.Form):
    consent = forms.BooleanField(label="I consent to participate in this study", required=True)
    consent_reason = forms.CharField(
        max_length=500,
        required=False,
        label="If you do not consent, please provide a brief reason",
        widget=forms.Textarea(attrs={'rows': 3, 'cols': 40})
    )

    def clean(self):
        cleaned_data = super().clean()
        consent = cleaned_data.get('consent')
        reason = cleaned_data.get('consent_reason')
        if consent is False and not reason:
            raise forms.ValidationError("Please provide a reason if you do not consent.")
        return cleaned_data

class PasswordResetForm(forms.Form):
    identifier = forms.CharField(
        label="Email Address or Participant ID", 
        required=True,
        help_text="Enter your email address or participant ID (e.g., P0001)"
    )

class PasswordResetConfirmForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label="New Password", required=True)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm New Password", required=True)
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data