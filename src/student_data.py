# student_data.py
from api_client import APIClient

def load_students_from_db():
    client = APIClient()
    result = client.get_students()
    if result.get("success"):
        return result.get("students", [])
    else:
        print("Error loading students:", result.get("message"))
        return []

def load_matieres_from_db(section_filter=None):
    client = APIClient()
    # Use "All" if no section filter is provided.
    result = client.get_matieres(section_filter or "All")
    if result.get("success"):
        matieres = result.get("matieres", [])
        matieres_s1 = [m for m in matieres if m.get("semester") == 1]
        matieres_s2 = [m for m in matieres if m.get("semester") != 1]
        return matieres_s1, matieres_s2
    else:
        print("Error loading matieres:", result.get("message"))
        return [], []

def save_grades_to_db(student_id, matiere_id, semester, ds=None, tp=None, exam=None, final=None):
    client = APIClient()
    result = client.post_grades(student_id, matiere_id, semester, ds, tp, exam, final)
    print(result.get("message", "Grades update response:"), result)

def load_grades_for_students(students_data, matieres_s1, matieres_s2):
    client = APIClient()
    for student in students_data:
        result = client.get_grades(student['id'])
        if result.get("success"):
            grades = result.get("grades", {})
            student['grades_s1'] = grades.get("grades_s1", {})
            student['grades_s2'] = grades.get("grades_s2", {})
        else:
            student['grades_s1'] = {}
            student['grades_s2'] = {}
