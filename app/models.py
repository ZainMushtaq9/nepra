from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

from app import db, login

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(150), index=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    google_id: so.Mapped[Optional[str]] = so.mapped_column(sa.String(150), unique=True)
    groq_api_key: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    created_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    bills: so.WriteOnlyMapped['Bill'] = so.relationship(back_populates='author')
    complaints: so.WriteOnlyMapped['Complaint'] = so.relationship(back_populates='author')
    chats: so.WriteOnlyMapped['Chat'] = so.relationship(back_populates='author')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

class Bill(db.Model):
    __tablename__ = 'bills'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    bill_json: so.Mapped[str] = so.mapped_column(sa.Text) # Storing JSON string
    analysis_result: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    fault_type: so.Mapped[Optional[str]] = so.mapped_column(sa.String(50))
    raw_html: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    created_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    author: so.Mapped[User] = so.relationship(back_populates='bills')
    complaints: so.WriteOnlyMapped['Complaint'] = so.relationship(back_populates='bill')

class Complaint(db.Model):
    __tablename__ = 'complaints'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    bill_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(Bill.id), index=True)
    complaint_text: so.Mapped[str] = so.mapped_column(sa.Text)
    language: so.Mapped[str] = so.mapped_column(sa.String(10), default='ur') # 'ur' or 'en'
    authority_type: so.Mapped[str] = so.mapped_column(sa.String(50)) # SDO, XEN, Wafaqi Mohtasib
    created_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    
    author: so.Mapped[User] = so.relationship(back_populates='complaints')
    bill: so.Mapped[Optional[Bill]] = so.relationship(back_populates='complaints')

class Chat(db.Model):
    __tablename__ = 'chats'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    bill_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(Bill.id), index=True)
    message: so.Mapped[str] = so.mapped_column(sa.Text)
    response: so.Mapped[str] = so.mapped_column(sa.Text)
    context_snapshot: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    author: so.Mapped[User] = so.relationship(back_populates='chats')
    bill: so.Mapped[Optional[Bill]] = so.relationship()
