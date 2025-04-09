# admin_app.py

import sys
import json
import os
import pickle
import csv
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QFormLayout, QApplication, QTableWidget, QTableWidgetItem, QComboBox,
    QDialog, QCheckBox, QFileDialog, QGroupBox, QProgressBar, QSpinBox, QDoubleSpinBox,
    QStackedWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QCloseEvent
from concurrent.futures import ThreadPoolExecutor, as_completed

from llama_cpp import Llama

from api_data import (
    get_students, get_matieres, get_grades, save_grades, get_user,
    add_matiere, get_all_reclamations, update_reclamation_status,
    get_all_users, cleanup_old_reclamations, update_ai_report,
    get_app_min_version, upload_admin_log_file
)
from auth import (
    login_user, login_user_with_token, clear_auth_token,
    send_notification_to_all, send_notification_to_user, send_notification_to_section
)
from utils import log_action, log_admin_action

ADMIN_APP_VERSION = "1.0.0"

def resource_path(relative_path):
    """
    Resolve resource paths properly, especially for packaged distributions (e.g., PyInstaller).
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.abspath("."), relative_path)

class AdminApp(QMainWindow):
    """
    Main admin application for managing subjects, grades, reclamations, notifications, 
    and generating AI-based orientation reports.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin Panel")
        self.resize(800, 600)

        font = QFont("Poppins", 12)
        QApplication.instance().setFont(font)

        # LLM references for AI-based report generation (if admin)
        self.llm = None
        self.admin_token = None
        self.admin_role = None
        self.admin_email = None
        self.saved_theme = "Light"

        # Attempt to load a remembered token
        self.load_admin_token_if_remembered()

        # Check version compatibility with the backend
        if not self.check_app_version():
            sys.exit(0)

        # Prepare the login page and main interface, using a QStackedWidget
        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)

        self.login_page = QWidget()
        self.build_login_page(self.login_page)

        self.main_page = QWidget()
        self.build_main_page(self.main_page)

        self.stacked.addWidget(self.login_page)
        self.stacked.addWidget(self.main_page)

        # If a token is found, try auto-login
        if self.admin_token:
            success, user_data = login_user_with_token(self.admin_token)
            if success:
                role = user_data.get("role", "").strip().lower()
                if role == "admin":
                    self.admin_role = "admin"
                    self.admin_email = user_data.get("email", "unknown@insat.ucar.tn")
                elif role == "friend":
                    self.admin_role = "friend"
                    self.admin_email = user_data.get("email", "unknown@insat.ucar.tn")

                    # For a 'friend' role, find the assigned section
                    friend_id = user_data.get("id")
                    friend_info = get_user(friend_id, bearer_token=self.admin_token)
                    if friend_info:
                        self.friend_section = friend_info.get("section", "").lower()
                    else:
                        self.friend_section = ""
                else:
                    # If the role doesn't match, remove the stored token and show login
                    if os.path.exists("remember_admin.pkl"):
                        os.remove("remember_admin.pkl")
                    self.show_login_interface()
                    return

                # Apply saved theme
                chosen_mode = self.saved_theme
                if chosen_mode == "Dark":
                    with open(resource_path("resources/admindark.qss"), "r", encoding="utf-8") as f:
                        QApplication.instance().setStyleSheet(f.read())
                else:
                    QApplication.instance().setStyleSheet("")

                self.show_main_interface()
            else:
                # Auto-login failed; remove token and show login
                if os.path.exists("remember_admin.pkl"):
                    os.remove("remember_admin.pkl")
                self.show_login_interface()
        else:
            self.show_login_interface()

    def load_admin_token_if_remembered(self):
        """
        Load a previously saved admin token and UI theme, if present.
        """
        if os.path.exists("remember_admin.pkl"):
            with open("remember_admin.pkl", "rb") as f:
                data = pickle.load(f)
                self.admin_token = data.get("admin_token", None)
                self.saved_theme = data.get("theme", "Light")

    def closeEvent(self, event: QCloseEvent):
        """
        On close, upload daily logs to Cloudinary.
        """
        if self.admin_token and (self.admin_role == "admin"):
            log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
            if os.path.exists(log_filename):
                response = upload_admin_log_file(log_filename, self.admin_token)
                if response.get("success"):
                    log_admin_action(self.admin_email, f"Uploaded admin logs on close => {log_filename}")
                else:
                    msg = response.get("message", "Unknown error uploading logs")
                    log_admin_action(self.admin_email, f"Failed to upload logs on close => {msg}")
        event.accept()

    def build_login_page(self, page_widget):
        """
        Construct the login form with fields for email, password, 
        'Remember me' checkbox, and a theme mode selector.
        """
        layout = QVBoxLayout(page_widget)
        form_layout = QFormLayout()

        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Admin/Friend Email:", self.email_input)
        form_layout.addRow("Password:", self.password_input)

        self.remember_check = QCheckBox("Remember me")
        form_layout.addRow(self.remember_check)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Light", "Dark"])
        form_layout.addRow("Theme Mode:", self.mode_combo)

        btn_login = QPushButton("Login")
        btn_login.clicked.connect(self.do_admin_login)

        layout.addLayout(form_layout)
        layout.addWidget(btn_login, alignment=Qt.AlignCenter)

    def get_allowed_sections(self):
        """
        Return the sections accessible by the current user, based on admin vs friend role.
        """
        if self.admin_role == "admin":
            return ["rt", "gl", "iia", "imi", "mpi", "cba", "bio", "ch"]
        elif self.admin_role == "friend":
            s = getattr(self, "friend_section", "")
            if s in ["rt", "gl", "iia", "imi"]:
                return ["rt", "gl", "iia", "imi"]
            elif s:
                return [s]
            else:
                return []
        else:
            return []

    def check_app_version(self) -> bool:
        """
        Compare the local ADMIN_APP_VERSION to the server's min required version.
        If below the required version, display an error and return False.
        """
        resp = get_app_min_version("admin_app")
        if not resp.get("success"):
            QMessageBox.warning(
                self,
                "Version Check Warning",
                f"Could not verify minimal version requirement.\n{resp.get('message')}\nContinuing anyway."
            )
            return True

        min_required = resp["min_version"]
        if not self.is_version_compatible(ADMIN_APP_VERSION, min_required):
            QMessageBox.critical(
                self,
                "Outdated Version",
                f"Local Admin App version ({ADMIN_APP_VERSION}) is below minimum required ({min_required})."
            )
            return False
        return True

    @staticmethod
    def is_version_compatible(local_version, min_version):
        """
        Compare two semantic version strings (e.g. "1.0.0" vs. "0.9.2") 
        to see if local_version >= min_version.
        """
        def parse(ver):
            return [int(x) for x in ver.split('.') if x.isdigit()]
        try:
            lv = parse(local_version)
            mv = parse(min_version)
            for i in range(max(len(lv), len(mv))):
                a = lv[i] if i < len(lv) else 0
                b = mv[i] if i < len(mv) else 0
                if a < b:
                    return False
                elif a > b:
                    return True
            return True
        except:
            # If parsing fails, consider them compatible by default
            return True

    def upload_logs_to_cloudinary(self):
        """
        Manually upload logs for the current day to Cloudinary (for admin).
        """
        log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
        if not os.path.exists(log_filename):
            QMessageBox.information(self, "No Logs", f"No log file found at {log_filename}")
            return

        if not self.admin_token:
            QMessageBox.critical(self, "Error", "No admin token found. Please log in first.")
            return

        response = upload_admin_log_file(log_filename, self.admin_token)
        if response.get("success"):
            QMessageBox.information(self, "Success", "Admin log file uploaded.")
            log_admin_action(self.admin_email, f"Uploaded logs file {log_filename} to Cloudinary.")
        else:
            err = response.get("message", "Unknown error")
            QMessageBox.critical(self, "Error", f"Failed to upload logs: {err}")

    def build_main_page(self, page_widget):
        """
        Build the main UI for admin/friend roles:
        - Matière management
        - Grade assignment
        - Bulk operations
        - Reclamation management
        - CSV import
        - Notifications
        - AI Reports (admin only)
        """
        self.main_layout = QVBoxLayout(page_widget)

        btn_add_matiere = QPushButton("Add Matière")
        btn_add_matiere.clicked.connect(self.add_matiere_dialog)

        btn_assign_grades = QPushButton("Assign Grades")
        btn_assign_grades.clicked.connect(self.assign_grades_dialog)

        btn_bulk_add_grades = QPushButton("Bulk Add Grades")
        btn_bulk_add_grades.clicked.connect(self.bulk_add_grades_dialog)

        btn_manage_reclamations = QPushButton("Manage Reclamations")
        btn_manage_reclamations.clicked.connect(self.manage_reclamations_dialog)

        btn_import_grades = QPushButton("Import Grades from CSV")
        btn_import_grades.clicked.connect(self.import_grades_from_csv_dialog)

        btn_notify_all = QPushButton("Send Notification to All")
        btn_notify_all.clicked.connect(self.send_notif_all_dialog)

        btn_notify_user = QPushButton("Send Notification to Specific User")
        btn_notify_user.clicked.connect(self.send_notif_user_dialog)

        btn_notify_section = QPushButton("Send Notification to Section")
        btn_notify_section.clicked.connect(self.send_notif_section_dialog)

        btn_generate_ai_reports = QPushButton("Generate AI Reports for MPI")
        btn_generate_ai_reports.clicked.connect(self.generate_ai_reports_for_mpi)

        btn_logout = QPushButton("Logout Admin")
        btn_logout.clicked.connect(self.logout_admin)

        # Friend role sees fewer actions
        if self.admin_role == "friend":
            self.main_layout.addWidget(btn_add_matiere)
            self.main_layout.addWidget(btn_assign_grades)
            self.main_layout.addWidget(btn_bulk_add_grades)
            self.main_layout.addWidget(btn_manage_reclamations)
        else:
            self.main_layout.addWidget(btn_add_matiere)
            self.main_layout.addWidget(btn_assign_grades)
            self.main_layout.addWidget(btn_bulk_add_grades)
            self.main_layout.addWidget(btn_manage_reclamations)
            self.main_layout.addWidget(btn_import_grades)
            self.main_layout.addWidget(btn_notify_all)
            self.main_layout.addWidget(btn_notify_user)
            self.main_layout.addWidget(btn_notify_section)
            self.main_layout.addWidget(btn_generate_ai_reports)

        self.main_layout.addWidget(btn_logout, alignment=Qt.AlignRight)

        # Table to display Matières
        self.matieres_view = QTableWidget()
        self.main_layout.addWidget(self.matieres_view)

        # Perform a cleanup of old, solved reclamations at launch
        self.cleanup_old_solved_reclamations()

    def show_login_interface(self):
        """
        Switch the stacked widget to display the login page.
        """
        self.stacked.setCurrentIndex(0)

    def show_main_interface(self):
        """
        Switch the stacked widget to display the main admin interface.
        """
        self.load_matieres_table()
        self.stacked.setCurrentIndex(1)

    def do_admin_login(self):
        """
        Handle the admin/friend login by calling the auth endpoint with email/password.
        If successful, store the token (if 'Remember me' is checked) and apply the chosen theme.
        """
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        success, user_data, top_auth_token, refresh_token = login_user(email, password)
        if not success:
            QMessageBox.critical(self, "Error", f"Login failed: {user_data}")
            return

        self.admin_email = email
        role = user_data.get("role", "")

        # Store admin token
        self.admin_token = top_auth_token

        if role == "admin":
            self.admin_role = "admin"
        elif role == "friend":
            self.admin_role = "friend"
            friend_id = user_data.get("id")
            friend_info = get_user(friend_id, bearer_token=self.admin_token)
            if friend_info:
                self.friend_section = friend_info.get("section", "").lower()
            else:
                self.friend_section = ""
        else:
            QMessageBox.critical(self, "Error", "You do not have admin/friend privileges.")
            return

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_admin_action(email, f"Admin login successful at {current_time}")

        if self.remember_check.isChecked():
            chosen_theme = self.mode_combo.currentText()
            with open("remember_admin.pkl", "wb") as f:
                pickle.dump({"admin_token": self.admin_token, "theme": chosen_theme}, f)

        chosen_mode = self.mode_combo.currentText()
        if chosen_mode == "Dark":
            with open(resource_path("resources/admindark.qss"), "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
        else:
            QApplication.instance().setStyleSheet("")

        self.show_main_interface()

    def add_matiere_dialog(self):
        """
        Dialog for adding a new Matière (course).
        Allows specifying name, semester, whether it has TP, 
        weights for DS/TP/Exam, etc.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Matière")
        layout = QVBoxLayout(dialog)

        instructions = QLabel("Fill in the details for the new Matière and click 'Add':")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        group_info = QGroupBox("Matière Info")
        form_info = QFormLayout(group_info)

        name_input = QLineEdit()
        semester_input = QSpinBox()
        semester_input.setRange(1, 2)
        tp_box = QComboBox()
        tp_box.addItems(["No", "Yes"])
        section_box = QComboBox()
        section_box.addItems(["rt", "gl", "iia", "imi", "mpi", "cba", "bio", "ch"])

        form_info.addRow("Name:", name_input)
        form_info.addRow("Semester:", semester_input)
        form_info.addRow("Has TP:", tp_box)
        form_info.addRow("Section:", section_box)
        layout.addWidget(group_info)

        group_weights = QGroupBox("Weights")
        form_weights = QFormLayout(group_weights)

        ds_input = QDoubleSpinBox()
        ds_input.setRange(0.0, 1.0)
        ds_input.setDecimals(2)
        ds_input.setSingleStep(0.1)
        ds_input.setValue(0.3)

        tp_input = QDoubleSpinBox()
        tp_input.setRange(0.0, 1.0)
        tp_input.setDecimals(2)
        tp_input.setSingleStep(0.1)
        tp_input.setValue(0.2)

        exam_input = QDoubleSpinBox()
        exam_input.setRange(0.0, 1.0)
        exam_input.setDecimals(2)
        exam_input.setSingleStep(0.1)
        exam_input.setValue(0.5)

        overall_input = QDoubleSpinBox()
        overall_input.setRange(0.0, 10.0)
        overall_input.setDecimals(2)
        overall_input.setSingleStep(0.5)
        overall_input.setValue(2.0)

        form_weights.addRow("DS Weight:", ds_input)
        form_weights.addRow("TP Weight:", tp_input)
        form_weights.addRow("Exam Weight:", exam_input)
        form_weights.addRow("Overall Coefficient:", overall_input)
        layout.addWidget(group_weights)

        def validate_weights():
            total = ds_input.value() + tp_input.value() + exam_input.value()
            eps = 1e-6
            if abs(total - 1.0) < eps:
                ds_input.setStyleSheet("")
                tp_input.setStyleSheet("")
                exam_input.setStyleSheet("")
            else:
                ds_input.setStyleSheet("background-color: #ffcccc;")
                tp_input.setStyleSheet("background-color: #ffcccc;")
                exam_input.setStyleSheet("background-color: #ffcccc;")

        ds_input.valueChanged.connect(validate_weights)
        tp_input.valueChanged.connect(validate_weights)
        exam_input.valueChanged.connect(validate_weights)

        def update_tp():
            if tp_box.currentText() == "Yes":
                tp_input.setEnabled(True)
            else:
                tp_input.setValue(0.0)
                tp_input.setEnabled(False)
            validate_weights()

        tp_box.currentIndexChanged.connect(update_tp)
        update_tp()

        btn_layout = QHBoxLayout()

        def fill_defaults():
            ds_input.setValue(0.3)
            if tp_box.currentText() == "Yes":
                tp_input.setValue(0.2)
            else:
                tp_input.setValue(0.0)
            exam_input.setValue(0.5)
            overall_input.setValue(2.0)
            validate_weights()

        btn_defaults = QPushButton("Use Defaults")
        btn_defaults.clicked.connect(fill_defaults)

        btn_clear = QPushButton("Clear")
        def clear_form():
            name_input.clear()
            semester_input.setValue(1)
            tp_box.setCurrentIndex(0)
            section_box.setCurrentIndex(0)
            ds_input.setValue(0.0)
            tp_input.setValue(0.0)
            exam_input.setValue(0.0)
            overall_input.setValue(0.0)
            validate_weights()
            update_tp()
        btn_clear.clicked.connect(clear_form)
        btn_add = QPushButton("Add Matière")
        btn_cancel = QPushButton("Cancel")

        def do_add():
            name = name_input.text().strip()
            sem = semester_input.value()
            has_tp = (tp_box.currentText() == "Yes")
            sec = section_box.currentText()

            ds_w = ds_input.value()
            tp_w = tp_input.value() if has_tp else 0.0
            exam_w = exam_input.value()
            overall_w = overall_input.value()

            if not name:
                QMessageBox.warning(dialog, "Error", "Name is required.")
                return

            total = ds_w + tp_w + exam_w
            if abs(total - 1.0) > 1e-6:
                QMessageBox.warning(dialog, "Error", f"DS+TP+Exam must sum to 1.0 (currently {total:.2f}).")
                return

            mat_data = {
                "name": name,
                "semester": sem,
                "has_tp": has_tp,
                "weights": {"DS": ds_w, "TP": tp_w, "Exam": exam_w},
                "overall_weight": overall_w,
                "section": sec
            }
            try:
                result = add_matiere(mat_data, self.admin_token)
                if result.get("success"):
                    log_admin_action(self.admin_email, f"Added matière '{name}' in section '{sec}' (sem {sem})")
                    QMessageBox.information(dialog, "Added", "Matière added successfully.")
                    dialog.accept()
                    self.load_matieres_table()
                else:
                    QMessageBox.warning(dialog, "Failed", result.get("message", "Error adding matière."))
            except Exception as e:
                QMessageBox.critical(dialog, "Error", str(e))

        btn_add.clicked.connect(do_add)
        btn_cancel.clicked.connect(dialog.reject)

        btn_layout.addWidget(btn_defaults)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        dialog.exec_()

    def assign_grades_dialog(self):
        """
        Dialog to assign grades to a single student in a single Matière.
        Loads students/matières using the admin token, then calls save_grades.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Assign Grades")
        layout = QFormLayout(dialog)

        # Load students
        students = get_students(bearer_token=self.admin_token)
        if not students:
            QMessageBox.critical(self, "Error", "Failed to load students (no data or invalid token).")
            return

        # Load matieres
        mat_s1, mat_s2 = get_matieres("All", bearer_token=self.admin_token)
        if not mat_s1 and not mat_s2:
            QMessageBox.critical(self, "Error", "Failed to load matieres (invalid token or no data).")
            return
        matieres = mat_s1 + mat_s2

        student_box = QComboBox()
        for s in students:
            label = f"{s.get('display_id','')} - {s.get('prenom','')} {s.get('nom','')}"
            student_box.addItem(label, s.get("id"))

        matiere_box = QComboBox()
        for m in matieres:
            label = f"{m.get('name')} (Sem:{m.get('semester')}, Sec:{m.get('section')})"
            matiere_box.addItem(label, (m.get("name"), m.get("semester"), m.get("section"), m.get("has_tp")))

        ds_input = QLineEdit()
        tp_input = QLineEdit()
        exam_input = QLineEdit()

        layout.addRow("Student:", student_box)
        layout.addRow("Matière:", matiere_box)
        layout.addRow("DS:", ds_input)
        layout.addRow("TP:", tp_input)
        layout.addRow("Exam:", exam_input)

        btn_save = QPushButton("Save Grades")
        btn_cancel = QPushButton("Cancel")

        def do_save():
            sid = student_box.currentData()
            nm, sem, sec, htp = matiere_box.currentData()
            try:
                ds_val = float(ds_input.text().strip()) if ds_input.text() else None
                tp_val = float(tp_input.text().strip()) if (tp_input.text() and htp) else None
                exam_val = float(exam_input.text().strip()) if exam_input.text() else None

                # Re-fetch matieres for the chosen section
                m_s1, m_s2 = get_matieres(sec, bearer_token=self.admin_token)
                all_m = m_s1 + m_s2
                mat_obj = None
                for mm in all_m:
                    if mm["name"] == nm and mm["semester"] == sem:
                        mat_obj = mm
                        break
                if not mat_obj:
                    QMessageBox.critical(dialog, "Error", "Matière not found in the selected section.")
                    return

                ds_calc = ds_val or 0
                tp_calc = tp_val or 0
                exam_calc = exam_val or 0
                ds_w = mat_obj.get("weights", {}).get("DS", 0)
                tp_w = mat_obj.get("weights", {}).get("TP", 0)
                exam_w = mat_obj.get("weights", {}).get("Exam", 0)
                final_val = round(ds_calc * ds_w + tp_calc * tp_w + exam_calc * exam_w, 2)

                res = save_grades(
                    student_id=sid,
                    matiere_id=mat_obj["id"],
                    semester=sem,
                    ds=ds_val,
                    tp=tp_val,
                    exam=exam_val,
                    final=final_val,
                    bearer_token=self.admin_token
                )
                if res.get("success"):
                    student_name = student_box.currentText()
                    matiere_name = matiere_box.currentText()
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log_admin_action(
                        self.admin_email,
                        f"Assigned grades for {student_name} in {matiere_name} at {current_time}"
                    )
                    QMessageBox.information(dialog, "Success", "Grades saved.")
                    dialog.accept()
                else:
                    QMessageBox.critical(dialog, "Error", res.get("message", "Failed to save."))
            except Exception as e:
                QMessageBox.critical(dialog, "Error", str(e))

        btn_save.clicked.connect(do_save)
        btn_cancel.clicked.connect(dialog.reject)

        h = QHBoxLayout()
        h.addWidget(btn_save)
        h.addWidget(btn_cancel)
        layout.addRow(h)
        dialog.exec_()

    def bulk_add_grades_dialog(self):
        """
        Dialog to bulk-assign grades for a chosen Matière and selected sections.
        This includes a table for DS/TP/Exam values. Uses multi-threading to save concurrently.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk Add Grades")
        dialog.resize(900, 600)
        main_layout = QVBoxLayout(dialog)

        instructions = QLabel(
            "Check sections, pick one Matière, fill DS/TP/Exam, then 'Save All Grades'."
        )
        instructions.setWordWrap(True)
        main_layout.addWidget(instructions)

        section_group = QGroupBox("Sections")
        section_h = QHBoxLayout(section_group)
        self.section_list = self.get_allowed_sections()
        self.section_checkboxes = {}
        for s in self.section_list:
            cb = QCheckBox(s.upper())
            cb.setChecked(False)
            cb.stateChanged.connect(lambda st, sx=s: refresh_matieres())
            section_h.addWidget(cb)
            self.section_checkboxes[s] = cb
        main_layout.addWidget(section_group)

        matiere_grp = QGroupBox("Choose Matière")
        matiere_form = QFormLayout(matiere_grp)
        self.matiere_box = QComboBox()
        matiere_form.addRow("Matière:", self.matiere_box)
        main_layout.addWidget(matiere_grp)

        self.grades_table = QTableWidget()
        self.grades_table.setColumnCount(5)
        self.grades_table.setHorizontalHeaderLabels(["ID", "Name", "DS", "TP", "Exam"])
        main_layout.addWidget(self.grades_table, stretch=1)

        btn_bar = QHBoxLayout()
        btn_save = QPushButton("Save All Grades")
        btn_cancel = QPushButton("Cancel")
        btn_bar.addWidget(btn_save)
        btn_bar.addWidget(btn_cancel)
        main_layout.addLayout(btn_bar)

        self.cached_grades = {}

        def refresh_matieres():
            self.matiere_box.clear()
            selected_sections = [s for s in self.section_list if self.section_checkboxes[s].isChecked()]
            if not selected_sections:
                return

            matieres_collected = []
            for sec in selected_sections:
                m_s1, m_s2 = get_matieres(sec, bearer_token=self.admin_token)
                matieres_collected.extend(m_s1 + m_s2)

            # Deduplicate by ID
            unique = {}
            for mm in matieres_collected:
                unique[mm["id"]] = mm

            for mid, mm in unique.items():
                lbl = f"{mm['name']} (Sem:{mm['semester']}, Sec:{mm['section']})"
                self.matiere_box.addItem(lbl, (mm["name"], mm["semester"], mm["section"], mm["has_tp"]))

        def load_students():
            self.grades_table.clearContents()
            self.grades_table.setRowCount(0)
            data = self.matiere_box.currentData()
            if not data:
                return

            nm, sem, sec, htp = data
            studs = get_students(sec, bearer_token=self.admin_token)
            if not studs:
                QMessageBox.critical(dialog, "Error", f"No students found in section '{sec}' or token error.")
                return
            studs.sort(key=lambda x: x.get("nom", "").lower())

            m_s1, m_s2 = get_matieres(sec, bearer_token=self.admin_token)
            all_m = m_s1 + m_s2
            mat_obj = None
            for mat in all_m:
                if mat["name"] == nm and mat["semester"] == sem:
                    mat_obj = mat
                    break
            if not mat_obj:
                QMessageBox.critical(dialog, "Error", "Matière not found!")
                return

            progress_dialog = QDialog(dialog)
            progress_dialog.setWindowTitle("Loading Grades...")
            pv_layout = QVBoxLayout(progress_dialog)
            p_label = QLabel("Loading student grades, please wait...")
            pv_layout.addWidget(p_label)
            p_bar = QProgressBar()
            p_bar.setRange(0, len(studs))
            pv_layout.addWidget(p_bar)
            progress_dialog.setModal(True)
            progress_dialog.show()

            results = {}
            with ThreadPoolExecutor(max_workers=30) as exe:
                future_map = {}
                for st in studs:
                    sid = st["id"]
                    if sid in self.cached_grades:
                        results[sid] = self.cached_grades[sid]
                    else:
                        fut = exe.submit(get_grades, sid, bearer_token=self.admin_token)
                        future_map[fut] = sid

                done_count = 0
                for fut in as_completed(future_map):
                    sid = future_map[fut]
                    try:
                        data_gr = fut.result()
                        results[sid] = data_gr
                        self.cached_grades[sid] = data_gr
                    except:
                        results[sid] = {}
                    done_count += 1
                    p_bar.setValue(done_count)

            progress_dialog.close()

            self.grades_table.setColumnCount(5)
            col_labels = ["ID", "Name", "DS", "TP" if htp else "TP (N/A)", "Exam"]
            self.grades_table.setHorizontalHeaderLabels(col_labels)
            self.grades_table.setRowCount(len(studs))

            mat_id_str = str(mat_obj["id"])
            for i, st in enumerate(studs):
                sid = st["id"]
                self.grades_table.setItem(i, 0, QTableWidgetItem(str(sid)))
                self.grades_table.item(i, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                st_name = f"{st.get('prenom','')} {st.get('nom','')}"
                self.grades_table.setItem(i, 1, QTableWidgetItem(st_name))
                self.grades_table.item(i, 1).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                user_grades = results[sid]
                if sem == 1:
                    g_obj = user_grades.get("grades_s1", {}).get(mat_id_str, {})
                else:
                    g_obj = user_grades.get("grades_s2", {}).get(mat_id_str, {})

                ds_val = g_obj.get("DS")
                tp_val = g_obj.get("TP") if htp else None
                exam_val = g_obj.get("Exam")

                self.grades_table.setItem(i, 2, QTableWidgetItem("" if ds_val is None else str(ds_val)))
                self.grades_table.setItem(i, 3, QTableWidgetItem("" if tp_val is None else str(tp_val)))
                self.grades_table.setItem(i, 4, QTableWidgetItem("" if exam_val is None else str(exam_val)))

            self.grades_table.resizeColumnsToContents()

        def save_all_grades():
            data = self.matiere_box.currentData()
            if not data:
                QMessageBox.critical(dialog, "Error", "No Matière selected.")
                return

            nm, sem, sec, htp = data
            m_s1, m_s2 = get_matieres(sec, bearer_token=self.admin_token)
            all_m = m_s1 + m_s2
            mat_obj = None
            for mm in all_m:
                if mm["name"] == nm and mm["semester"] == sem:
                    mat_obj = mm
                    break
            if not mat_obj:
                QMessageBox.critical(dialog, "Error", "Matière not found!")
                return

            ds_w = mat_obj.get("weights", {}).get("DS", 0)
            tp_w = mat_obj.get("weights", {}).get("TP", 0)
            exam_w = mat_obj.get("weights", {}).get("Exam", 0)

            def safe_float(txt):
                t = txt.strip()
                if not t:
                    return None
                try:
                    return float(t)
                except:
                    return None

            rows = self.grades_table.rowCount()
            if rows == 0:
                QMessageBox.information(dialog, "No Data", "No student data to save.")
                return

            progress_dialog = QDialog(dialog)
            progress_dialog.setWindowTitle("Saving Grades...")
            pl = QVBoxLayout(progress_dialog)
            p_label = QLabel("Saving grades, please wait...")
            pl.addWidget(p_label)
            p_bar = QProgressBar()
            p_bar.setRange(0, rows)
            pl.addWidget(p_bar)
            progress_dialog.setModal(True)
            progress_dialog.show()

            success_count = 0
            error_count = 0

            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=30) as exe:
                tasks = []
                for i in range(rows):
                    sid = self.grades_table.item(i, 0).text().strip()
                    ds_txt = self.grades_table.item(i, 2).text()
                    tp_txt = self.grades_table.item(i, 3).text()
                    exam_txt = self.grades_table.item(i, 4).text()

                    ds_val = safe_float(ds_txt)
                    tp_val = safe_float(tp_txt) if htp else None
                    exam_val = safe_float(exam_txt)

                    ds_calc = ds_val or 0
                    tp_calc = tp_val or 0
                    exam_calc = exam_val or 0
                    final_val = round(ds_calc * ds_w + tp_calc * tp_w + exam_calc * exam_w, 2)

                    fut = exe.submit(
                        save_grades,
                        sid,
                        mat_obj["id"],
                        sem,
                        ds_val,
                        tp_val,
                        exam_val,
                        final_val,
                        self.admin_token
                    )
                    tasks.append(fut)

                done_count = 0
                for fut in as_completed(tasks):
                    done_count += 1
                    p_bar.setValue(done_count)
                    try:
                        result = fut.result()
                        if result.get("success"):
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        error_count += 1
                        log_admin_action(self.admin_email, f"Error in bulk grade save: {str(e)}")

            progress_dialog.close()

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_admin_action(
                self.admin_email,
                f"Bulk-added grades for section {sec} in {nm} at {current_time}."
            )
            QMessageBox.information(dialog, "Done",
                                    f"Grades saved (Success: {success_count}, Errors: {error_count}).")
            dialog.accept()

        self.matiere_box.currentIndexChanged.connect(load_students)
        btn_save.clicked.connect(save_all_grades)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def import_grades_from_csv_dialog(self):
        """
        Dialog to import grades from a CSV file for a specific Matière.
        Uses the admin token for relevant calls.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Import Grades from CSV")
        main_layout = QVBoxLayout(dialog)

        form = QFormLayout()

        # Load all matieres with admin token
        mat_s1, mat_s2 = get_matieres("All", bearer_token=self.admin_token)
        if not mat_s1 and not mat_s2:
            QMessageBox.critical(self, "Error", "Failed to load matieres (token error or none found).")
            return
        all_mat = mat_s1 + mat_s2

        matiere_box = QComboBox()
        for m in all_mat:
            label = f"{m.get('name')} (Sem:{m.get('semester')}, Sec:{m.get('section')})"
            matiere_box.addItem(label, (m["name"], m["semester"], m["section"], m["has_tp"]))

        form.addRow("Matière:", matiere_box)
        csv_label = QLabel("No file selected.")

        def select_csv():
            try:
                import subprocess
                try:
                    result = subprocess.run(
                        [
                            "zenity",
                            "--file-selection",
                            "--title=Select CSV File",
                            "--file-filter=CSV Files | *.csv"
                        ],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        return
                    fname = result.stdout.strip()
                except subprocess.SubprocessError:
                    fname, _ = QFileDialog.getOpenFileName(
                        dialog, "Select CSV", "", "CSV Files (*.csv)"
                    )
                    if not fname:
                        return

                if not os.path.exists(fname):
                    QMessageBox.critical(dialog, "Error", "File does not exist.")
                    return
                if os.path.getsize(fname) > 10 * 1024 * 1024:
                    QMessageBox.critical(dialog, "Error", "File too large (max 10MB).")
                    return
                csv_label.setText(fname)
            except Exception as e:
                QMessageBox.critical(dialog, "Error", str(e))

        btn_select_csv = QPushButton("Select CSV")
        btn_select_csv.clicked.connect(select_csv)
        form.addRow(btn_select_csv, csv_label)
        main_layout.addLayout(form)

        def do_import():
            if csv_label.text() == "No file selected.":
                QMessageBox.warning(dialog, "Warning", "No CSV file selected.")
                return

            nm, sem, sec, htp = matiere_box.currentData()

            # Find the chosen matiere
            mm_s1, mm_s2 = get_matieres(sec, bearer_token=self.admin_token)
            mat_all = mm_s1 + mm_s2
            mat_obj = None
            for mm in mat_all:
                if mm["name"] == nm and mm["semester"] == sem:
                    mat_obj = mm
                    break
            if not mat_obj:
                QMessageBox.critical(dialog, "Error", "Matière not found!")
                return

            ds_w = mat_obj.get("weights", {}).get("DS", 0)
            tp_w = mat_obj.get("weights", {}).get("TP", 0)
            exam_w = mat_obj.get("weights", {}).get("Exam", 0)

            try:
                with open(csv_label.text(), "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sid = row.get("id", "").strip()
                        ds_val = float(row["ds"]) if row.get("ds") else None
                        tp_val = float(row["tp"]) if (row.get("tp") and htp) else None
                        exam_val = float(row["exam"]) if row.get("exam") else None

                        ds_calc = ds_val or 0
                        tp_calc = tp_val or 0
                        exam_calc = exam_val or 0
                        final_val = round(ds_calc * ds_w + tp_calc * tp_w + exam_calc * exam_w, 2)

                        save_grades(
                            student_id=sid,
                            matiere_id=mat_obj["id"],
                            semester=sem,
                            ds=ds_val,
                            tp=tp_val,
                            exam=exam_val,
                            final=final_val,
                            bearer_token=self.admin_token
                        )

                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_admin_action(
                    self.admin_email,
                    f"Imported CSV grades into {nm} (Section {sec}) at {current_time}"
                )
                QMessageBox.information(dialog, "Success", "Grades imported successfully.")
                dialog.accept()

            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to import: {str(e)}")

        btn_import = QPushButton("Import")
        btn_import.clicked.connect(do_import)
        main_layout.addWidget(btn_import, alignment=Qt.AlignCenter)
        dialog.exec_()

    def send_notif_all_dialog(self):
        """
        Dialog for sending a notification to all users.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Send Notification to All")
        layout = QFormLayout(dialog)

        title_input = QLineEdit()
        body_input = QLineEdit()

        layout.addRow("Title:", title_input)
        layout.addRow("Body:", body_input)

        btn_send = QPushButton("Send")
        btn_cancel = QPushButton("Cancel")

        def do_send():
            title = title_input.text().strip()
            bdy = body_input.text().strip()
            succ, msg = send_notification_to_all(title, bdy, self.admin_token)
            if succ:
                QMessageBox.information(dialog, "Success", msg)
                dialog.accept()
            else:
                QMessageBox.critical(dialog, "Error", msg)

        h = QHBoxLayout()
        h.addWidget(btn_send)
        h.addWidget(btn_cancel)
        layout.addRow(h)

        btn_send.clicked.connect(do_send)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def send_notif_user_dialog(self):
        """
        Dialog for sending a notification to a specific user.
        Loads the list of all users, then calls the relevant API endpoint.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Send Notification to User")
        layout = QFormLayout(dialog)

        all_users = get_all_users(self.admin_token)
        user_box = QComboBox()
        for u in all_users:
            user_box.addItem(u.get("email", "Unknown"), u.get("id"))

        title_input = QLineEdit()
        body_input = QLineEdit()

        layout.addRow("User:", user_box)
        layout.addRow("Title:", title_input)
        layout.addRow("Body:", body_input)

        btn_send = QPushButton("Send")
        btn_cancel = QPushButton("Cancel")

        def do_send():
            uid = user_box.currentData()
            t = title_input.text().strip()
            b = body_input.text().strip()
            succ, msg = send_notification_to_user(uid, t, b, self.admin_token)
            if succ:
                QMessageBox.information(dialog, "Success", msg)
                dialog.accept()
            else:
                QMessageBox.critical(dialog, "Error", msg)

        h = QHBoxLayout()
        h.addWidget(btn_send)
        h.addWidget(btn_cancel)
        layout.addRow(h)

        btn_send.clicked.connect(do_send)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def send_notif_section_dialog(self):
        """
        Dialog for sending a notification to all users in a single section.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Send Notification to a Section")
        layout = QFormLayout(dialog)

        section_box = QComboBox()
        section_box.addItems(["rt", "gl", "iia", "imi", "mpi", "cba", "bio", "ch"])

        title_input = QLineEdit()
        body_input = QLineEdit()

        layout.addRow("Section:", section_box)
        layout.addRow("Title:", title_input)
        layout.addRow("Body:", body_input)

        btn_send = QPushButton("Send")
        btn_cancel = QPushButton("Cancel")

        def do_send():
            section_val = section_box.currentText()
            t = title_input.text().strip()
            b = body_input.text().strip()
            succ, msg = send_notification_to_section(section_val, t, b, self.admin_token)
            if succ:
                QMessageBox.information(dialog, "Success", msg)
                dialog.accept()
            else:
                QMessageBox.critical(dialog, "Error", msg)

        btn_h = QHBoxLayout()
        btn_h.addWidget(btn_send)
        btn_h.addWidget(btn_cancel)
        layout.addRow(btn_h)

        btn_send.clicked.connect(do_send)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def manage_reclamations_dialog(self):
        """
        Dialog that lists reclamations and allows marking them as solved/unsolved.
        Each check state change triggers an update to the API.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Reclamations")
        dialog.resize(800, 600)
        main_layout = QVBoxLayout(dialog)

        rec_list = get_all_reclamations(self.admin_token)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["ID", "User", "Type", "Description", "Timestamp", "Solved"])
        table.setRowCount(len(rec_list))

        for i, rec in enumerate(rec_list):
            table.setItem(i, 0, QTableWidgetItem(str(rec.get("id"))))

            u_data = get_user(rec.get("user_id"), bearer_token=self.admin_token)
            uname = u_data.get("email", "Unknown") if u_data else "Unknown"
            table.setItem(i, 1, QTableWidgetItem(uname))

            table.setItem(i, 2, QTableWidgetItem(rec.get("reclamation_type","")))
            table.setItem(i, 3, QTableWidgetItem(rec.get("description","")))

            ts = rec.get("timestamp","")
            try:
                dt = datetime.fromisoformat(ts)
                ts_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                ts_str = ts
            table.setItem(i, 4, QTableWidgetItem(ts_str))

            solved_item = QTableWidgetItem()
            solved_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            solved_item.setCheckState(Qt.Checked if rec.get("is_solved") else Qt.Unchecked)
            table.setItem(i, 5, solved_item)

        table.resizeColumnsToContents()
        main_layout.addWidget(table)

        def on_cell_changed(row, col):
            if col == 5:
                rec_obj = rec_list[row]
                new_state = table.item(row, col).checkState() == Qt.Checked
                update_reclamation_status(rec_obj["id"], new_state, self.admin_token)
                log_action(f"Reclamation {rec_obj['id']} => is_solved={new_state}")
                user_email = table.item(row, 1).text()
                status_text = "solved" if new_state else "not solved"
                log_admin_action(
                    self.admin_email,
                    f"Admin marked reclamation #{rec_obj['id']} from user {user_email} as {status_text}"
                )

        table.cellChanged.connect(on_cell_changed)
        dialog.exec_()

    def load_matieres_table(self):
        """
        Load Matières into the main table for display. Uses the bearer token 
        (for both admin and friend roles).
        """
        if self.admin_role == "admin":
            s1, s2 = get_matieres("All", bearer_token=self.admin_token)
        else:
            friend_sec = getattr(self, "friend_section", None)
            if friend_sec:
                s1, s2 = get_matieres(friend_sec.lower(), bearer_token=self.admin_token)
            else:
                s1, s2 = [], []

        all_m = s1 + s2
        cols = ["ID", "Name", "Semester", "Has TP", "Weight DS", "Weight TP", "Weight Exam", "Overall Weight", "Section"]
        self.matieres_view.setColumnCount(len(cols))
        self.matieres_view.setHorizontalHeaderLabels(cols)
        self.matieres_view.setRowCount(len(all_m))

        for i, m in enumerate(all_m):
            self.matieres_view.setItem(i, 0, QTableWidgetItem(str(m.get("id", ""))))
            self.matieres_view.setItem(i, 1, QTableWidgetItem(m.get("name", "")))
            self.matieres_view.setItem(i, 2, QTableWidgetItem(str(m.get("semester", ""))))
            self.matieres_view.setItem(i, 3, QTableWidgetItem("Yes" if m.get("has_tp") else "No"))

            ds_val = str(m.get("weights", {}).get("DS", 0))
            tp_val = str(m.get("weights", {}).get("TP", 0))
            ex_val = str(m.get("weights", {}).get("Exam", 0))

            self.matieres_view.setItem(i, 4, QTableWidgetItem(ds_val))
            self.matieres_view.setItem(i, 5, QTableWidgetItem(tp_val if m.get("has_tp") else "0"))
            self.matieres_view.setItem(i, 6, QTableWidgetItem(ex_val))
            self.matieres_view.setItem(i, 7, QTableWidgetItem(str(m.get("overall_weight", ""))))
            self.matieres_view.setItem(i, 8, QTableWidgetItem(m.get("section", "")))

        self.matieres_view.resizeColumnsToContents()

    def cleanup_old_solved_reclamations(self):
        """
        Automatically remove old solved reclamations at startup.
        """
        msg = cleanup_old_reclamations(self.admin_token)
        log_action(f"Auto-removed old solved reclamations => {msg}")

    def generate_ai_reports_for_mpi(self):
        """
        Generate AI-based orientation reports for MPI students.
        This requires admin privileges and uses the llama_cpp library for LLM generation.
        don’t recommend running locally, use an API.(check google api is free for now)
        """
        if self.admin_role != "admin":
            QMessageBox.information(self, "Denied", "Only admin can do that.")
            return

        mpi_studs = get_students("mpi", bearer_token=self.admin_token)
        if not mpi_studs:
            QMessageBox.information(self, "None", "No MPI students found.")
            return

        # Load the LLM model if not already loaded
        if self.llm is None:
            self.llm = Llama(
                model_path="put the path to the model here",# here
                n_ctx=2048,
            )

        data = self.compute_student_scores_and_rank(mpi_studs)
        count = 0
        for item in data:
            if item["mg"] <= 0:
                continue
            self.generate_mpi_student_report(item)
            count += 1

        QMessageBox.information(self, "Done", f"Generated {count} AI reports.")

    def compute_student_scores_and_rank(self, mpi_students):
        """
        Compute weighted means and orientation scores for MPI students 
        to feed the AI report generator. Ranks them across potential orientations.
        """
        mat_s1, mat_s2 = get_matieres("mpi", bearer_token=self.admin_token)
        all_matieres = mat_s1 + mat_s2
        total_weight = sum(m.get("overall_weight", 0) for m in all_matieres)
        results = []

        def get_final(student, mat_name, semester):
            grades_s1 = student.get("grades_s1", {})
            grades_s2 = student.get("grades_s2", {})
            if semester == 1:
                mat_obj = grades_s1.get(mat_name, {})
            else:
                mat_obj = grades_s2.get(mat_name, {})
            return mat_obj.get("Final", 0.0)

        for stud in mpi_students:
            weighted_sum = 0.0
            for m in all_matieres:
                f_val = get_final(stud, m.get("name"), m.get("semester"))
                weighted_sum += f_val * m.get("overall_weight", 0)
            mg = (weighted_sum / total_weight) if total_weight > 0 else 0.0

            math_names = ["analyse1", "analyse2", "algebre1", "algebre2"]
            math_vals = []
            for name in math_names:
                val_s1 = stud.get("grades_s1", {}).get(name, {}).get("Final", 0)
                val_s2 = stud.get("grades_s2", {}).get(name, {}).get("Final", 0)
                math_vals.append(max(val_s1, val_s2))
            math_mean = sum(math_vals) / len(math_vals) if math_vals else 0.0

            algo1 = max(stud.get("grades_s1", {}).get("algo1", {}).get("Final", 0),
                        stud.get("grades_s2", {}).get("algo1", {}).get("Final", 0))
            algo2 = max(stud.get("grades_s1", {}).get("algo2", {}).get("Final", 0),
                        stud.get("grades_s2", {}).get("algo2", {}).get("Final", 0))
            prog1 = max(stud.get("grades_s1", {}).get("prog1", {}).get("Final", 0),
                        stud.get("grades_s2", {}).get("prog1", {}).get("Final", 0))
            prog2 = max(stud.get("grades_s1", {}).get("prog2", {}).get("Final", 0),
                        stud.get("grades_s2", {}).get("prog2", {}).get("Final", 0))
            info_mean = (2 * algo1 + 2 * algo2 + prog1 + prog2) / 6.0

            sl_value = max(stud.get("grades_s1", {}).get("sys logique", {}).get("Final", 0),
                           stud.get("grades_s2", {}).get("sys logique", {}).get("Final", 0))
            en_val = max(stud.get("grades_s1", {}).get("electronique", {}).get("Final", 0),
                         stud.get("grades_s2", {}).get("electronique", {}).get("Final", 0))
            circ_val = max(stud.get("grades_s1", {}).get("circuits", {}).get("Final", 0),
                           stud.get("grades_s2", {}).get("circuits", {}).get("Final", 0))

            gl_score = 2.0 * mg + math_mean + 2.0 * info_mean + sl_value
            rt_score = 2.0 * mg + math_mean + 1.0 * info_mean + sl_value
            iia_score = 2.0 * mg + math_mean + info_mean + sl_value + ((en_val + circ_val) / 2.0)

            results.append({
                "student": stud,
                "mg": mg,
                "math_mean": math_mean,
                "info_mean": info_mean,
                "sl_value": sl_value,
                "gl_score": gl_score,
                "rt_score": rt_score,
                "iia_score": iia_score
            })

        def rank_students_by_score(key):
            sorted_res = sorted(results, key=lambda x: x[key], reverse=True)
            rank_map = {}
            current_rank = 0
            used_position = 0
            last_score = None
            for item in sorted_res:
                used_position += 1
                score_val = item[key]
                if score_val != last_score:
                    current_rank = used_position
                rank_map[item["student"].get("id")] = current_rank
                last_score = score_val
            return rank_map

        gl_ranks = rank_students_by_score("gl_score")
        rt_ranks = rank_students_by_score("rt_score")
        iia_ranks = rank_students_by_score("iia_score")

        for item in results:
            sid = item["student"].get("id")
            item["gl_rank"] = gl_ranks.get(sid, "-")
            item["rt_rank"] = rt_ranks.get(sid, "-")
            item["iia_rank"] = iia_ranks.get(sid, "-")

        return results

    def generate_mpi_student_report(self, item):
        """
        Create a short orientation recommendation for a given MPI student 
        based on computed scores and ranks, using the loaded LLM model.
        """
        s = item["student"]
        mg_val = item["mg"]
        gl_sc = item["gl_score"]
        rt_sc = item["rt_score"]
        iia_sc = item["iia_score"]
        gl_rank = item["gl_rank"]
        rt_rank = item["rt_rank"]
        iia_rank = item["iia_rank"]

        prompt_text = (
            f"System: You are an academic advisor analyzing student orientation data. "
            f"Provide a direct response with:\n"
            f"1. Overall performance (MG={mg_val:.2f}/20)\n"
            f"2. Orientation scores: GL={gl_sc:.2f} (rank {gl_rank}), "
            f"RT={rt_sc:.2f} (rank {rt_rank}), IIA={iia_sc:.2f} (rank {iia_rank})\n"
            f"3. Clear recommendation based on rank\n"
            f"Student: {s.get('prenom','')} {s.get('nom','')}\n"
            f"Keep under 150 words. Provide only the final report."
        )

        output = self.llm(prompt_text, max_tokens=300, temperature=0.5)
        report_text = output["choices"][0]["text"].strip()
        update_ai_report(s.get("id"), report_text, bearer_token=self.admin_token)

    def logout_admin(self):
        """
        Log out from admin/friend role, removing any saved token 
        and returning to the login interface.
        """
        self.admin_token = None
        self.admin_role = None
        if os.path.exists("remember_admin.pkl"):
            os.remove("remember_admin.pkl")
        self.show_login_interface()

if __name__ == "__main__":
    # Configure Qt scaling (I do this because i use ubuntu)
    os.environ.pop('QT_DEVICE_PIXEL_RATIO', None)
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QApplication(sys.argv)
    window = AdminApp()
    window.show()
    sys.exit(app.exec_())
