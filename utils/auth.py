# auth.py
import streamlit as st
import requests
from streamlit_cookies_manager import EncryptedCookieManager

API_KEY = st.secrets['FIREBASE_API_KEY']
FIREBASE_SIGNIN = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# Setup cookie manager
cookies = EncryptedCookieManager(prefix="auth_", password="YOUR_SECRET_KEY")
if not cookies.ready():
    st.stop()

def login_form():
    with st.form("Login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In")

        if submitted:
            result = login_user(email, password)
            if "idToken" in result:
                st.session_state["idToken"] = result["idToken"]
                st.session_state["email"] = result["email"]
                cookies["idToken"] = result["idToken"]
                cookies["email"] = result["email"]
                cookies.save()
                st.success("Logged in!")
                st.rerun()
            else:
                st.error(result.get("error", {}).get("message", "Login failed"))

def login_user(email, password):
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    response = requests.post(FIREBASE_SIGNIN, json=payload)
    return response.json()

def require_login():
    # Rehydrate session from cookies if needed
    if "idToken" not in st.session_state and cookies.get("idToken"):
        st.session_state["idToken"] = cookies.get("idToken")
        st.session_state["email"] = cookies.get("email")

    if "idToken" not in st.session_state:
        st.warning("Please log in to continue.")
        login_form()
        st.stop()  # Prevent rest of the page from loading

def logout():
    for key in ["idToken", "email"]:
        st.session_state.pop(key, None)
        cookies[key] = ""
    cookies.save()
    st.rerun()