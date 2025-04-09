import requests
import json

class APIClient:
    """
    A client class to interface with the backend's API.
    Handles requests for user auth, notifications, students/grades, reclamations, etc.
    """

    def __init__(self, base_url="put your base url here !", default_timeout=15):
        self.base_url = base_url
        self.default_timeout = default_timeout

    # -------------------------
    # AUTH / USERS
    # -------------------------
    def register(self, email, password, national_id, role):
        url = f"{self.base_url}/api/auth/register"
        payload = {
            "email": email,
            "password": password,
            "national_id": national_id,
            "role": role
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Register request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def verify_user(self, email, token):
        url = f"{self.base_url}/api/auth/verify"
        payload = {"email": email, "token": token}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Verify request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def login(self, email, password):
        url = f"{self.base_url}/api/auth/login"
        payload = {"email": email, "password": password}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Login request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def refresh_auth_token(self, user_id, refresh_token):
        url = f"{self.base_url}/api/auth/refresh"
        payload = {"user_id": user_id, "refresh_token": refresh_token}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Refresh token request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def resend_verification_code(self, email):
        url = f"{self.base_url}/api/auth/resend_verification"
        payload = {"email": email}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Resend verification code timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def start_password_reset(self, email):
        url = f"{self.base_url}/api/auth/start_reset"
        payload = {"email": email}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Start password reset timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def reset_password(self, token, new_password):
        url = f"{self.base_url}/api/auth/reset"
        payload = {"token": token, "new_password": new_password}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Reset password request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def unsubscribe_user(self, token):
        url = f"{self.base_url}/api/auth/unsubscribe"
        payload = {"token": token}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Unsubscribe request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # "Remember me" token flow
    # -------------------------
    def login_with_token(self, token):
        url = f"{self.base_url}/api/auth/login_token"
        payload = {"token": token}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Login with token timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_auth_token_in_db(self, user_id, hashed_token):
        url = f"{self.base_url}/api/auth/update_auth_token"
        payload = {"user_id": user_id, "auth_token": hashed_token}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Timed out updating auth token in DB."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def clear_auth_token(self, user_id):
        url = f"{self.base_url}/api/auth/clear_token"
        payload = {"user": {"id": user_id}}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Clear token request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # ADMIN/FRIEND NOTIFICATIONS
    # -------------------------
    def send_notification_to_all(self, title, body, bearer_token):
        url = f"{self.base_url}/api/notifications/send_all"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        payload = {"title": title, "body": body}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Send notification to all timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def send_notification_to_user(self, user_id, title, body, bearer_token):
        url = f"{self.base_url}/api/notifications/send_user"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        payload = {"user_id": user_id, "title": title, "body": body}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Send notification to user timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def send_notification_to_section(self, section, title, body, bearer_token):
        url = f"{self.base_url}/api/notifications/send_section"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        payload = {"section": section, "title": title, "body": body}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Send notification to section timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # USER NOTIFICATIONS
    # -------------------------
    def mark_notification_as_read(self, notification_id, user_id):
        url = f"{self.base_url}/api/notifications/mark_read"
        payload = {"notification_id": notification_id, "user_id": user_id}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Mark notification as read timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def mark_notification_as_seen(self, notification_id, user_id):
        url = f"{self.base_url}/api/notifications/mark_seen"
        payload = {"notification_id": notification_id, "user_id": user_id}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Mark notification as seen timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -----------------------------------------------------
    # STUDENT / MATIERE / GRADES (GET calls with Bearer)
    # -----------------------------------------------------
    def get_students(self, section=None, bearer_token=None):
        if section:
            url = f"{self.base_url}/api/students?section={section}"
        else:
            url = f"{self.base_url}/api/students"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get students timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_matieres(self, section="All", bearer_token=None):
        url = f"{self.base_url}/api/matieres?section={section}"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get matieres timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_grades(self, student_id, bearer_token=None):
        url = f"{self.base_url}/api/grades?student_id={student_id}"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get grades timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def post_grades(self, student_id, matiere_id, semester, ds, tp, exam, final, bearer_token):
        url = f"{self.base_url}/api/grades"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        payload = {
            "student_id": student_id,
            "matiere_id": matiere_id,
            "semester": semester,
            "ds": ds,
            "tp": tp,
            "exam": exam,
            "final": final
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Post grades timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # USER / PROFILE (GET with Bearer)
    # -------------------------
    def get_user(self, user_id, bearer_token=None):
        url = f"{self.base_url}/api/user?user_id={user_id}"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get user timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_time_spent(self, user_id, time_spent, bearer_token=None):
        url = f"{self.base_url}/api/user/update_time"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        payload = {"user_id": user_id, "time_spent": time_spent}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Update time spent timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}


    def update_profile_pic(self, user_id, profile_pic_url, bearer_token=None):
        url = f"{self.base_url}/api/user/update_profile_pic"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        payload = {"user_id": user_id, "profile_pic_url": profile_pic_url}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Update profile pic timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}


    # -------------------------
    # ADS
    # -------------------------
    def log_ad_click(self, ad_id, user_id):
        url = f"{self.base_url}/api/ad-click"
        payload = {"ad_id": ad_id, "user_id": user_id}
        try:
            resp = requests.post(url, json=payload, timeout=self.default_timeout)
            data = resp.json()
            return (data.get("success", False), data.get("message", ""))
        except requests.exceptions.ReadTimeout:
            return (False, "Log ad click timed out.")
        except Exception as e:
            return (False, str(e))

    def get_targeted_ad(self, user_rank_percent):
        url = f"{self.base_url}/api/targeted-ad?userRankPercent={user_rank_percent}"
        try:
            resp = requests.get(url, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get targeted ad timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # STUDENT AI REPORT (GET with Bearer)
    # -------------------------
    def get_student_ai_report(self, student_id, bearer_token=None):
        url = f"{self.base_url}/api/student/ai_report?student_id={student_id}"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get AI report timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # RECLAMATIONS (GET with Bearer)
    # -------------------------
    def submit_reclamation(self, user_id, reclamation_type, description, bearer_token=None):
        url = f"{self.base_url}/api/reclamations"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        payload = {
            "user_id": user_id,
            "reclamation_type": reclamation_type,
            "description": description
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Submit reclamation timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}


    def get_reclamations(self, user_id, bearer_token=None):
        url = f"{self.base_url}/api/reclamations?user_id={user_id}"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get reclamations timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # -------------------------
    # NOTIFICATIONS (GET with Bearer)
    # -------------------------
    def get_notifications(self, user_id, bearer_token=None):
        url = f"{self.base_url}/api/notifications?user_id={user_id}"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get notifications timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_notifications(self, user_id, subscribed, bearer_token=None):
        url = f"{self.base_url}/api/user/update_notifications"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        payload = {"user_id": user_id, "subscribed": subscribed}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Update notifications timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}


    def update_password(self, user_id, current_password, new_password, bearer_token=None):
        url = f"{self.base_url}/api/user/change_password"
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        payload = {
            "user_id": user_id,
            "current_password": current_password,
            "new_password": new_password
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Update password timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}



    # -------------------------
    # MATIERE, RECLAMATIONS, AI REPORT
    # -------------------------
    def add_matiere(self, matiere_data, bearer_token):
        url = f"{self.base_url}/api/matieres"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            resp = requests.post(url, json=matiere_data, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Add matiere request timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_all_reclamations(self, bearer_token):
        url = f"{self.base_url}/api/reclamations/all"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get all reclamations timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_reclamation_status(self, rec_id, is_solved, bearer_token):
        url = f"{self.base_url}/api/reclamations/update"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        payload = {"id": rec_id, "is_solved": is_solved}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Update reclamation status timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_all_users(self, bearer_token):
        url = f"{self.base_url}/api/users"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Get all users timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def cleanup_old_reclamations(self, bearer_token):
        url = f"{self.base_url}/api/reclamations/cleanup"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            resp = requests.post(url, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Cleanup reclamations timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_ai_report(self, student_id, ai_report, bearer_token):
        url = f"{self.base_url}/api/student/ai_report/update"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        payload = {"student_id": student_id, "ai_report": ai_report}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Update AI report timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_app_min_version(self, app_name):
        url = f"{self.base_url}/api/app_version?app_name={app_name}"
        try:
            resp = requests.get(url, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Request timed out while checking min version."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def upload_admin_log_file(self, file_path, bearer_token):
        url = f"{self.base_url}/api/upload-admin-log-file"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                resp = requests.post(url, files=files, headers=headers, timeout=self.default_timeout)
            return resp.json()
        except requests.exceptions.ReadTimeout:
            return {"success": False, "message": "Upload admin log file request timed out."}
        except FileNotFoundError:
            return {"success": False, "message": f"File not found: {file_path}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
