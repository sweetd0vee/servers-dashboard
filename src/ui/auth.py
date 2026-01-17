import base64
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import sys
import time
from urllib.parse import urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import requests
import streamlit as st


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_logger import logger


# Configuration (should be in environment variables in production)
# ----without httpd proxy----
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8087/keycloak")
KEYCLOAK_URL_FOR_AUTH = os.getenv("KEYCLOAK_URL_FOR_AUTH", "http://localhost:8087/keycloak")
KEYCLOAK_REDIRECT_URI = os.getenv("KEYCLOAK_REDIRECT_URI", "http://localhost:8501/dashboard")
# ----with httpd proxy----
# KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost/keycloak")
# KEYCLOAK_URL_FOR_AUTH = os.getenv("KEYCLOAK_URL_FOR_AUTH", "http://localhost/keycloak")
# KEYCLOAK_REDIRECT_URI = os.getenv("KEYCLOAK_REDIRECT_URI", "http://localhost/dashboard")
#----
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "srv")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "srv-keycloak-client")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "12tbrbzRuSX48jI08yPKdxo8OcqtPhrq")

# Keycloak endpoints
KEYCLOAK_AUTH_URL = f"{KEYCLOAK_URL_FOR_AUTH}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
KEYCLOAK_TOKEN_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
KEYCLOAK_CERTS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
KEYCLOAK_USERINFO_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
KEYCLOAK_LOGOUT_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"

# Cache for public key
PUBLIC_KEY_CACHE = None
KEY_CACHE_TIMESTAMP = None
KEY_CACHE_TTL = 3600  # 1 hour


def get_public_key():
    """Fetch public key from Keycloak for token verification"""
    global PUBLIC_KEY_CACHE, KEY_CACHE_TIMESTAMP

    # Check if we have a cached key that's still valid
    if PUBLIC_KEY_CACHE and KEY_CACHE_TIMESTAMP:
        if time.time() - KEY_CACHE_TIMESTAMP < KEY_CACHE_TTL:
            return PUBLIC_KEY_CACHE

    try:
        response = requests.get(KEYCLOAK_CERTS_URL)
        response.raise_for_status()
        jwks = response.json()

        # Get the first RSA key
        rsa_key = None
        for key in jwks["keys"]:
            if key["kty"] == "RSA" and key["alg"] == "RS256":
                rsa_key = key
                break

        if not rsa_key:
            raise ValueError("No RSA key found in JWKS")

        # Construct public key from JWK
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(rsa_key))

        # Cache the key
        PUBLIC_KEY_CACHE = public_key
        KEY_CACHE_TIMESTAMP = time.time()

        return public_key

    except Exception as e:
        st.error(f"Error fetching public key: {str(e)}")
        return None


def verify_token(token: str):
    """Verify JWT token with Keycloak public key"""
    try:
        public_key = get_public_key()
        if not public_key:
            return None

        # TODO review it
        payload_unverified = jwt.decode(token, options={"verify_signature": False})
        actual_aud = payload_unverified.get('aud')
        # Decode and verify token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=actual_aud,
            #issuer=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}",
            options={"verify_exp": True}
        )

        return payload

    except jwt.ExpiredSignatureError:
        st.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        st.warning(f"Invalid token: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Token verification error: {str(e)}")
        return None


def get_auth_url():
    """Generate Keycloak authorization URL"""
    params = {
        "client_id": KEYCLOAK_CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": KEYCLOAK_REDIRECT_URI,
        "state": "streamlit_app"  # Could be more complex for CSRF protection
    }

    return f"{KEYCLOAK_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str):
    """Exchange authorization code for tokens"""
    try:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": KEYCLOAK_REDIRECT_URI,
            "client_id": KEYCLOAK_CLIENT_ID,
            "client_secret": KEYCLOAK_CLIENT_SECRET
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(KEYCLOAK_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        st.error(f"Error exchanging code for token: {str(e)}")
        return None


def refresh_token_method(refresh_token: str):
    """Refresh access token using refresh token"""
    try:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": KEYCLOAK_CLIENT_ID,
            "client_secret": KEYCLOAK_CLIENT_SECRET
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(KEYCLOAK_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        st.error(f"Error refreshing token: {str(e)}")
        return None


def get_user_info(access_token: str):
    """Get user info from Keycloak"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.get(KEYCLOAK_USERINFO_URL, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        st.error(f"Error getting user info: {str(e)}")
        return None


def logout_user():
    """Logout from Keycloak"""
    try:
        refresh_token = st.session_state.get("refresh_token", "")

        if refresh_token:
            data = {
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
                "refresh_token": refresh_token
            }

            response = requests.post(
                KEYCLOAK_LOGOUT_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            # Clear session state even if logout fails
            for key in ["access_token", "refresh_token", "user_info", "authenticated", "id_token"]:
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()

    except Exception as e:
        st.error(f"Error during logout: {str(e)}")
        # Still clear session state
        for key in ["access_token", "refresh_token", "user_info", "authenticated", "id_token"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


def login_page():
    """Keycloak login page"""
    st.title("🔐 Keycloak Authentication")

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Single Sign-On with Keycloak")

            # Get authorization URL
            auth_url = get_auth_url()

            st.markdown(f"""
            <a href="{auth_url}" target="_self">
                <button style="
                    background-color: #4CAF50;
                    color: white;
                    padding: 14px 20px;
                    margin: 8px 0;
                    border: none;
                    cursor: pointer;
                    width: 100%;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: bold;
                ">
                    Login with Keycloak
                </button>
            </a>
            """, unsafe_allow_html=True)


def check_auth():
    """Check if user is authenticated and token is valid"""
    # Check for authorization code in URL parameters
    query_params = st.query_params.to_dict()

    if "code" in query_params and "state" in query_params:
        # We have an authorization code from Keycloak
        code = query_params["code"]

        # Exchange code for tokens
        token_response = exchange_code_for_token(code)

        if token_response:
            # Verify the access token
            payload = verify_token(token_response["access_token"])

            if payload:
                # Get user info
                user_info = get_user_info(token_response["access_token"])

                if user_info:
                    # Store tokens and user info in session state
                    st.session_state["access_token"] = token_response["access_token"]
                    st.session_state["refresh_token"] = token_response.get("refresh_token", "")
                    st.session_state["id_token"] = token_response.get("id_token", "")
                    st.session_state["user_info"] = user_info
                    st.session_state["authenticated"] = True

                    # Clear the code from URL
                    st.query_params.clear()
                    st.rerun()

    # Check if we have a valid token in session
    if st.session_state.get("authenticated", False):
        access_token = st.session_state.get("access_token", "")

        if access_token:
            # Verify token
            payload = verify_token(access_token)

            if payload:
                # Check if token is about to expire (less than 5 minutes)
                exp_time = datetime.fromtimestamp(payload["exp"])
                time_remaining = exp_time - datetime.now()

                if time_remaining < timedelta(minutes=5):
                    # Try to refresh the token
                    refresh_token = st.session_state.get("refresh_token", "")
                    if refresh_token:
                        token_response = refresh_token_method(refresh_token)
                        if token_response:
                            st.session_state["access_token"] = token_response["access_token"]
                            st.session_state["refresh_token"] = token_response.get("refresh_token", "")
                            return True
                        else:
                            logout_user()
                            return False
                return True
            else:
                # Token is invalid, try to refresh
                refresh_token = st.session_state.get("refresh_token", "")
                if refresh_token:
                    token_response = refresh_token_method(refresh_token)
                    if token_response:
                        st.session_state["access_token"] = token_response["access_token"]
                        st.session_state["refresh_token"] = token_response.get("refresh_token", "")
                        return True

                # If refresh fails, logout
                logout_user()
                return False

    return False


def require_auth(func):
    """Decorator for requiring authentication"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not check_auth():
            login_page()
            st.stop()
        return func(*args, **kwargs)

    return wrapper


def require_role(required_roles: list):
    """Decorator for requiring specific roles"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not check_auth():
                login_page()
                st.stop()

            # Get user roles from token or user info
            user_roles = []

            # Check token payload
            access_token = st.session_state.get("access_token", "")
            if access_token:
                payload = verify_token(access_token)
                if payload and "realm_access" in payload:
                    user_roles = payload["realm_access"].get("roles", [])
                elif payload and "resource_access" in payload:
                    client_access = payload["resource_access"].get(KEYCLOAK_CLIENT_ID, {})
                    user_roles = client_access.get("roles", [])

            # Check user info
            user_info = st.session_state.get("user_info", {})
            if user_info and isinstance(user_info, dict):
                if "roles" in user_info:
                    user_roles.extend(user_info["roles"])

            # Check if user has any of the required roles
            has_role = any(role in user_roles for role in required_roles)

            if not has_role:
                st.error(f"Access denied. Required roles: {', '.join(required_roles)}")
                st.info(f"Your roles: {', '.join(user_roles) if user_roles else 'None'}")
                st.stop()

            return func(*args, **kwargs)

        return wrapper

    return decorator


def has_role(required_roles: list):
    """Check if user has any of the required roles"""
    if not check_auth():
        return False

    user_roles = []
    access_token = st.session_state.get("access_token", "")

    if access_token:
        payload = verify_token(access_token)
        if payload and "realm_access" in payload:
            user_roles = payload["realm_access"].get("roles", [])

    user_info = st.session_state.get("user_info", {})
    if user_info and isinstance(user_info, dict) and "roles" in user_info:
        user_roles.extend(user_info["roles"])

    return any(role in user_roles for role in required_roles)


def get_current_user():
    """Get current user information"""
    if check_auth():
        return st.session_state.get("user_info", {})
    return None


def display_user_info():
    """Display user information in sidebar"""
    if check_auth():
        user_info = st.session_state.get("user_info", {})

        st.sidebar.markdown("### 👤 User Info")

        if user_info:
            if "name" in user_info:
                st.sidebar.text(f"Name: {user_info['name']}")
            if "preferred_username" in user_info:
                st.sidebar.text(f"Username: {user_info['preferred_username']}")
            if "email" in user_info:
                st.sidebar.text(f"Email: {user_info['email']}")

        # Logout button
        if st.sidebar.button("🚪 Logout", type="primary", use_container_width=True):
            logout_user()


# Example Streamlit app pages with Keycloak integration
@require_auth
def dashboard_page():
    """Main dashboard page (requires authentication)"""
    st.title("📊 Dashboard")

    user_info = get_current_user()
    if user_info:
        st.success(f"Welcome, {user_info.get('name', user_info.get('preferred_username', 'User'))}!")

    st.markdown("## Key Metrics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Active Users", "1,234", "12%")

    with col2:
        st.metric("Revenue", "$45,231", "8%")

    with col3:
        st.metric("Conversion Rate", "3.2%", "-0.5%")

    st.markdown("---")

    # Role-based content
    if has_role(["admin"]):
        st.markdown("### Admin Section")
        st.info("This section is only visible to administrators.")

        if st.button("Manage Users"):
            st.write("User management functionality would go here...")

    if has_role(["admin", "user"]):
        st.markdown("### User Section")
        st.info("This section is visible to users and admins.")

        if st.button("View Reports"):
            st.write("Report viewing functionality would go here...")


@require_role(["admin"])
def admin_page():
    """Admin-only page"""
    st.title("⚙️ Admin Panel")
    st.warning("This page is only accessible to administrators.")

    st.markdown("### User Management")

    # Example admin functionality
    st.dataframe({
        "Username": ["admin", "user1", "user2"],
        "Email": ["admin@example.com", "user1@example.com", "user2@example.com"],
        "Role": ["admin", "user", "viewer"],
        "Status": ["Active", "Active", "Inactive"]
    })

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Add new user")
        st.button("Add User")

    with col2:
        st.selectbox("Select user to edit", ["admin", "user1", "user2"])
        st.button("Edit User")


@require_auth
def profile_page():
    """User profile page"""
    st.title("👤 User Profile")

    user_info = get_current_user()

    if user_info:
        with st.form("profile_form"):
            st.text_input("Full Name", value=user_info.get("name", ""))
            st.text_input("Email", value=user_info.get("email", ""))
            st.text_input("Username", value=user_info.get("preferred_username", ""))

            if st.form_submit_button("Update Profile"):
                st.success("Profile updated successfully!")

    # Display token info (for debugging)
    with st.expander("Token Information (Debug)"):
        access_token = st.session_state.get("access_token", "")
        if access_token:
            try:
                payload = verify_token(access_token)
                if payload:
                    st.json(payload)
            except:
                st.write("Cannot decode token")


def main():
    """Main application"""
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # Page configuration
    st.set_page_config(
        page_title="Streamlit + Keycloak",
        page_icon="🔐",
        layout="wide"
    )

    # Display user info in sidebar if authenticated
    if check_auth():
        display_user_info()

    # Sidebar navigation
    st.sidebar.title("🔐 Keycloak Auth Demo")

    # Navigation
    if check_auth():
        pages = {
            "Dashboard": dashboard_page,
            "Profile": profile_page,
        }

        # Add admin page only for admins
        if has_role(["admin"]):
            pages["Admin Panel"] = admin_page

        selection = st.sidebar.radio("Navigation", list(pages.keys()))
        pages[selection]()
    else:
        login_page()


if __name__ == "__main__":
    # Environment variables check
    if not os.getenv("KEYCLOAK_URL"):
        st.warning("""
        **Keycloak Configuration Required:**

        Please set the following environment variables:

        ```bash
        export KEYCLOAK_URL="http://localhost:8087/keycloak"
        export KEYCLOAK_REALM=srv
        export KEYCLOAK_CLIENT_ID=srv-keycloak-client
        export KEYCLOAK_CLIENT_SECRET=clientsecret
        export KEYCLOAK_REDIRECT_URI="http://localhost:8501/dashboard"
        ```

        Using development mode for now.
        """)

    main()
