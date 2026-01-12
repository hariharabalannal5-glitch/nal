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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===================== APP CONFIG =====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'csir-4pi-super-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///csir4pi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ===================== EMAIL CONFIG =====================
GMAIL_USER = 'hariharabalan787@gmail.com'
GMAIL_PASSWORD = 'ccft pfqt itmq wref'

# ===================== EXTENSIONS =====================
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ===================== MODELS =====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6))
    otp_expires = db.Column(db.DateTime)

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

# ===================== FORMS =====================
class SignupForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=10, max=15)])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class OTPForm(FlaskForm):
    otp = StringField('OTP', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify')

# ===================== LOGIN =====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ===================== EMAIL =====================
def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = 'CSIR-4PI OTP Verification'
        msg.attach(MIMEText(f"Your OTP is {otp} (Valid 10 mins)", 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email failed:", e)
        print("OTP:", otp)
        return False

# ===================== ROUTES =====================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = SignupForm()
    if form.validate_on_submit():
        if User.query.filter(
            (User.username == form.username.data) |
            (User.email == form.email.data)
        ).first():
            flash('Username or email already exists', 'danger')
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

        send_otp_email(user.email, otp)
        session['pending_user_id'] = user.id
        flash('OTP sent to your email', 'success')
        return redirect(url_for('verify_otp'))

    return render_template('signup.html', form=form)

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('signup'))

    user = User.query.get_or_404(user_id)
    form = OTPForm()

    if form.validate_on_submit():
        if user.otp == form.otp.data and user.otp_expires > datetime.utcnow():
            user.email_verified = True
            user.otp = None
            user.otp_expires = None
            db.session.commit()
            login_user(user)
            session.pop('pending_user_id')
            return redirect(url_for('dashboard'))
        flash('Invalid OTP', 'danger')

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
        flash('Invalid login or email not verified', 'danger')

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

# ===================== BOOKINGS API =====================
@app.route('/api/bookings', methods=['GET'])
@login_required
def get_bookings():
    bookings = {}
    for b in Booking.query.all():
        cell_id = f"{b.room}_{b.date_str}_{b.time_slot}"
        user = User.query.get(b.user_id)
        bookings[cell_id] = {'name': user.name}
    return jsonify(bookings)

@app.route('/api/bookings', methods=['POST'])
@login_required
def save_booking():
    data = request.get_json()
    room, date_str, time_slot = data['cellId'].split('_')
    room, time_slot = int(room), int(time_slot)

    if Booking.query.filter_by(room=room, date_str=date_str, time_slot=time_slot).first():
        return jsonify({'success': False, 'message': 'Already booked'})

    booking = Booking(
        user_id=current_user.id,
        room=room,
        date_str=date_str,
        time_slot=time_slot
    )
    db.session.add(booking)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/bookings', methods=['DELETE'])
@login_required
def delete_booking():
    data = request.get_json()
    room, date_str, time_slot = data['cellId'].split('_')
    booking = Booking.query.filter_by(
        room=int(room),
        date_str=date_str,
        time_slot=int(time_slot)
    ).first()

    if booking and booking.user_id == current_user.id:
        db.session.delete(booking)
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'success': False})

# ===================== ADMIN =====================
@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.username != 'admin':
        return redirect(url_for('dashboard'))

    users = User.query.all()
    users_data = []

    for u in users:
        users_data.append({
            'id': u.id,
            'username': u.username,
            'name': u.name,
            'email': u.email,
            'phone': u.phone,  # ✅ FIXED
            'email_verified': u.email_verified,
            'booking_count': Booking.query.filter_by(user_id=u.id).count()
        })

    return render_template('admin_users.html', users=users_data)


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.username != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)

    if user.username == 'admin':
        flash('Admin user cannot be deleted', 'danger')
        return redirect(url_for('admin_users'))

    # Delete user's bookings first
    Booking.query.filter_by(user_id=user.id).delete()

    db.session.delete(user)
    db.session.commit()

    flash(f'User "{user.username}" deleted successfully', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/setup')
def admin_setup():
    if User.query.filter_by(username='admin').first():
        return "Admin already exists"

    admin = User(
        username='admin',
        name='CSIR-4PI Admin',
        email='admin@csir4pi.com',
        phone='9999999999',
        email_verified=True
    )
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()
    return "Admin created: admin / admin123"

# ===================== RUN =====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
