from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class UploadForm(FlaskForm):
    bill_image = FileField('Upload Bill Image', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    submit = SubmitField('Analyze Bill')

class ChatForm(FlaskForm):
    message = StringField('Ask a question...', validators=[DataRequired()])
    submit = SubmitField('Send')

class DirectFetchForm(FlaskForm):
    ref_no = StringField('14-Digit Reference No', validators=[DataRequired(), Length(min=14, max=14, message="Must be exactly 14 characters")])
    company = SelectField('Distributor', choices=[
        ('lescobill', 'LESCO (Lahore)'),
        ('mepcobill', 'MEPCO (Multan)'),
        ('fescobill', 'FESCO (Faisalabad)'),
        ('iescobill', 'IESCO (Islamabad)'),
        ('gepcobill', 'GEPCO (Gujranwala)'),
        ('pescobill', 'PESCO (Peshawar)'),
        ('hescobill', 'HESCO (Hyderabad)'),
        ('sepcobill', 'SEPCO (Sukkur)'),
        ('qescobill', 'QESCO (Quetta)'),
        ('tescobill', 'TESCO (Tribal Areas)')
    ], validators=[DataRequired()])
    submit_fetch = SubmitField('Fetch Bill Data')
