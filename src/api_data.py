import json
from api_client import APIClient

client = APIClient()

def get_students(section=None, bearer_token=None):
    """
    Get students for a specific section (requires Bearer token).
    """
    result = client.get_students(section, bearer_token=bearer_token)
    if result.get("success"):
        return result.get("students", [])
    else:
        print("Error loading students:", result.get("message"))
        return []

def get_matieres(section_filter="All", bearer_token=None):
    """
    Get matieres for a specific section (requires Bearer token).
    """
    result = client.get_matieres(section_filter, bearer_token=bearer_token)
    if result.get("success"):
        raw_matieres = result.get("matieres", [])
        matieres = []
        for m in raw_matieres:
            if isinstance(m, dict):
                matieres.append(m)
            else:
                weight_val = m[4]
                if isinstance(weight_val, str):
                    try:
                        weight_val = json.loads(weight_val)
                    except Exception:
                        weight_val = {}
                matieres.append({
                    "id": m[0],
                    "name": m[1],
                    "semester": m[2],
                    "has_tp": m[3],
                    "weights": weight_val,
                    "overall_weight": m[5],
                    "section": m[6]
                })
        matieres_s1 = [m for m in matieres if m.get("semester") == 1]
        matieres_s2 = [m for m in matieres if m.get("semester") != 1]
        return matieres_s1, matieres_s2
    else:
        print("Error loading matieres:", result.get("message"))
        return [], []

def get_grades(student_id, bearer_token=None):
    """
    Get grades for a student (requires Bearer token).
    """
    r = client.get_grades(student_id, bearer_token=bearer_token)
    if r.get("success"):
        data = r.get("grades", {"grades_s1": {}, "grades_s2": {}})
        return data
    else:
        print("Error loading grades:", r.get("message"))
        return {"grades_s1": {}, "grades_s2": {}}


def save_grades(student_id, matiere_id, semester, ds=None, tp=None, exam=None, final=None, bearer_token=None):
    """
    Save grades for a student (requires Bearer token).
    """
    if not bearer_token:
        print("No bearer_token provided to save_grades - route may fail!")
    r = client.post_grades(student_id, matiere_id, semester, ds, tp, exam, final, bearer_token)
    print(r.get("message", "Grades update response:"), r)
    return r

def get_user(user_id, bearer_token=None):
    """
    Get user information by ID (requires Bearer token).
    """
    r = client.get_user(user_id, bearer_token=bearer_token)
    if r.get("success"):
        return r.get("user")
    else:
        print("Error getting user:", r.get("message"))
        return None

def update_time_spent(user_id, time_spent, bearer_token=None):
    """
    Update user's time_spent_seconds in the DB (requires Bearer token).
    """
    r = client.update_time_spent(user_id, time_spent, bearer_token=bearer_token)
    if not r.get("success"):
        print("Error updating time spent:", r.get("message"))
    return r


def update_profile_pic(user_id, profile_pic_url, bearer_token=None):
    """
    Update user's profile_pic_url in the DB (requires Bearer token).
    """
    r = client.update_profile_pic(user_id, profile_pic_url, bearer_token=bearer_token)
    if not r.get("success"):
        print("Error updating profile picture:", r.get("message"))
    return r


def log_ad_click(ad_id, user_id):
    """
    Log an ad click for a user."""
    success, message = client.log_ad_click(ad_id, user_id)
    if not success:
        print("Error logging ad click:", message)
    return success, message

def get_targeted_ad(user_rank_percent):
    """
    Get a targeted ad based on the user's rank percentile.
    """
    r = client.get_targeted_ad(user_rank_percent)
    if r.get("success"):
        return r.get("ad")
    else:
        print("Error getting targeted ad:", r.get("message"))
        return None

def get_student_ai_report(student_id, bearer_token=None):
    """
    Get the AI report for a student (requires Bearer token).
    """
    r = client.get_student_ai_report(student_id, bearer_token=bearer_token)
    if r.get("success"):
        return r.get("ai_report")
    else:
        print("Error loading AI report:", r.get("message"))
        return None

def get_notifications(user_id, bearer_token=None):
    """
    Get notifications for a user (requires Bearer token).
    """
    r = client.get_notifications(user_id, bearer_token=bearer_token)
    if r.get("success"):
        return r.get("notifications", [])
    else:
        print("Error loading notifications:", r.get("message"))
        return []


def submit_reclamation(user_id, reclamation_type, description, bearer_token=None):
    """
    Submit a reclamation for a user (requires Bearer token).
    """
    return client.submit_reclamation(user_id, reclamation_type, description, bearer_token=bearer_token)


def get_reclamations(user_id, bearer_token=None):
    """
    Get reclamations for a user (requires Bearer token).
    """
    r = client.get_reclamations(user_id, bearer_token=bearer_token)
    if r.get("success"):
        return r.get("reclamations", [])
    else:
        print("Error loading reclamations:", r.get("message"))
        return []

def update_password(user_id, current_password, new_password, bearer_token=None):
    """
    Change user's password (requires Bearer token).
    """
    r = client.update_password(user_id, current_password, new_password, bearer_token=bearer_token)
    if not r.get("success"):
        print("Error updating password:", r.get("message"))
    return r


def update_notifications(user_id, subscribed, bearer_token=None):
    """
    Update user's email-notification preference (requires Bearer token).
    """
    r = client.update_notifications(user_id, subscribed, bearer_token=bearer_token)
    if not r.get("success"):
        print("Error updating notification subscription:", r.get("message"))
    return r


def add_matiere(matiere_data, bearer_token):
    """
    Add a new matiere to the database (requires Bearer token)."""
    r = client.add_matiere(matiere_data, bearer_token)
    return r

def get_all_reclamations(bearer_token):
    """
    Get all reclamations from the database (requires Bearer token).
    """
    r = client.get_all_reclamations(bearer_token)
    if r.get("success"):
        return r.get("reclamations", [])
    else:
        print("Error loading reclamations:", r.get("message"))
        return []

def update_reclamation_status(rec_id, is_solved, bearer_token):
    """
    Update the status of a reclamation (requires Bearer token).
    """
    r = client.update_reclamation_status(rec_id, is_solved, bearer_token)
    return r

def get_all_users(bearer_token):
    """
    Get all users from the database (requires Bearer token).
    """
    r = client.get_all_users(bearer_token)
    if r.get("success"):
        return r.get("users", [])
    else:
        print("Error loading users:", r.get("message"))
        return []

def cleanup_old_reclamations(bearer_token):
    """
    Cleanup old reclamations from the database (requires Bearer token).
    """
    r = client.cleanup_old_reclamations(bearer_token)
    return r.get("message", "")

def update_ai_report(student_id, ai_report, bearer_token):
    """
    Update the AI report for a student (requires Bearer token).
    """
    r = client.update_ai_report(student_id, ai_report, bearer_token)
    return r

def get_app_min_version(app_name):
    """
    Get the minimum version required for a specific app.
    """
    r = client.get_app_min_version(app_name)
    return r

def upload_admin_log_file(file_path, bearer_token):
    """
    Upload a log file to the server (requires Bearer token).
    """
    return client.upload_admin_log_file(file_path, bearer_token)
