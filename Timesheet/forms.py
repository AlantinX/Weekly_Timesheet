from django import forms
from .models import Employee, Timesheet
from django.contrib.auth.models import User, Group


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name']


class TimesheetForm(forms.ModelForm):
    class Meta:
        model = Timesheet
        fields = ['week_start', 'additional_notes']
        widgets = {
            'additional_notes': forms.Textarea(attrs={'rows':4, 'class':'form-control'})
        }


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user and not current_user.groups.filter(name='Admin').exists():
            # Non-admin users can't assign Admin group
            self.fields['groups'].queryset = Group.objects.exclude(name='Admin')


class UserGroupForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)

    class Meta:
        model = User
        fields = ['groups']

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user and not current_user.groups.filter(name='Admin').exists():
            # Non-admin users can't assign Admin group
            self.fields['groups'].queryset = Group.objects.exclude(name='Admin')


class PasswordResetForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True)

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError("The passwords do not match")
        return cleaned_data
