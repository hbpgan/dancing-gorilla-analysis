from django import forms

class UrlForm(forms.Form):
    url = forms.URLField(label='URL', max_length=200)