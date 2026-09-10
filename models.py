from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class Tenant(db.Model):
    __tablename__ = 'tenants'
    id = db.Column(db.Integer, primary_key=True)
    full_names = db.Column(db.String(100), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    institution_work = db.Column(db.String(100))
    phone_number = db.Column(db.String(15), nullable=False)
    emergency_contact_name = db.Column(db.String(100), nullable=False)
    emergency_contact = db.Column(db.String(15), nullable=False)
    leases = db.relationship('Lease', backref='tenant', lazy=True)

class Unit(db.Model):
    __tablename__ = 'units'
    id = db.Column(db.Integer, primary_key=True)
    unit_type = db.Column(db.String(50), nullable=False) 
    door_number = db.Column(db.String(20), nullable=False, unique=True)
    standard_rate = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Vacant')
    leases = db.relationship('Lease', backref='unit', lazy=True)
    repairs = db.relationship('Repair', backref='unit', lazy=True)

class Lease(db.Model):
    __tablename__ = 'leases'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    
    agreed_rate = db.Column(db.Float, nullable=False) 
    due_date = db.Column(db.Date, nullable=False) 
    
    start_date = db.Column(db.Date, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    
    current_balance = db.Column(db.Float, default=0.0)
    deposit_paid = db.Column(db.Float, default=0.0) 
    
    deposit_returned = db.Column(db.Float, nullable=True) 
    deduction_reason = db.Column(db.String(255), nullable=True)
    
    notice_status = db.Column(db.String(20), default='Active') 
    transactions = db.relationship('Transaction', backref='lease', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    lease_id = db.Column(db.Integer, db.ForeignKey('leases.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    mpesa_receipt = db.Column(db.String(50), unique=True, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

class Repair(db.Model):
    __tablename__ = 'repairs'
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    date_filed = db.Column(db.DateTime, default=datetime.utcnow)