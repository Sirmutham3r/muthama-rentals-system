from app import app
from models import db, Tenant, Unit, Lease, Transaction, Repair
from datetime import date, datetime, timedelta

with app.app_context():
    # 1. Wipe the database clean and recreate the tables with the new schema
    db.drop_all()
    db.create_all()
    print("Database wiped and tables created.")

    # 2. Create Units
    u1 = Unit(unit_type='Single Room', door_number='SR - 01', standard_rate=3000.0, status='Occupied')
    u2 = Unit(unit_type='Bedsitter', door_number='BS - 01', standard_rate=5500.0, status='Occupied')
    u3 = Unit(unit_type='One Bedroom', door_number='1BR - 01', standard_rate=8500.0, status='Occupied')
    u4 = Unit(unit_type='Bedsitter', door_number='BS - 02', standard_rate=5500.0, status='Vacant') # Cleared tenant's old room
    u5 = Unit(unit_type='Single Room', door_number='SR - 02', standard_rate=3000.0, status='Vacant')
    db.session.add_all([u1, u2, u3, u4, u5])
    db.session.flush()

    # 3. Create Tenants
    t1 = Tenant(full_names='Brian Mutuku', national_id='11223344', institution_work='Kenyatta University', phone_number='254711111111', emergency_contact_name='Mary Mutuku', emergency_contact='254700000001')
    t2 = Tenant(full_names='Joy Wanjiku', national_id='22334455', institution_work='Nairobi Hospital', phone_number='254722222222', emergency_contact_name='Peter Wanjiku', emergency_contact='254700000002')
    t3 = Tenant(full_names='Kelvin Ochieng', national_id='33445566', institution_work='Safaricom', phone_number='254733333333', emergency_contact_name='Sarah Ochieng', emergency_contact='254700000003')
    t4 = Tenant(full_names='Grace Njoroge', national_id='44556677', institution_work='Strathmore', phone_number='254744444444', emergency_contact_name='John Njoroge', emergency_contact='254700000004')
    db.session.add_all([t1, t2, t3, t4])
    db.session.flush()

    today = date.today()
    next_month = today.month + 1 if today.month < 12 else 1
    next_year = today.year if today.month < 12 else today.year + 1
    standard_due_date = date(next_year, next_month, 8)
    overdue_date = date(today.year, today.month, 8) - timedelta(days=20) # Simulate a missed payment date

    # 4. Create Leases (Showcasing all system features)
    
    # Lease 1: Perfect Tenant (SR-01) - Balance 0
    l1 = Lease(tenant_id=t1.id, unit_id=u1.id, agreed_rate=u1.standard_rate, due_date=standard_due_date, start_date=date(2026, 1, 1), current_balance=0.0, deposit_paid=3000.0, notice_status='Active')
    
    # Lease 2: Holiday Mode & Arrears (BS-01) - 50% Rent, missed payment
    l2 = Lease(tenant_id=t2.id, unit_id=u2.id, agreed_rate=u2.standard_rate / 2, due_date=overdue_date, start_date=date(2026, 5, 1), current_balance=-2750.0, deposit_paid=5500.0, notice_status='Active')
    
    # Lease 3: Notice Given (1BR-01) - Overpaid
    l3 = Lease(tenant_id=t3.id, unit_id=u3.id, agreed_rate=u3.standard_rate, due_date=standard_due_date, start_date=date(2025, 11, 1), current_balance=1500.0, deposit_paid=8500.0, notice_status='Notice Given')
    
    # Lease 4: Cleared / Checked out (BS-02) - Deductions made for damages!
    l4 = Lease(tenant_id=t4.id, unit_id=u4.id, agreed_rate=u4.standard_rate, due_date=date(2026, 8, 8), start_date=date(2026, 2, 1), end_date=date(2026, 9, 1), current_balance=0.0, deposit_paid=5500.0, deposit_returned=4000.0, deduction_reason="Broken window pane and stained walls", notice_status='Cleared')

    db.session.add_all([l1, l2, l3, l4])
    db.session.flush()

    # 5. Create Transactions
    tx1 = Transaction(lease_id=l1.id, amount_paid=3000.0, mpesa_receipt='MOVE-IN-L1', payment_date=datetime.now() - timedelta(days=30))
    tx2 = Transaction(lease_id=l3.id, amount_paid=10000.0, mpesa_receipt='RDJ9876543', payment_date=datetime.now() - timedelta(days=2))
    db.session.add_all([tx1, tx2])

    # 6. Create Repairs (Including the deduction repair for the cleared tenant)
    r1 = Repair(unit_id=u1.id, description="Replaced leaking sink pipe", cost=800.0, date_filed=datetime.now() - timedelta(days=10))
    r2 = Repair(unit_id=u4.id, description=f"Checkout deduction: {l4.deduction_reason} ({t4.full_names})", cost=1500.0, date_filed=datetime.now() - timedelta(days=2))
    db.session.add_all([r1, r2])

    db.session.commit()
    print("Successfully seeded Muthama Rentals database with updated schema!")