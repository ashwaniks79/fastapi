import odoorpc, os
from dotenv import load_dotenv

load_dotenv()

print("Connecting...")
odoo = odoorpc.ODOO(os.getenv("ODOO_HOST"), port=int(os.getenv("ODOO_PORT")))
odoo.login(os.getenv("ODOO_DB"), os.getenv("ODOO_USER"), os.getenv("ODOO_PASSWORD"))

print("✅ Connected to Odoo")
print("UID:", odoo.env.uid)
print("User:", odoo.env.user.name)
