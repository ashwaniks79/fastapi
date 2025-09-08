import odoorpc
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def get_env_var(key: str) -> str:
    """Fetch env variable or raise clear error if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value

def get_odoo_connection():
    host = get_env_var("ODOO_HOST")
    port = int(get_env_var("ODOO_PORT"))
    db = get_env_var("ODOO_DB")
    login = get_env_var("ODOO_USER")
    password = get_env_var("ODOO_PASSWORD")

    try:
        odoo = odoorpc.ODOO(host=host, port=port)
        odoo.login(db=db, login=login, password=password)
        print(f"✅ Connected to Odoo DB '{db}' as {login}")
        return odoo
    except Exception as e:
        raise ConnectionError(f" Failed to connect to Odoo: {e}")

# import odoorpc
# import os

# def get_odoo_connection():
#     odoo = odoorpc.ODOO(
#         host=os.getenv("ODOO_HOST", "170.64.163.105"),       
#         port=int(os.getenv("ODOO_PORT", 8069))
#     )
#     odoo.login(
#         db=os.getenv("ODOO_DB", "odoo"),                       
#         login=os.getenv("ODOO_USER", "test@baselineitdevelopment.com"), 
#         password=os.getenv("ODOO_PASSWORD", "Base#")          
#     )
#     return odoo
# import odoorpc
# import os
# from dotenv import load_dotenv

# load_dotenv()

# def get_odoo_connection():
#     odoo = odoorpc.ODOO(
#         host=os.getenv("ODOO_HOST", "odoo"),       
#         port=int(os.getenv("ODOO_PORT", 8069))
#     )
#     odoo.login(
#         db=os.getenv("ODOO_DB", "eredoxproapi1"),                       
#         login=os.getenv("ODOO_USER", "admin"), 
#         password=os.getenv("ODOO_PASSWORD", "admin")          
#     )
#     return odoo
