import io
import os
from dotenv import load_dotenv # NEW
from mpesa import trigger_stk_push
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session, flash
from models import db, Tenant, Unit, Lease, Transaction, Repair
import pandas as pd
from datetime import datetime, date, timedelta

# Load environment variables from the .env file
load_dotenv()

app = Flask(__name__)

# Safely fetch the database URL and secret key
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

app.secret_key = os.getenv('SECRET_KEY')
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def owner_dashboard():
    leases = Lease.query.all()
    units = Unit.query.all()
    tenants = Tenant.query.all()
    transactions = Transaction.query.all()
    repairs = Repair.query.order_by(Repair.date_filed.desc()).all()
    
    # Fetch past tenants for the checkout history table
    cleared_leases = Lease.query.filter_by(notice_status='Cleared').order_by(Lease.end_date.desc()).all()

    summary = {
        'rent_collected': sum(t.amount_paid for t in transactions),
        'overpayment': sum(l.current_balance for l in leases if l.current_balance > 0 and l.notice_status != 'Cleared'),
        'arrears': sum(abs(l.current_balance) for l in leases if l.current_balance < 0 and l.notice_status != 'Cleared'),
        'deposits_held': sum(l.deposit_paid for l in leases if l.notice_status != 'Cleared'),
        'repairs_cost': sum(r.cost for r in repairs),
        'expected_monthly': sum(l.agreed_rate for l in leases if l.notice_status != 'Cleared'),
        'total_units': len(units),
        'occupied_units': sum(1 for u in units if u.status == 'Occupied')
    }
    
    today = date.today()
    next_month = today.month + 1 if today.month < 12 else 1
    next_year = today.year if today.month < 12 else today.year + 1
    default_due = date(next_year, next_month, 8)

    return render_template(
        'owner_dashboard.html', 
        leases=leases, units=units, tenants=tenants, 
        transactions=transactions, repairs=repairs, summary=summary,
        cleared_leases=cleared_leases, today=today, default_due=default_due
    )

@app.route('/add_unit', methods=['POST'])
def add_unit():
    unit_type = request.form.get('unit_type')
    door_number = request.form.get('door_number')
    standard_rate = float(request.form.get('standard_rate'))

    new_unit = Unit(unit_type=unit_type, door_number=door_number, standard_rate=standard_rate, status='Vacant')
    db.session.add(new_unit)
    db.session.commit()
    return redirect(url_for('owner_dashboard'))

@app.route('/add_tenant', methods=['POST'])
def add_tenant():
    full_names = request.form.get('full_names')
    national_id = request.form.get('national_id')
    institution_work = request.form.get('institution_work')
    phone_number = request.form.get('phone_number')
    emergency_contact_name = request.form.get('emergency_contact_name')
    emergency_contact = request.form.get('emergency_contact')
    unit_id = int(request.form.get('unit_id'))
    
    # REMOVED: Holiday mode from onboarding. Everyone starts at the standard rate.
    unit = db.session.get(Unit, unit_id)
    standard_rate = unit.standard_rate if unit else 0.0
    agreed_rate = standard_rate 
    
    deposit_paid = 0.0
    starting_balance = -agreed_rate
    due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()

    existing_tenant = Tenant.query.filter_by(national_id=national_id).first()
    if existing_tenant:
        existing_tenant.full_names = full_names
        existing_tenant.institution_work = institution_work
        existing_tenant.phone_number = phone_number
        existing_tenant.emergency_contact_name = emergency_contact_name
        existing_tenant.emergency_contact = emergency_contact
        tenant_id_to_use = existing_tenant.id
    else:
        new_tenant = Tenant(
            full_names=full_names, national_id=national_id, institution_work=institution_work,
            phone_number=phone_number, emergency_contact_name=emergency_contact_name, emergency_contact=emergency_contact
        )
        db.session.add(new_tenant)
        db.session.flush()
        tenant_id_to_use = new_tenant.id

    new_lease = Lease(
        tenant_id=tenant_id_to_use, unit_id=unit_id, agreed_rate=agreed_rate, due_date=due_date,
        start_date=date.today(), current_balance=starting_balance, deposit_paid=deposit_paid, notice_status='Active'
    )
    
    if unit: unit.status = 'Occupied'
    db.session.add(new_lease)
    db.session.commit()
    
    flash(f"Success! {full_names} has been registered to Door {unit.door_number}.", "success")
    return redirect(url_for('owner_dashboard'))

@app.route('/toggle_holiday/<int:lease_id>', methods=['POST'])
def toggle_holiday(lease_id):
    lease = db.session.get(Lease, lease_id)
    if not lease:
        return redirect(url_for('owner_dashboard'))
        
    discount = lease.unit.standard_rate / 2
    
    # SMART TOGGLE LOGIC
    if lease.agreed_rate == lease.unit.standard_rate:
        # Turn ON Holiday Mode: Cut rate in half and instantly credit their balance
        lease.agreed_rate = discount
        lease.current_balance += discount
        flash(f"Holiday Mode ACTIVATED for {lease.tenant.full_names}. KES {discount} has been credited to their current balance.", "success")
    else:
        # Turn OFF Holiday Mode: Restore full rate and instantly charge the missing half
        lease.agreed_rate = lease.unit.standard_rate
        lease.current_balance -= discount
        flash(f"Holiday Mode REMOVED for {lease.tenant.full_names}. Standard rent rate restored.", "success")
        
    db.session.commit()
    return redirect(url_for('owner_dashboard'))

@app.route('/add_repair', methods=['POST'])
def add_repair():
    unit_id = int(request.form.get('unit_id'))
    description = request.form.get('description')
    cost = float(request.form.get('cost'))

    new_repair = Repair(unit_id=unit_id, description=description, cost=cost)
    db.session.add(new_repair)
    db.session.commit()
    return redirect(url_for('owner_dashboard'))

@app.route('/file_notice/<int:lease_id>', methods=['POST'])
def file_notice(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    lease.notice_status = 'Notice Given'
    db.session.commit()
    return redirect(url_for('owner_dashboard'))

@app.route('/release_tenant/<int:lease_id>', methods=['POST'])
def release_tenant(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    condition = request.form.get('condition')
    
    deduction_str = request.form.get('deduction_amount')
    deduction_amount = float(deduction_str) if deduction_str else 0.0
    deduction_reason = request.form.get('deduction_reason', '')
    
    if condition != 'Good' and deduction_amount > 0:
        new_repair = Repair(unit_id=lease.unit_id, description=f"Checkout deduction: {deduction_reason} ({lease.tenant.full_names})", cost=deduction_amount)
        db.session.add(new_repair)
        lease.deduction_reason = deduction_reason
    else:
        lease.deduction_reason = "House left in good condition."

    unit = db.session.get(Unit, lease.unit_id)
    if unit: unit.status = 'Vacant'
        
    lease.notice_status = 'Cleared'
    lease.deposit_returned = lease.deposit_paid - deduction_amount
    lease.end_date = date.today()
    db.session.commit()
    
    return redirect(url_for('owner_dashboard'))

@app.route('/export/system_backup')
def system_backup():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        kra_query = "SELECT u.door_number AS \"Door Number\", COALESCE(SUM(t.amount_paid), 0) AS \"Gross Rent Income (KES)\", COALESCE((SELECT SUM(cost) FROM repairs r WHERE r.unit_id = u.id), 0) AS \"Deductible Repairs (KES)\", (COALESCE(SUM(t.amount_paid), 0) - COALESCE((SELECT SUM(cost) FROM repairs r WHERE r.unit_id = u.id), 0)) AS \"Net Taxable Income (KES)\" FROM units u LEFT JOIN leases l ON u.id = l.unit_id LEFT JOIN transactions t ON l.id = t.lease_id GROUP BY u.id, u.door_number"
        pd.read_sql_query(kra_query, db.engine).to_excel(writer, index=False, sheet_name='KRA Summary')
        
        tx_query = "SELECT t.payment_date AS \"Date Paid\", t.mpesa_receipt AS \"M-Pesa Code\", ten.full_names AS \"Tenant Name\", u.door_number AS \"Door Number\", t.amount_paid AS \"Amount (KES)\" FROM transactions t JOIN leases l ON t.lease_id = l.id JOIN tenants ten ON l.tenant_id = ten.id JOIN units u ON l.unit_id = u.id ORDER BY t.payment_date DESC"
        pd.read_sql_query(tx_query, db.engine).to_excel(writer, index=False, sheet_name='Transactions')

        active_query = "SELECT ten.full_names AS \"Tenant Name\", ten.national_id AS \"ID Number\", u.door_number AS \"Door Number\", l.start_date AS \"Move-in Date\", l.agreed_rate AS \"Monthly Rent\", l.deposit_paid AS \"Deposit Held\", l.current_balance AS \"Current Balance\" FROM leases l JOIN tenants ten ON l.tenant_id = ten.id JOIN units u ON l.unit_id = u.id WHERE l.notice_status != 'Cleared'"
        pd.read_sql_query(active_query, db.engine).to_excel(writer, index=False, sheet_name='Active Tenants')

        checkout_query = "SELECT ten.full_names AS \"Tenant Name\", u.door_number AS \"Door Number\", l.end_date AS \"Checkout Date\", l.deposit_returned AS \"Refunded (KES)\", l.deduction_reason AS \"Deduction Reason\" FROM leases l JOIN tenants ten ON l.tenant_id = ten.id JOIN units u ON l.unit_id = u.id WHERE l.notice_status = 'Cleared'"
        pd.read_sql_query(checkout_query, db.engine).to_excel(writer, index=False, sheet_name='Checkouts')

        repairs_query = "SELECT r.date_filed AS \"Date\", u.door_number AS \"Door Number\", r.description AS \"Description\", r.cost AS \"Cost (KES)\" FROM repairs r JOIN units u ON r.unit_id = u.id ORDER BY r.date_filed DESC"
        pd.read_sql_query(repairs_query, db.engine).to_excel(writer, index=False, sheet_name='Repairs')

    output.seek(0)
    return send_file(output, download_name=f"Muthama_Rentals_Master_Backup_{date.today()}.xlsx", as_attachment=True)

@app.route('/tenant', methods=['GET', 'POST'])
def tenant_portal():
    if request.method == 'POST':
        national_id = request.form.get('national_id')
        phone_number = request.form.get('phone_number')
        
        tenant = Tenant.query.filter_by(national_id=national_id, phone_number=phone_number).first()
        if tenant:
            session['tenant_id'] = tenant.id
            return redirect(url_for('tenant_portal'))
        else:
            return render_template('tenant_portal.html', error="Invalid National ID or Phone Number.")

    if 'tenant_id' in session:
        tenant = db.session.get(Tenant, session['tenant_id'])
        if tenant:
            lease = Lease.query.filter_by(tenant_id=tenant.id).order_by(Lease.id.desc()).first()
            transactions = []
            if lease:
                transactions = Transaction.query.filter_by(lease_id=lease.id).order_by(Transaction.payment_date.desc()).all()
            
            return render_template('tenant_portal.html', tenant=tenant, lease=lease, transactions=transactions, today=date.today())
        else:
            session.pop('tenant_id', None)
            
    return render_template('tenant_portal.html')

@app.route('/tenant/give_notice', methods=['POST'])
def tenant_give_notice():
    if 'tenant_id' not in session: return redirect(url_for('tenant_portal'))
    lease = Lease.query.filter_by(tenant_id=session['tenant_id'], notice_status='Active').first()
    if lease:
        lease.notice_status = 'Notice Given'
        db.session.commit()
    return redirect(url_for('tenant_portal'))

@app.route('/tenant/logout')
def tenant_logout():
    session.pop('tenant_id', None)
    return redirect(url_for('tenant_portal'))

# --- M-PESA PAYMENT ROUTE ---
@app.route('/tenant/pay', methods=['POST'])
def tenant_pay():
    if 'tenant_id' not in session:
        return redirect(url_for('tenant_portal'))
        
    tenant = db.session.get(Tenant, session['tenant_id'])
    lease = Lease.query.filter_by(tenant_id=tenant.id, notice_status='Active').first()
    
    if not lease:
        return redirect(url_for('tenant_portal'))
        
    try:
        payment_amount = float(request.form.get('amount'))
        if payment_amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        # Fallback calculating exact amount owed based on new logic
        deposit_owed = lease.unit.standard_rate - lease.deposit_paid
        rent_owed = abs(lease.current_balance) if lease.current_balance < 0 else 0
        payment_amount = deposit_owed + rent_owed
        if payment_amount <= 0:
            payment_amount = lease.agreed_rate

    phone_number = tenant.phone_number
    account_ref = f"Door {lease.unit.door_number}"
    
    transactions = Transaction.query.filter_by(lease_id=lease.id).order_by(Transaction.payment_date.desc()).all()
    
    # ... (keep the top half of tenant_pay the same up to trigger_stk_push) ...
    
    response = trigger_stk_push(phone_number, payment_amount, account_ref)
    
    if response.get('ResponseCode') == '0':
        flash(f"STK Push for KES {payment_amount} sent successfully to {phone_number}. Please check your phone to enter your PIN.", "success")
    else:
        error_msg = response.get('errorMessage', 'Failed to initiate M-Pesa push. Please try again.')
        flash(error_msg, "error")
        
    return redirect(url_for('tenant_portal'))

# --- PULSE CHECKER FOR AUTO-REFRESH ---
@app.route('/api/tx_count')
def tx_count():
    count = Transaction.query.count()
    return jsonify({"count": count})

# --- BULLETPROOF MPESA CALLBACK WEBHOOK WITH SMART ALLOCATION ---
@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    data = request.json
    print("=== M-PESA WEBHOOK TRIGGERED ===")
    
    try:
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        if stk_callback.get('ResultCode') == 0:
            metadata = stk_callback['CallbackMetadata']['Item']
            amount = float(next(item['Value'] for item in metadata if item['Name'] == 'Amount'))
            receipt = next(item['Value'] for item in metadata if item['Name'] == 'MpesaReceiptNumber')
            phone = str(next(item['Value'] for item in metadata if item['Name'] == 'PhoneNumber'))
            
            print(f"Extracted -> Phone: {phone}, Amount: {amount}, Receipt: {receipt}")

            with app.app_context():
                phone_suffix = phone[-9:]
                
                lease = Lease.query.join(Tenant).filter(Tenant.phone_number.like(f"%{phone_suffix}")).order_by(Lease.id.desc()).first()
                
                if lease:
                    print(f"Found Lease for Tenant: {lease.tenant.full_names} (Door {lease.unit.door_number})")
                    
                    if lease.notice_status == 'Cleared':
                        lease.notice_status = 'Active'
                        
                    existing_tx = Transaction.query.filter_by(mpesa_receipt=receipt).first()
                    if not existing_tx:
                        new_tx = Transaction(lease_id=lease.id, amount_paid=float(amount), mpesa_receipt=receipt)
                        db.session.add(new_tx)
                        
                        # SMART ALLOCATION LOGIC
                        payment_remaining = amount
                        deposit_owed = lease.unit.standard_rate - lease.deposit_paid

                        if deposit_owed > 0:
                            if payment_remaining >= deposit_owed:
                                lease.deposit_paid += deposit_owed
                                payment_remaining -= deposit_owed
                            else:
                                lease.deposit_paid += payment_remaining
                                payment_remaining = 0

                        # Apply leftover money to the rent balance
                        lease.current_balance += payment_remaining

                        db.session.commit()
                        print(f">>> SUCCESS: Saved KES {amount} with receipt {receipt} to DB! <<<")
                    else:
                        print("Notice: Transaction receipt already recorded.")
                else:
                    print(f"Error: No lease found associated with phone suffix '{phone_suffix}'.")
        else:
            print(f"Payment failed or cancelled by user. ResultCode: {stk_callback.get('ResultCode')}")
            
    except Exception as e:
        print(f"CRITICAL CALLBACK EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)