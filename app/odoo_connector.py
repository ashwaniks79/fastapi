# import odoorpc
# import os

# def get_odoo_connection():
#     odoo = odoorpc.ODOO(
#         os.getenv("ODOO_HOST"), 
#         port=int(os.getenv("ODOO_PORT"))
#     )
#     odoo.login(
#         os.getenv("ODOO_DB"),
#         os.getenv("ODOO_USER"),
#         os.getenv("ODOO_PASSWORD")
#     )
#     return odoo
import odoorpc
import os

def get_odoo_connection():
    odoo = odoorpc.ODOO(
        os.getenv("ODOO_HOST"),
        port=int(os.getenv("ODOO_PORT"))
    )
    odoo.login(
        os.getenv("ODOO_DB"),
        os.getenv("ODOO_USER"),
        os.getenv("ODOO_PASSWORD")
    )
    return odoo
