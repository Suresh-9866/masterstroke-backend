import sqlite3
import secrets
import hashlib

def hash_pw(pw: str) -> str:
    salt = secrets.token_hex(8)
    hashed = hashlib.sha256((salt + pw).encode()).hexdigest()
    return f"{salt}${hashed}"

conn = sqlite3.connect("wings.db")
c = conn.cursor()

pw_hash = hash_pw("wings123")

c.execute("SELECT id FROM subscribers WHERE phone LIKE ? OR whatsapp_number LIKE ?", ("%9876543210%", "%9876543210%"))
row = c.fetchone()
if not row:
    c.execute("""
        INSERT INTO subscribers (
            business_name, business_category, owner_name, phone, whatsapp_number,
            password_hash, is_password_set, total_business_taken, total_business_given,
            business_count, leads, total_rewards_gained, is_deleted
        ) VALUES (
            'Wings Tech Solutions', 'IT & Digital Services', 'Suresh Kumar', '9876543210', '9876543210',
            ?, 1, 50000.0, 25000.0, 12, 8, 1500, 0
        )
    """, (pw_hash,))
    print("Seeded demo subscriber: 9876543210 / wings123")
else:
    c.execute("UPDATE subscribers SET password_hash = ?, is_password_set = 1 WHERE id = ?", (pw_hash, row[0]))
    print("Updated existing subscriber password to wings123")

c.execute("SELECT id FROM beneficiaries WHERE whatsapp_number LIKE ? OR referrer_phone LIKE ?", ("%9876543211%", "%9876543211%"))
row = c.fetchone()
if not row:
    c.execute("""
        INSERT INTO beneficiaries (
            beneficiary_name, whatsapp_number, referrer_phone, status,
            occupation, qualification, password_hash, is_password_set,
            total_business_given, total_rewards_gained, jobs_taken, is_deleted
        ) VALUES (
            'Ramesh Patel', '9876543211', '9876543211', 'Active',
            'Business Associate', 'B.Tech', ?, 1,
            15000.0, 800, 3, 0
        )
    """, (pw_hash,))
    print("Seeded demo beneficiary: 9876543211 / wings123")
else:
    c.execute("UPDATE beneficiaries SET password_hash = ?, is_password_set = 1 WHERE id = ?", (pw_hash, row[0]))
    print("Updated existing beneficiary password to wings123")

conn.commit()
conn.close()
print("Database seed complete.")
