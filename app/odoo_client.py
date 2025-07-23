# app/odoo_client.py

# import odoorpc
# import os

# def get_odoo_connection():
#     odoo = odoorpc.ODOO(
#         host=os.getenv("ODOO_HOST", "odoo-odoo-1"),
#         port=int(os.getenv("ODOO_PORT", 8069))
#     )
#     odoo.login(
#         db=os.getenv("ODOO_DB", "eredoxproapi1"),
#         login=os.getenv("ODOO_USER", "odoo"),
#         password=os.getenv("ODOO_PASSWORD", "odoo")
#     )
#     return odoo

import odoorpc
import os

def get_odoo_connection():
    odoo = odoorpc.ODOO(
        host=os.getenv("ODOO_HOST", "170.64.163.105"),       
        port=int(os.getenv("ODOO_PORT", 8069))
    )
    odoo.login(
        db=os.getenv("ODOO_DB", "odoo"),                       
        login=os.getenv("ODOO_USER", "test@baselineitdevelopment.com"), 
        password=os.getenv("ODOO_PASSWORD", "Base#")          
    )
    return odoo