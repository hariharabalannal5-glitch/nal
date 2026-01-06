from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import smtplib
from email.mime.text import MIMEText  # ✅ FIXED: MIMEText (uppercase)
from email.mime.multipart import MIMEMultipart  # ✅ FIXED: MIMEMultipart (uppercase)
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'csir-4pi-super-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///csir4pi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# ✅ GMAIL SMTP CONFIG - UPDATE TH,ESE 2 LINES
GMAIL_USER = 'hariharabalan787@gmail.com'  # ← YOUR GMAIL
GMAIL_PASSWORD = 'ccft pfqt itmq wref'  # ← GMAIL APP PASSWORD


db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# MODELS (UNCHANGED)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6), nullable=True)
    otp_expires = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_otp(self):
        self.otp = secrets.token_hex(3).upper()
        self.otp_expires = datetime.utcnow() + timedelta(minutes=10)
        return self.otp


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room = db.Column(db.Integer, nullable=False)
    date_str = db.Column(db.String(10), nullable=False)
    time_slot = db.Column(db.Integer, nullable=False)


# FORMS (UNCHANGED)
class SignupForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=10, max=15)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class OTPForm(FlaskForm):
    otp = StringField('Enter OTP', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify OTP')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ✅ FIXED EMAIL FUNCTION
def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart()  # ✅ FIXED: MIMEMultipart
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = 'CSIR-4PI Room Booking - Your OTP Code'
        
        body = f"""
        👋 Hello! Your OTP for CSIR-4PI Room Booking is:

        🔥 OTP: {otp}
        ⏰ Valid for 10 minutes only

        If you didn't request this, please ignore.

        Regards,
        CSIR-4PI Team
        """
        
        msg.attach(MIMEText(body, 'plain'))  # ✅ FIXED: MIMEText
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ OTP SENT to {to_email}: {otp}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print(f"🔥 FALLBACK OTP for {to_email}: {otp}")
        return False


# ROUTES
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        
        if existing_user:
            flash('Username or email already exists!', 'danger')
            return render_template('signup.html', form=form)
        
        user = User(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            username=form.username.data
        )
        user.set_password(form.password.data)
        otp = user.generate_otp()
        
        db.session.add(user)
        db.session.commit()
        
        # ✅ SEND EMAIL OTP (with fallback)
        if send_otp_email(user.email, otp):
            flash('✅ OTP sent to your email! Check inbox/spam.', 'success')
        else:
            flash('⚠️ Email failed. Check terminal for OTP.', 'warning')
        
        session['pending_user_id'] = user.id
        return redirect(url_for('verify_otp'))
    
    return render_template('signup.html', form=form)


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        flash('Please sign up first!', 'danger')
        return redirect(url_for('signup'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Invalid session!', 'danger')
        return redirect(url_for('signup'))
    
    form = OTPForm()
    if form.validate_on_submit():
        if user.otp and user.otp == form.otp.data and user.otp_expires > datetime.utcnow():
            user.email_verified = True
            user.otp = None
            user.otp_expires = None
            db.session.commit()
            flash(f'Welcome {user.name}!', 'success')
            login_user(user)
            session.pop('pending_user_id', None)
            return redirect(url_for('dashboard'))
        else:
            flash('Wrong OTP! Check your email or terminal.', 'danger')
    
    return render_template('verify_otp.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.email_verified:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid login or unverified email!', 'danger')
    
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


@app.route('/api/bookings', methods=['GET'])
@login_required
def get_bookings():
    all_bookings = Booking.query.all()
    bookings = {}
    for b in all_bookings:
        user = User.query.get(b.user_id)
        cell_id = f"{b.room}_{b.date_str}_{b.time_slot}"
        bookings[cell_id] = {'name': user.name if user else 'Unknown'}
    return jsonify(bookings)


@app.route('/api/bookings', methods=['POST'])
@login_required
def save_booking():
    data = request.get_json()
    cell_id = data['cellId']
    
    parts = cell_id.split('_')
    if len(parts) != 3:
        return jsonify({'success': False, 'error': 'Invalid cellId'})
    
    room = int(parts[0])
    date_str = parts[1]
    time_slot = int(parts[2])
    
    existing = Booking.query.filter_by(room=room, date_str=date_str, time_slot=time_slot).first()
    if existing:
        return jsonify({'success': False, 'message': 'Slot already booked'})
    
    booking = Booking(
        user_id=current_user.id,
        room=room,
        date_str=date_str,
        time_slot=time_slot
    )
    db.session.add(booking)
    db.session.commit()
    
    print(f"✅ BOOKED: Room {room}, {date_str}, TimeSlot {time_slot} by {current_user.name}")
    return jsonify({'success': True})


# ⭐ NEW: DELETE BOOKING ROUTE ⭐
@app.route('/api/bookings', methods=['DELETE'])
@login_required
def delete_booking():
    data = request.get_json()
    cell_id = data['cellId']
    
    parts = cell_id.split('_')
    if len(parts) != 3:
        return jsonify({'success': False, 'error': 'Invalid cellId'})
    
    room = int(parts[0])
    date_str = parts[1]
    time_slot = int(parts[2])
    
    # Find the booking
    booking = Booking.query.filter_by(
        room=room, 
        date_str=date_str, 
        time_slot=time_slot
    ).first()
    
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'})
    
    # Only owner can delete their booking
    if booking.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not authorized'})
    
    db.session.delete(booking)
    db.session.commit()
    
    print(f"✅ DELETED: Room {room}, {date_str}, TimeSlot {time_slot} by {current_user.name}")
    return jsonify({'success': True})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
