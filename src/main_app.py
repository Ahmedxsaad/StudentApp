# main_app.py

import sys
import json
import os
import platform
import pickle
import re
import socket
import subprocess
import traceback
import requests
import math 
from math import ceil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# PyQt Imports
from PyQt5.QtCore import (
    Qt, QUrl, QDate, QSize, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QLocale
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QFont, QTextCharFormat, QPainterPath, QPainter, QPen,
    QColor, QBrush, QDoubleValidator,QDesktopServices
)
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QApplication, QTextEdit, QCalendarWidget, QFrame,
    QStackedWidget, QDialog, QSlider, QFileDialog, QCheckBox, QProgressBar,
    QScrollArea, QAbstractItemView, QToolButton, QGraphicsOpacityEffect,
    QTabWidget, QSizePolicy, QDesktopWidget, QHeaderView
)
from PyQt5.QtChart import (
    QChart, QChartView, QLineSeries, QValueAxis, QCategoryAxis, QPolarChart
)

# Local module imports
from api_data import (
    get_user, update_time_spent, update_password, update_profile_pic,
    get_reclamations, submit_reclamation, get_notifications,
    get_student_ai_report, log_ad_click, get_students, get_matieres,
    get_grades, update_notifications, get_targeted_ad
)
from auth import (
    register_user, verify_user, login_user, start_password_reset,
    reset_password, clear_auth_token, login_user_with_token,
    resend_verification_code, refresh_auth_token, clean_email
)
from email_utils import send_email
from utils import log_action
from translations import translations
from custom_widgets import NeedleGauge, CircularProgress, BarChartFrame, ToggleSwitch

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.abspath("."), relative_path)

# Load config
with open(resource_path('config.json'), 'r', encoding='utf-8') as f:
    config = json.load(f)



def year_progress():
    """Return how far we are in the academic year in percent."""
    start = datetime(2024, 9, 3, 8, 0)
    end = datetime(2025, 5, 28, 12, 0)
    now = datetime.now()

    total_seconds = (end - start).total_seconds()
    elapsed_seconds = (now - start).total_seconds()

    if elapsed_seconds < 0:
        elapsed_seconds = 0
    if elapsed_seconds > total_seconds:
        elapsed_seconds = total_seconds

    return round((elapsed_seconds / total_seconds) * 100, 2)

class MyCalendarWidget(QCalendarWidget):
    doubleClicked = pyqtSignal(QDate)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.selectedDate())
        event.accept()
def check_system_status():
    """Check internet connectivity."""
    try:
        sock = socket.create_connection(("www.google.com", 80), timeout=2)
        sock.close()
        return "online"
    except:
        return "offline"


class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

class MainApp(QMainWindow):
    def __init__(self):

        super().__init__()
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)  
        self.setGraphicsEffect(self.opacity_effect)

        self.theme_animation = None
        self.orientation_thresholds = {"IMI": 9.0}  
        self.setWindowTitle("Student Grades and Rankings")
        self.show_spider_mode = False
        self.chart_mode = "GL" 
        self.MODES = ["GL", "RT", "IIA", "IMI"]
        screen_rect = QDesktopWidget().availableGeometry()
        screen_width = screen_rect.width()
        screen_height = screen_rect.height()
        self.setGeometry(
            100, 100,
            min(screen_width, 1200),
            min(screen_height, 900)
        )

        self.current_user = None
        self.app_config = config
        self.theme = self.app_config.get('theme', 'dark')
        self.current_language = self.app_config.get('language', 'en')

        self.translations = translations
        self.system_status = check_system_status()

        font_size = self.app_config.get('font_size', 10)
        font = QFont("Maven Pro", font_size)
        QApplication.instance().setFont(font)

        self.main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        # Track login time
        self.login_time = None

        # StackedWidget for pages
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        # Create core pages
        self.login_page = self.create_login_page()
        self.register_page = self.create_register_page()
        self.reset_request_page = self.create_reset_request_page()
        self.reset_page = self.create_reset_page()

        # Add them
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.register_page)
        self.stack.addWidget(self.reset_request_page)
        self.stack.addWidget(self.reset_page)

        # Create the new unified verify page
        self.unified_verify_page = self.create_unified_verify_page()
        self.stack.addWidget(self.unified_verify_page)

        self.logo_label = QLabel()
        self.show()
        self.set_theme(self.theme)

        # Periodic internet check
        self.internet_timer = QTimer(self)
        self.internet_timer.timeout.connect(self.perform_periodic_internet_check)
        self.internet_timer.start(30000)

        if self.system_status == "offline":
            self.disable_all_actions()
            QMessageBox.warning(self, self.tr("No Internet"), self.tr("reset_internet"))

        # Some placeholders for purple card texts
        self.purple_name_label = QLabel()
        self.purple_rank_label = QLabel()
        self.purple_best_label = QLabel()
        self.purple_message_label = QLabel()

        # Apply translations, try auto-login, and perform periodic internet check
        self.apply_translations()
        self.try_auto_login()
        self.perform_periodic_internet_check()
    # -------------------------------------------------------------------------
    #                           FUNCTIONS AND UTILS
    # -------------------------------------------------------------------------
    def upload_logs(self):
        """ Uploads the log file to the server."""

        if not self.auth_token:
            log_action("Cannot upload logs: No auth token available")
            return

        log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
        if not os.path.exists(log_filename):
            log_action(f"No log file found => {log_filename}")
            return

        url = "put your upload URL here"#here
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }

        try:
            with open(log_filename, "rb") as f:
                files = {"file": f}
                response = requests.post(url, files=files, headers=headers, timeout=10)

            if response.ok:
                data = response.json()
                if data.get("success"):
                    log_action(f"Log file uploaded: {data.get('secure_url')}")
                else:
                    log_action("Log upload failed: " + data.get("message", "Unknown error"))
            else:
                log_action(f"Log upload failed with status: {response.status_code}")

        except Exception as exc:
            log_action(f"Error uploading logs: {exc}")

    def show_advertisement(self):
        if not self.current_user or not hasattr(self, 'all_students_data'):
            return

        # Find the current student by matching national_id.
        current_student = next(
            (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
            None
        )
        if not current_student:
            return

        # Calculate the user's rank percentage.
        user_rank_percent = self.calculate_section_top_percent(
            current_student,
            self.all_students_data,
            self.matieres_s1,
            self.matieres_s2
        )
        if user_rank_percent is None or (isinstance(user_rank_percent, float) and math.isnan(user_rank_percent)):
            user_rank_percent = 100.0

        # Get the targeted ad based on the user's rank percentage.
        ad_result = get_targeted_ad(user_rank_percent)
        if not ad_result or "id" not in ad_result:
            return

        ad = ad_result

        delay = 5  # default delay in seconds
        if hasattr(self, 'main_stack'):
            current_widget = self.main_stack.currentWidget()
            if current_widget.objectName() == "dashboard_page":
                fallback = ad.get("delay_dashboard", 15)
                delay = int(fallback) if fallback else 15
            elif current_widget.objectName() == "stats_page":
                fallback = ad.get("delay_statistics", 2)
                delay = int(fallback) if fallback else 2
        QTimer.singleShot(delay * 1000, lambda: self._display_ad(ad))

    def _display_ad(self, ad):
        # Create a dialog to display the ad.
        ad_dialog = QDialog(self)
        ad_dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        ad_dialog.setModal(True)
        dialog_width = int(self.width() * 0.9)
        dialog_height = int(self.height() * 0.9)
        ad_dialog.resize(dialog_width, dialog_height)

        layout = QVBoxLayout(ad_dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Retrieve image URL and target link.
        image_url = ad.get("image_url")
        target_link = ad.get("target_link")

        # Create a clickable label and load the ad image.
        ad_label = ClickableLabel(ad_dialog)
        pixmap = self.load_pixmap_from_url(image_url)
        if pixmap:
            scaled_pix = pixmap.scaled(ad_dialog.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ad_label.setPixmap(scaled_pix)
        ad_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(ad_label)

        def handle_label_click():
            # Log the ad click and then open the target URL.
            self.handle_ad_click(ad)
            if target_link:
                QDesktopServices.openUrl(QUrl(target_link))
        ad_label.clicked.connect(handle_label_click)

        # Create and position a close button.
        close_button = QPushButton("X", ad_dialog)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: red;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: darkred;
            }
        """)
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(ad_dialog.accept)
        close_button.move(ad_dialog.width() - close_button.width() - 10, 10)

        ad_dialog.exec_()

    def handle_ad_click(self, ad):
        user_id = self.current_user['id'] if self.current_user else None
        ad_id = ad.get("id")
        if not ad_id:
            return
        success, message = log_ad_click(ad_id, user_id)
        if not success:
            return

    def on_dashboard_page_shown(self):
        QTimer.singleShot(15000, self.show_advertisement)  # 15 sec delay for dashboard

    def on_statistics_page_shown(self):
        QTimer.singleShot(2000, self.show_advertisement)  # 2 sec delay for statistics

    def refresh_stats_chart(self):
        # Clear existing chart
        for i in reversed(range(self.stats_chart_card.layout().count())):
            item = self.stats_chart_card.layout().takeAt(i)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        user_student = None
        if self.current_user:
            user_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )

        if not user_student:
            empty_chart = QChart()
            empty_chart.setTitle("No user data.")
            chart_view = QChartView(empty_chart)
            chart_view.setStyleSheet("background: transparent;")
            self.stats_chart_card.layout().addWidget(chart_view)
            return

        section = user_student.get('section', '').lower()
        # Only allow multi-section logic if section == 'mpi'
        if section == 'mpi':
            if self.chart_mode == "GL":
                if self.show_spider_mode:
                    chart_view = self.build_spider_chart_for_mpi_spider(user_student)
                else:
                    chart_view = self.build_gl_multi_line_chart_for_mpi(user_student)
            elif self.chart_mode == "RT":
                if self.show_spider_mode:
                    chart_view = self.build_spider_chart_for_rt_spider(user_student)
                else:
                    chart_view = self.build_rt_multi_line_chart_for_mpi(user_student)
            elif self.chart_mode == "IIA":
                if self.show_spider_mode:
                    chart_view = self.build_spider_chart_for_iia_spider(user_student)
                else:
                    chart_view = self.build_iia_multi_line_chart_for_iia(user_student)
            elif self.chart_mode == "IMI":
                if self.show_spider_mode:
                    chart_view = self.build_spider_chart_for_imi_spider(user_student)
                else:
                    chart_view = self.build_imi_multi_line_chart_for_imi(user_student)
            else:
                # Fallback if needed
                chart_view = self.build_rank_line_chart()
        else:
            # If not MPI, always show single line rank chart
            chart_view = self.build_rank_line_chart()

        self.stats_chart_card.layout().addWidget(chart_view)
    
    def load_pixmap_from_url(self, url):
        """
        Downloads the image data from `url` and returns a QPixmap.
        Returns None if download fails.
        """
        try:
            resp = requests.get(url, timeout=5)  # 5s timeout
            resp.raise_for_status()             # raise exception if status != 200
            pix = QPixmap()
            pix.loadFromData(resp.content)
            return pix
        except Exception as e:
            log_action(f"Failed to load image from URL: {str(e)}")
            return None

    def upload_profile_pic(self, file_path):
        """
        Uploads a single profile picture to the Worker route /api/upload-profile-pic,"""
        if not self.auth_token:
            log_action("Cannot upload profile pic: No auth token available")
            return None
        url = "put your upload URL here"#here
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post(url, files=files, headers=headers, timeout=10)
            if response.ok:
                data = response.json()
                if data.get("success"):
                    return data.get("secure_url")
                else:
                    log_action("Profile picture upload failed: " + data.get("message", ""))
            else:
                log_action("Profile picture upload failed with status: " + str(response.status_code))
        except Exception as exc:
            log_action(f"Profile pic upload error: {exc}")

        return None

    def upload_log_file(self, file_path):
        """Uploads a single log file to the Worker route /api/upload-log-file,"""
        if not self.auth_token:
            log_action("Cannot upload log file: No auth token available")
            return None

        url = "put your upload URL here"#here
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post(url, files=files, headers=headers, timeout=10)
            if response.ok:
                data = response.json()
                if data.get("success"):
                    return data.get("secure_url")
                else:
                    log_action("Log file upload failed: " + data.get("message", ""))
            else:
                log_action("Log file upload failed with status: " + str(response.status_code))
        except Exception as exc:
            log_action(f"Log file upload error: {exc}")

        return None

    def animate_theme_change(self, new_theme: str):
        """
        Fade the entire window out, switch to 'new_theme',
        then fade back in.
        """
        if self.theme_animation and self.theme_animation.state() == QPropertyAnimation.Running:
            self.theme_animation.stop()
        fade_out = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        fade_out.setDuration(300)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InOutCubic)
        def handle_fade_out_finished():
            self.set_theme(new_theme)
            self.refresh_stats_chart()
            fade_in = QPropertyAnimation(self.opacity_effect, b"opacity", self)
            fade_in.setDuration(300)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.InOutCubic)
            fade_in.start()
            self.theme_animation = fade_in
        fade_out.finished.connect(handle_fade_out_finished)
        fade_out.start()
        self.theme_animation = fade_out

    def update_purple_card_text(self):
        """ Update the purple card text with user data."""
        current_student = None
        if self.current_user and hasattr(self, 'all_students_data'):
            current_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )
        if not current_student:
            self.purple_name_label.setText("Joe Doe")
            self.purple_rank_label.setText("No data.")
            self.purple_best_label.setText("Your best grade is ???")
            self.purple_message_label.setText("...")
            return
        user_section = current_student.get('section', '').strip().lower()
        user_mpi_avg = round(current_student.get('moy_an_year1', 0), 2)

        # Find top% in the section
        top_pct = self.calculate_section_top_percent(
            current_student,
            self.all_students_data,
            self.matieres_s1,
            self.matieres_s2
        )
        # Identify user’s best subject among the matieres
        relevant_matieres = [
            m for m in (self.matieres_s1 + self.matieres_s2)
            if m['section'].strip().lower() == user_section
        ]
        user_final_grades = []
        for mat in relevant_matieres:
            mat_id_str = str(mat['id'])
            sem = mat['semester']
            if sem == 1:
                final_val = current_student['grades_s1'].get(mat_id_str, {}).get('Final')
            else:
                final_val = current_student['grades_s2'].get(mat_id_str, {}).get('Final')
            if final_val is not None:
                user_final_grades.append((mat['name'], float(final_val)))

        if user_final_grades:
            max_final_val = max(x[1] for x in user_final_grades)
            best_subjects = [x[0] for x in user_final_grades if abs(x[1] - max_final_val) < 1e-9]
            best_subs_str = " / ".join(best_subjects)
        else:
            best_subs_str = "N/A"
        # Example message if user is below section average in certain subjects
        matieres_below = []
        section_students = [
            s for s in self.all_students_data
            if s.get('section', '').strip().lower() == user_section
        ]
        for (mat_name, final_val) in user_final_grades:
            mat_obj = next((mm for mm in relevant_matieres if mm['name'] == mat_name), None)
            if not mat_obj:
                continue
            sem = mat_obj['semester']
            mat_id_str = str(mat_obj['id'])
            # Collect final grades for that mat
            finals_for_that_mat = []
            for st in section_students:
                if sem == 1:
                    f_val = st['grades_s1'].get(mat_id_str, {}).get('Final')
                else:
                    f_val = st['grades_s2'].get(mat_id_str, {}).get('Final')
                if f_val is not None:
                    finals_for_that_mat.append(float(f_val))

            if finals_for_that_mat:
                avg_mat = sum(finals_for_that_mat) / len(finals_for_that_mat)
                if final_val < avg_mat:
                    matieres_below.append(mat_name)

        below_count = len(matieres_below)
        if below_count == 0:
            final_line = self.tr("congrats_all_above")
        elif below_count > 3:
            final_line = self.tr("need_concentrate")
        else:
            mat_below_str = " / ".join(matieres_below)
            final_line = self.tr("good_job_need_work_on").format(mat_below_str=mat_below_str)
        # Set purple card UI
        self.purple_name_label.setText(f"{current_student.get('prenom','')} {current_student.get('nom','')}")
        if top_pct is None:
            self.purple_rank_label.setText("No data to compute top%.")
        else:
            self.purple_rank_label.setText(self.tr("top_percentage").format(val=f"{top_pct}%"))

        self.purple_best_label.setText(self.tr("purple_best_grades").format(subs=best_subs_str))
        self.purple_message_label.setText(final_line)
    def calculate_section_top_percent(self, current_student, all_students_data, matieres_s1, matieres_s2):
        """
        Calculate the top percentage of a student in their section.
        """        
        if not current_student or not current_student.get('section'):
            return None
        sec_name = current_student['section'].strip().lower()
        relevant_matieres = [
            m for m in (matieres_s1 + matieres_s2)
            if m['section'].strip().lower() == sec_name
        ]
        if not relevant_matieres:
            return None
        
        same_sec_studs = [
            s for s in all_students_data
            if s.get('section', '').strip().lower() == sec_name
        ]
        if not same_sec_studs:
            return None
        
        total_w = sum(m['overall_weight'] for m in relevant_matieres)
        if total_w <= 0:
            return None

        results = []
        for stud in same_sec_studs:
            weighted_sum = 0.0
            for mat in relevant_matieres:
                mat_id_str = str(mat['id'])
                sem = mat['semester']
                w = mat['overall_weight']

                if sem == 1:
                    final_val = stud['grades_s1'].get(mat_id_str, {}).get('Final')
                else:
                    final_val = stud['grades_s2'].get(mat_id_str, {}).get('Final')

                if final_val is not None:
                    weighted_sum += float(final_val) * w

            overall_avg = weighted_sum / total_w if total_w > 0 else 0.0
            results.append((stud['id'], overall_avg))
        # Sort descending
        results.sort(key=lambda x: x[1], reverse=True)

        rank = None
        for idx, (sid, val) in enumerate(results, start=1):
            if sid == current_student['id']:
                rank = idx
                break

        if not rank:
            return None
        total_students = len(results)
        top_percentage = (rank / total_students) * 100
        return round(top_percentage, 2)
    def perform_periodic_internet_check(self):
        old_status = self.system_status
        self.system_status = check_system_status()
        if self.system_status == "offline":
            if old_status == "online":
                QMessageBox.warning(self, self.tr("No Internet"), self.tr("reset_internet"))
            self.disable_all_actions()
        else:
            if old_status == "offline":
                QMessageBox.information(self, self.tr("Online"), self.tr("connected_now"))
            self.enable_all_actions()

        self.update_footer_html()
    def disable_all_actions(self):
        fields = [
            'login_email', 'login_password', 'reg_email', 'reg_password',
            'reg_nid', 'reset_email_input', 'verify_token_input',
            'reset_token_input', 'new_password_input', 'reclamation_desc',
            'reclamation_type_box'
        ]
        for attr in fields:
            fld = getattr(self, attr, None)
            if fld is not None:
                fld.setDisabled(True)

        for page in [
            self.login_page, self.register_page, self.unified_verify_page,
            self.reset_request_page, self.reset_page
        ]:
            for w in page.findChildren(QPushButton):
                w.setDisabled(True)


    def enable_all_actions(self):
        fields = [
            'login_email', 'login_password', 'reg_email', 'reg_password',
            'reg_nid', 'reset_email_input', 'verify_token_input',
            'reset_token_input', 'new_password_input', 'reclamation_desc',
            'reclamation_type_box'
        ]
        for attr in fields:
            fld = getattr(self, attr, None)
            if fld is not None:
                fld.setDisabled(False)

        for page in [
            self.login_page, self.register_page, self.unified_verify_page,
            self.reset_request_page, self.reset_page
        ]:
            for w in page.findChildren(QPushButton):
                w.setDisabled(False)

    # -------------------------------------------------------------------------
    #                           UNIFIED VERIFICATION PAGE
    # -------------------------------------------------------------------------
    def create_unified_verify_page(self):
        page = QWidget()
        page.setObjectName("unified_verify_page")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(30)

        self.unified_title_label = QLabel("Verify Your Account")
        self.unified_title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.unified_title_label)

        self.unified_email_label = QLabel("Enter your email:")
        self.unified_email_input = QLineEdit()
        card_layout.addWidget(self.unified_email_label)
        card_layout.addWidget(self.unified_email_input)

        self.unified_code_label = QLabel("Enter Verification Code:")
        self.unified_code_input = QLineEdit()
        self.unified_code_input.setPlaceholderText("6-digit code")

        card_layout.addWidget(self.unified_code_label)
        card_layout.addWidget(self.unified_code_input)

        btn_layout = QHBoxLayout()

        self.btn_unified_verify = QPushButton("Verify")
        self.btn_unified_verify.clicked.connect(self.do_unified_verify)

        self.btn_unified_resend = QPushButton("Resend Code")
        self.btn_unified_resend.clicked.connect(self.do_unified_resend)

        self.btn_unified_back = QPushButton("Back to Login")
        self.btn_unified_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))

        btn_layout.addWidget(self.btn_unified_verify)
        btn_layout.addWidget(self.btn_unified_resend)
        btn_layout.addWidget(self.btn_unified_back)

        card_layout.addLayout(btn_layout)
        layout.addWidget(card, alignment=Qt.AlignCenter)
        return page

    def show_unified_verify_page(self, email=None):
        """
        Show the unified verification page.
        If email is provided, set it as the input and make it read-only.
        """
        if email:
            self.unified_email_input.setText(email)
            self.unified_email_input.setReadOnly(True)
            self.unified_email_label.hide()
            self.unified_email_input.hide()
            self.last_verif_email = email
        else:
            self.unified_email_input.clear()
            self.unified_email_input.setReadOnly(False)
            self.unified_email_label.show()
            self.unified_email_input.show()
            self.last_verif_email = None

        self.unified_code_input.clear()
        self.stack.setCurrentWidget(self.unified_verify_page)

    def do_unified_verify(self):
        typed_email = self.unified_email_input.text().strip()
        code = self.unified_code_input.text().strip()

        if not typed_email:
            QMessageBox.warning(self, "No Email", "Please enter or provide your email.")
            return

        success, msg = verify_user(typed_email, code)
        if success:
            QMessageBox.information(self, "Verified", msg)
            self.stack.setCurrentWidget(self.login_page)
        else:
            QMessageBox.critical(self, "Failed", msg)
    def do_unified_resend(self):
        if self.system_status == "offline":
            QMessageBox.critical(self, "No Internet", "You are not connected.")
            return
        if hasattr(self, 'last_verif_email') and self.last_verif_email:
            typed_email = self.last_verif_email
        else:
            typed_email = self.unified_email_input.text().strip()
            if not typed_email:
                QMessageBox.warning(self, "No Email", "Please enter your email first.")
                return

        # Clean the email (using the auth helper)
        typed_email = clean_email(typed_email)
        success, msg = resend_verification_code(typed_email)
        if success:
            QMessageBox.information(self, "Code Resent", msg)
            self.last_verif_email = typed_email
        else:
            QMessageBox.critical(self, "Error", msg)

    # -------------------------------------------------------------------------
    #                           AUTO-LOGIN / CORE
    # -------------------------------------------------------------------------
    def try_auto_login(self):
        """
        Try to auto-login using the stored auth token.
        If successful, set the current user and login time.
        """
        if not os.path.exists("remember_user.pkl"):
            return  # No remembered token => do nothing
        try:
            with open("remember_user.pkl", "rb") as f:
                data = pickle.load(f)
                stored_token = data.get("auth_token", "")
                stored_refresh = data.get("refresh_token", "")
                remembered_user_id = data.get("id", "")
        except Exception:
            # If file is corrupted, remove it
            if os.path.exists("remember_user.pkl"):
                os.remove("remember_user.pkl")
            return
        if not stored_token:
            # No auth_token => can't auto-login
            if os.path.exists("remember_user.pkl"):
                os.remove("remember_user.pkl")
            return
        success, user_or_msg = login_user_with_token(stored_token)
        if success:
            self.auth_token = stored_token  
            if not user_or_msg.get('section'):
                user_db = get_user(user_or_msg['id'], bearer_token=self.auth_token)
                if user_db:
                    user_or_msg['section'] = user_db.get("section", "").lower().strip()
            self.current_user = {
                'id':       user_or_msg['id'],
                'email':    user_or_msg['email'],
                'verified': user_or_msg['verified'],
                'national_id': user_or_msg['national_id'],
                'section': user_or_msg.get('section', "").lower().strip()
            }
            self.login_time = datetime.now()
            self.post_login_setup()
            return
        else:
            if stored_refresh and remembered_user_id:
                succ, new_auth = refresh_auth_token(remembered_user_id, stored_refresh)
                if succ and new_auth:
                    data["auth_token"] = new_auth
                    with open("remember_user.pkl", "wb") as f:
                        pickle.dump(data, f)
                    success2, user_or_msg2 = login_user_with_token(new_auth)
                    if success2:
                        self.auth_token = new_auth  
                        if not user_or_msg2.get('section'):
                            user_db2 = get_user(user_or_msg2['id'], bearer_token=self.auth_token)
                            if user_db2:
                                user_or_msg2['section'] = user_db2.get("section", "").lower().strip()
                        self.current_user = {
                            'id':       user_or_msg2['id'],
                            'email':    user_or_msg2['email'],
                            'verified': user_or_msg2['verified'],
                            'national_id': user_or_msg2['national_id'],
                            'section': user_or_msg2.get('section', "").lower().strip()
                        }
                        self.login_time = datetime.now()
                        self.post_login_setup()
                        return
                    else:
                        if os.path.exists("remember_user.pkl"):
                            os.remove("remember_user.pkl")
                        return
                else:
                    if os.path.exists("remember_user.pkl"):
                        os.remove("remember_user.pkl")
            else:
                if os.path.exists("remember_user.pkl"):
                    os.remove("remember_user.pkl")
    # -------------------------------------------------------------------------
    #                           LOGIN PAGE
    # -------------------------------------------------------------------------
    def create_login_page(self):
        page = QWidget()
        page.setObjectName("login_page")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        self.login_card = QFrame()
        self.login_card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(self.login_card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(30)

        self.login_title_label = QLabel()
        self.login_subtitle_label = QLabel()
        self.login_subtitle_label.setAlignment(Qt.AlignCenter)

        form_layout = QFormLayout()
        form_layout.setSpacing(20)

        self.login_email = QLineEdit()
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)

        self.show_login_pass_btn = QToolButton(self.login_password)
        self.show_login_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
        )
        self.show_login_pass_btn.setCheckable(True)
        self.show_login_pass_btn.hide()
        self.show_login_pass_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 0 5px;
            }
        """)
        self.login_password.setStyleSheet("padding-right: 20px;")
        self.show_login_pass_btn.setCursor(Qt.PointingHandCursor)

        def toggle_login_pass_visibility():
            if self.show_login_pass_btn.isChecked():
                self.login_password.setEchoMode(QLineEdit.Normal)
                self.show_login_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.login_password.setEchoMode(QLineEdit.Password)
                self.show_login_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        def show_hide_login_eye(text):
            self.show_login_pass_btn.setVisible(bool(text))

        self.show_login_pass_btn.clicked.connect(toggle_login_pass_visibility)
        self.login_password.textChanged.connect(show_hide_login_eye)

        def resize_login_pass_event(event):
            buttonSize = self.show_login_pass_btn.sizeHint()
            self.show_login_pass_btn.move(
                self.login_password.width() - buttonSize.width() - 5,
                (self.login_password.height() - buttonSize.height()) // 2
            )
        self.login_password.resizeEvent = resize_login_pass_event

        self.login_email_label = QLabel()
        self.login_password_label = QLabel()

        form_layout.addRow(self.login_email_label, self.login_email)
        form_layout.addRow(self.login_password_label, self.login_password)

        self.remember_me_check = QCheckBox("Remember me")

        self.btn_login = QPushButton()
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self.do_login)

        self.btn_goto_register = QPushButton()
        self.btn_goto_register.setCursor(Qt.PointingHandCursor)
        self.btn_goto_register.clicked.connect(lambda: self.stack.setCurrentWidget(self.register_page))

        self.btn_forgot = QPushButton()
        self.btn_forgot.setCursor(Qt.PointingHandCursor)
        self.btn_forgot.clicked.connect(lambda: self.stack.setCurrentWidget(self.reset_request_page))

        card_layout.addWidget(self.login_title_label)
        card_layout.addWidget(self.login_subtitle_label)
        card_layout.addLayout(form_layout)
        card_layout.addWidget(self.remember_me_check, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_login, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_goto_register, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_forgot, alignment=Qt.AlignCenter)

        self.btn_not_verified = QPushButton("Not Verified Yet?")
        self.btn_not_verified.setCursor(Qt.PointingHandCursor)
        self.btn_not_verified.clicked.connect(lambda: self.show_unified_verify_page())
        card_layout.addWidget(self.btn_not_verified, alignment=Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(self.login_card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def do_login(self):
        """
        Perform the login action.
        Validate the email and password fields.
        If valid, call the login_user function.
        """
        if self.system_status == "offline":
            QMessageBox.critical(self, self.tr("No Internet"), self.tr("reset_internet"))
            return
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()

        success, user_info, top_auth_token, refresh_token = login_user(email, password)
        if success:
            self.auth_token = top_auth_token
            if not user_info.get('section'):
                user_db = get_user(user_info['id'], bearer_token=self.auth_token)
                if user_db:
                    user_info['section'] = user_db.get("section", "").lower().strip()

            self.current_user = {
                'id':       user_info['id'],
                'email':    user_info['email'],
                'verified': user_info['verified'],
                'national_id': user_info['national_id'],
                'section': user_info.get('section', "").lower().strip()
            }
            log_action(f"User {email} logged in successfully.")
            self.login_time = datetime.now()
            if self.remember_me_check.isChecked():
                with open("remember_user.pkl", "wb") as f:
                    pickle.dump({
                        "auth_token":    top_auth_token,
                        "refresh_token": refresh_token,
                        "id":            user_info["id"]
                    }, f)

            self.post_login_setup()
        else:
            if user_info == "unverified":
                QMessageBox.information(
                    self,
                    "Not Verified",
                    "Your account is not verified yet.\n"
                    "A new code was just sent to your email.\n"
                    "Enter it on the verify page."
                )
                self.show_unified_verify_page(email)
            else:
                QMessageBox.critical(self, self.tr("Login Failed"), str(user_info))

    # -------------------------------------------------------------------------
    #                           REGISTER PAGE
    # -------------------------------------------------------------------------
    def create_register_page(self):
        """
        Create the registration page with input fields for email, password, and NID.
        """
        page = QWidget()
        page.setObjectName("register_page")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        self.register_card = QFrame()
        self.register_card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(self.register_card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(30)

        self.register_title = QLabel()
        self.register_title.setAlignment(Qt.AlignCenter)

        form_layout = QFormLayout()
        form_layout.setSpacing(20)

        self.reg_email = QLineEdit()
        self.reg_password = QLineEdit()
        self.reg_password.setEchoMode(QLineEdit.Password)

        self.show_reg_pass_btn = QToolButton(self.reg_password)
        self.show_reg_pass_btn.setIcon(
            QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
        )
        self.show_reg_pass_btn.setCheckable(True)
        self.show_reg_pass_btn.hide()
        self.show_reg_pass_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 0 5px;
            }
        """)
        self.reg_password.setStyleSheet("padding-right: 20px;")
        self.show_reg_pass_btn.setCursor(Qt.PointingHandCursor)

        def toggle_reg_pass_visibility():
            if self.show_reg_pass_btn.isChecked():
                self.reg_password.setEchoMode(QLineEdit.Normal)
                self.show_reg_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.reg_password.setEchoMode(QLineEdit.Password)
                self.show_reg_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        def show_hide_reg_eye(text):
            self.show_reg_pass_btn.setVisible(bool(text))

        self.show_reg_pass_btn.clicked.connect(toggle_reg_pass_visibility)
        self.reg_password.textChanged.connect(show_hide_reg_eye)

        def resize_reg_pass_event(event):
            buttonSize = self.show_reg_pass_btn.sizeHint()
            self.show_reg_pass_btn.move(
                self.reg_password.width() - buttonSize.width() - 5,
                (self.reg_password.height() - buttonSize.height()) // 2
            )
        self.reg_password.resizeEvent = resize_reg_pass_event

        self.reg_nid = QLineEdit()

        self.univ_email_label = QLabel()
        self.password_label_reg = QLabel()
        self.nid_label = QLabel()

        form_layout.addRow(self.univ_email_label, self.reg_email)
        form_layout.addRow(self.password_label_reg, self.reg_password)
        form_layout.addRow(self.nid_label, self.reg_nid)

        self.password_strength_bar = QProgressBar()
        self.password_strength_bar.setRange(0, 100)
        self.reg_password.textChanged.connect(self.update_password_strength)
        form_layout.addRow("Password Strength:", self.password_strength_bar)

        self.btn_register = QPushButton()
        self.btn_register.setCursor(Qt.PointingHandCursor)
        self.btn_register.clicked.connect(self.do_register_user)

        self.btn_back_login = QPushButton()
        self.btn_back_login.setCursor(Qt.PointingHandCursor)
        self.btn_back_login.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))

        card_layout.addWidget(self.register_title)
        card_layout.addLayout(form_layout)
        card_layout.addWidget(self.btn_register, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_back_login, alignment=Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(self.register_card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def password_strength(self, pwd):
        score = 0
        length = len(pwd)
        if length > 5:
            score += 20
        if length > 8:
            score += 20
        if re.search("[A-Z]", pwd):
            score += 20
        if re.search("[0-9]", pwd):
            score += 20
        if re.search("[^a-zA-Z0-9]", pwd):
            score += 20
        return score

    def update_password_strength(self):
        pwd = self.reg_password.text()
        strength = self.password_strength(pwd)
        self.password_strength_bar.setValue(strength)

    def do_register_user(self):
        if self.system_status == "offline":
            QMessageBox.critical(self, self.tr("No Internet"), self.tr("reset_internet"))
            return
        email = self.reg_email.text().strip()
        password = self.reg_password.text().strip()
        nid = self.reg_nid.text().strip()

        if not (email and password and nid):
            QMessageBox.critical(self, self.tr("Error"), "Please fill all fields.")
            return

        succ, msg = register_user(email, password, nid, role='student')
        if succ:
            QMessageBox.information(self, self.tr("Registered"), msg)
            self.show_unified_verify_page(email)
        else:
            QMessageBox.critical(self, self.tr("Error"), msg)

    # -------------------------------------------------------------------------
    #                           RESET REQUEST PAGE
    # -------------------------------------------------------------------------
    def create_reset_request_page(self):
        """
        Create the reset password request page with input fields for email.
        """
        page = QWidget()
        page.setObjectName("reset_request_page")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        self.reset_request_card = QFrame()
        self.reset_request_card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(self.reset_request_card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(30)

        self.reset_title_label = QLabel()
        self.reset_title_label.setAlignment(Qt.AlignCenter)

        self.reset_email_input = QLineEdit()

        self.btn_send_token = QPushButton()
        self.btn_send_token.setCursor(Qt.PointingHandCursor)
        self.btn_send_token.clicked.connect(self.do_start_password_reset)

        self.btn_back_to_login_reset = QPushButton()
        self.btn_back_to_login_reset.setCursor(Qt.PointingHandCursor)
        self.btn_back_to_login_reset.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))

        self.btn_goto_reset_page = QPushButton()
        self.btn_goto_reset_page.setCursor(Qt.PointingHandCursor)
        self.btn_goto_reset_page.clicked.connect(lambda: self.stack.setCurrentWidget(self.reset_page))

        card_layout.addWidget(self.reset_title_label)
        card_layout.addWidget(self.reset_email_input)
        card_layout.addWidget(self.btn_send_token, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_goto_reset_page, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_back_to_login_reset, alignment=Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(self.reset_request_card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def do_start_password_reset(self):
        if self.system_status == "offline":
            QMessageBox.critical(self, self.tr("No Internet"), self.tr("reset_internet"))
            return

        f_email = self.reset_email_input.text().strip()
        if f_email:
            succ, msg = start_password_reset(f_email)
            if succ:
                QMessageBox.information(self, self.tr("Check Email"), msg)
            else:
                QMessageBox.critical(self, self.tr("Error"), msg)
        else:
            QMessageBox.information(self, self.tr("Canceled"), "No email entered.")

    # -------------------------------------------------------------------------
    #                           RESET PAGE
    # -------------------------------------------------------------------------
    def create_reset_page(self):
        """
        Create the reset password page with input fields for token and new password.
        """
        page = QWidget()
        page.setObjectName("reset_page")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        self.reset_card = QFrame()
        self.reset_card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(self.reset_card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(30)

        self.reset_page_title = QLabel()
        self.reset_page_title.setAlignment(Qt.AlignCenter)

        form_layout = QFormLayout()
        self.reset_token_input = QLineEdit()
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)

        self.token_label_w = QLabel()
        self.new_password_label_w = QLabel()

        form_layout.addRow(self.token_label_w, self.reset_token_input)
        form_layout.addRow(self.new_password_label_w, self.new_password_input)

        self.btn_reset_pass = QPushButton()
        self.btn_reset_pass.setCursor(Qt.PointingHandCursor)
        self.btn_reset_pass.clicked.connect(self.do_reset_password)

        self.btn_back_reset = QPushButton()
        self.btn_back_reset.setCursor(Qt.PointingHandCursor)
        self.btn_back_reset.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))

        card_layout.addWidget(self.reset_page_title)
        card_layout.addLayout(form_layout)
        card_layout.addWidget(self.btn_reset_pass, alignment=Qt.AlignCenter)
        card_layout.addWidget(self.btn_back_reset, alignment=Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(self.reset_card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def do_reset_password(self):
        if self.system_status == "offline":
            QMessageBox.critical(self, self.tr("No Internet"), self.tr("reset_internet"))
            return

        token = self.reset_token_input.text().strip()
        new_pass = self.new_password_input.text().strip()

        if not token or not new_pass:
            QMessageBox.critical(self, self.tr("Error"), "Please enter token and new password.")
            return

        succ, msg = reset_password(token, new_pass)
        if succ:
            QMessageBox.information(self, self.tr("Success"), msg)
            self.stack.setCurrentWidget(self.login_page)
        else:
            QMessageBox.critical(self, self.tr("Error"), msg)

    # -------------------------------------------------------------------------
    #                          MAIN PAGE & POST-LOGIN
    # -------------------------------------------------------------------------

    def post_login_setup(self):
        """
        Perform the setup after a successful login.
        This includes loading student data, grades, and matieres.
        """
        section = self.current_user.get('section', None)
        self.all_students_data = get_students(section=section, bearer_token=self.auth_token)
        if not self.all_students_data:
            QMessageBox.warning(self, "Error", "No students found (or API error).")
            return
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                futures_map = {
                    executor.submit(get_grades, student['id'], bearer_token=self.auth_token): student
                    for student in self.all_students_data
                }
                for fut in as_completed(futures_map):
                    st = futures_map[fut]
                    try:
                        grades_data = fut.result()
                        st['grades_s1'] = grades_data.get("grades_s1", {})
                        st['grades_s2'] = grades_data.get("grades_s2", {})
                    except Exception as e:
                        traceback.print_exc()
                        st['grades_s1'] = {}
                        st['grades_s2'] = {}

        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load student grades concurrently:\n{exc}")
            return
        found_student = next(
            (s for s in self.all_students_data if s['id'] == self.current_user['national_id']), 
            None
        )
        if not found_student:
            self.students_data = []
            QMessageBox.warning(
                self, self.tr("Not Found"),
                "No matching student found for your Student ID."
            )
        else:
            self.students_data = [found_student]

        mat_s1, mat_s2 = get_matieres(section_filter=section, bearer_token=self.auth_token)
        self.matieres_s1, self.matieres_s2 = mat_s1, mat_s2

        self.main_page = self.create_main_page()
        self.stack.addWidget(self.main_page)
        self.stack.setCurrentWidget(self.main_page)

        self.set_theme(self.theme)
        self.apply_translations()
        self.update_footer_html()
        self.populate_matiere_table()
        self.populate_dashboard_chart()
        QTimer.singleShot(2000, self.show_advertisement)



    def post_login_setup_continue(self):
        """
        Continue the setup after a successful login."""
        found_student = next(
            (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
            None
        )
        if not found_student:
            self.students_data = []
            QMessageBox.warning(self, self.tr("Not Found"), "No matching student found for your Student ID.")
        else:
            self.students_data = [found_student]
        
        # Load matieres 
        section_filter = found_student['section'] if found_student else None
        self.matieres_s1, self.matieres_s2 = get_matieres(section_filter, bearer_token=self.auth_token)

        self.main_page = self.create_main_page()
        self.stack.addWidget(self.main_page)
        self.stack.setCurrentWidget(self.main_page)
        self.set_theme(self.theme)
        self.apply_translations()
        self.update_footer_html()
        self.populate_matiere_table()
        self.populate_dashboard_chart()

        # Schedule the advertisement after a 2-second delay
        QTimer.singleShot(2000, self.show_advertisement)

    # -------------------------------------------------------------------------
    #                           MAIN PAGE CREATION
    # -------------------------------------------------------------------------
    def create_main_page(self):
        page = QWidget()
        page.setObjectName("main_page")
        main_v_layout = QVBoxLayout(page)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(20, 20, 20, 20)
        top_bar.setSpacing(10)

        self.update_logo()
        self.logo_label.setStyleSheet("background: none;margin:0;padding:0;border-radius:20%;")
        top_bar.addWidget(self.logo_label, alignment=Qt.AlignVCenter)

        self.welcome_label = QLabel()
        self.welcome_label.setFont(QFont("Maven Pro", 16, QFont.Bold))
        self.welcome_label.setStyleSheet("background: none;")
        top_bar.addWidget(self.welcome_label, alignment=Qt.AlignVCenter | Qt.AlignLeft)

        top_bar.addStretch()

        self.btn_toggle_theme_top = QPushButton()
        self.btn_toggle_theme_top.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_theme_top.setFlat(True)
        self.btn_toggle_theme_top.setStyleSheet("background: none;")
        self.btn_toggle_theme_top.clicked.connect(self.toggle_theme)

        self.lang_combo = QComboBox()
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        self.lang_combo.setStyleSheet("""
            QComboBox {
                color: black;
                background-color: white;
                padding: 5px 5px 5px 10px;
                min-width: 100px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView {
                color: black;
                background-color: white;
            }
        """)
        self.lang_combo.setIconSize(QSize(24, 24))
        self.lang_combo.clear()
        self.lang_combo.addItem("English")
        self.lang_combo.setItemIcon(0, QIcon(resource_path("resources/english.svg")))
        self.lang_combo.addItem("Français")
        self.lang_combo.setItemIcon(1, QIcon(resource_path("resources/french.svg")))
        self.lang_combo.addItem("العربية")
        self.lang_combo.setItemIcon(2, QIcon(resource_path("resources/arabic.svg")))

        lang_index = {"en": 0, "fr": 1, "ar": 2}.get(self.current_language, 0)
        self.lang_combo.setCurrentIndex(lang_index)
        self.lang_combo.currentIndexChanged.connect(self.change_language)

        top_bar.addWidget(self.btn_toggle_theme_top)
        top_bar.addWidget(self.lang_combo)

        top_bar_widget = QWidget()
        top_bar_widget.setLayout(top_bar)
        main_v_layout.addWidget(top_bar_widget)

        top_separator = QFrame()
        top_separator.setFrameShape(QFrame.HLine)
        top_separator.setFrameShadow(QFrame.Sunken)
        main_v_layout.addWidget(top_separator)

        h_main = QHBoxLayout()
        h_main.setContentsMargins(0, 0, 0, 0)
        h_main.setSpacing(0)

        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("LeftNavigation")
        self.nav_frame.setFixedWidth(60)
        nav_layout = QVBoxLayout(self.nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(10)

        main_nav_frame = QFrame()
        main_nav_frame.setObjectName("MainNavFrame")
        main_nav_layout = QVBoxLayout(main_nav_frame)
        main_nav_layout.setContentsMargins(0, 0, 0, 0)
        main_nav_layout.setSpacing(10)

        def create_icon_button_frame(btn_tooltip, click_func):
            fr = QFrame()
            fr.setObjectName("NavButtonFrame")
            fl = QVBoxLayout(fr)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(0)
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.setFlat(True)
            b.setToolTip(btn_tooltip)
            b.clicked.connect(click_func)
            fl.addWidget(b, alignment=Qt.AlignCenter)
            return fr, b

        self.home_frame, self.btn_home = create_icon_button_frame("Dashboard", lambda: self.main_stack.setCurrentWidget(self.dashboard_page))
        self.matiere_frame, self.btn_matiere = create_icon_button_frame("Matières", lambda: self.main_stack.setCurrentWidget(self.matiere_page))
        self.stats_frame, self.btn_stats = create_icon_button_frame("Statistics",  lambda: self.main_stack.setCurrentWidget(self.stats_page))
        self.reclam_frame, self.btn_reclam = create_icon_button_frame("Reclamations", lambda: self.main_stack.setCurrentWidget(self.reclamation_page))
        self.settings_frame, self.btn_settings = create_icon_button_frame("Settings", lambda: self.main_stack.setCurrentWidget(self.settings_page))
        self.notif_frame, self.btn_notif = create_icon_button_frame("Notifications", self.show_notifications_page)

        main_nav_layout.addWidget(self.home_frame, alignment=Qt.AlignCenter)
        main_nav_layout.addWidget(self.matiere_frame, alignment=Qt.AlignCenter)
        main_nav_layout.addWidget(self.stats_frame, alignment=Qt.AlignCenter)
        main_nav_layout.addWidget(self.reclam_frame, alignment=Qt.AlignCenter)
        main_nav_layout.addWidget(self.settings_frame, alignment=Qt.AlignCenter)
        main_nav_layout.addWidget(self.notif_frame, alignment=Qt.AlignCenter)
        main_nav_layout.addStretch()

        nav_layout.addWidget(main_nav_frame)

        profile_buttons_frame = QFrame()
        profile_buttons_frame.setObjectName("ProfileButtonsFrame")
        pbf_layout = QVBoxLayout(profile_buttons_frame)
        pbf_layout.setContentsMargins(0, 0, 0, 0)
        pbf_layout.setSpacing(10)

        self.btn_logout = QPushButton()
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.setFlat(True)

        self.btn_profile = QPushButton()
        self.btn_profile.setCursor(Qt.PointingHandCursor)
        self.btn_profile.setFlat(True)

        pbf_layout.addWidget(self.btn_logout, alignment=Qt.AlignCenter)
        pbf_layout.addWidget(self.btn_profile, alignment=Qt.AlignCenter)

        self.btn_profile.clicked.connect(lambda: self.main_stack.setCurrentWidget(self.profile_page))
        self.btn_logout.clicked.connect(self.logout_user)
        nav_layout.addStretch()

        nav_layout.addWidget(profile_buttons_frame, alignment=Qt.AlignCenter)

        h_main.addWidget(self.nav_frame)

        nav_separator = QFrame()
        nav_separator.setFrameShape(QFrame.VLine)
        nav_separator.setFrameShadow(QFrame.Sunken)
        h_main.addWidget(nav_separator)

        self.main_stack = QStackedWidget()
        h_main.addWidget(self.main_stack)
        main_v_layout.addLayout(h_main)

        footer_frame = QFrame()
        footer_frame.setObjectName("FooterFrame")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(20, 5, 20, 5)
        footer_layout.setSpacing(10)

        self.status_label = QLabel()
        footer_layout.addWidget(self.status_label, alignment=Qt.AlignRight)
        main_v_layout.addWidget(footer_frame)

        self.dashboard_page = QWidget()
        self.dashboard_page.setObjectName("dashboard_page")
        self.matiere_page = QWidget()
        self.matiere_page.setObjectName("matiere_page")
        self.stats_page = QWidget()
        self.stats_page.setObjectName("stats_page")
        self.reclamation_page = QWidget()
        self.reclamation_page.setObjectName("reclamation_page")
        self.settings_page = QWidget()
        self.settings_page.setObjectName("settings_page")
        self.profile_page = QWidget()
        self.profile_page.setObjectName("profile_page")
        self.notif_page = QWidget()
        self.notif_page.setObjectName("notif_page")

        self.main_stack.addWidget(self.dashboard_page)
        self.main_stack.addWidget(self.matiere_page)
        self.main_stack.addWidget(self.stats_page)
        self.main_stack.addWidget(self.reclamation_page)
        self.main_stack.addWidget(self.settings_page)
        self.main_stack.addWidget(self.profile_page)
        self.main_stack.addWidget(self.notif_page)

        # Set up each page
        self.setup_dashboard_page()
        self.setup_matiere_page()
        self.setup_stats_page() 
        self.setup_reclamation_page()
        self.setup_settings_page()
        self.setup_profile_page()
        self.setup_notifications_page()

        self.main_stack.currentChanged.connect(self.update_active_icons)

        return page
    # -------------------------------------------------------------------------
    #                           DASHBOARD PAGE
    # -------------------------------------------------------------------------

    def setup_dashboard_page(self):
        self.dashboard_layout = QHBoxLayout(self.dashboard_page)
        self.dashboard_layout.setContentsMargins(20, 20, 20, 20)
        self.dashboard_layout.setSpacing(20)

        self.left_col = QVBoxLayout()
        self.left_col.setSpacing(20)

        # -- Grey Card --
        self.section_card = QFrame()
        self.section_card.setObjectName("CardWidget")
        self.section_card.setStyleSheet(
            "QFrame#CardWidget { background-color: #464646; } "
            "QFrame#CardWidget QLabel { color: #ffffff; }"
        )
        self.section_layout = QVBoxLayout(self.section_card)
        self.section_layout.setSpacing(2)
        self.section_layout.setContentsMargins(20, 20, 20, 20)
        self.section_layout.setSpacing(10)

        self.section_label = QLabel()
        self.moy_section_label = QLabel()
        self.acceptance_label = QLabel()

        self.section_layout.addWidget(self.section_label)
        self.section_layout.addWidget(self.moy_section_label)
        self.section_layout.addWidget(self.acceptance_label)
        self.left_col.addWidget(self.section_card, 3)

        # -- School Card (Year Progress) --
        self.school_card = QFrame()
        self.school_card.setObjectName("CardWidget")
        self.school_card.setStyleSheet("QFrame#CardWidget { background-color: #455A64; }")
        self.sc_layout = QHBoxLayout(self.school_card)
        self.sc_layout.setContentsMargins(20, 20, 20, 20)
        self.sc_layout.setSpacing(20)

        prog_value = year_progress()
        self.sy_label = QLabel()
        self.sy_label.setProperty("CardText", True)
        self.sc_layout.addWidget(self.sy_label, alignment=Qt.AlignLeft | Qt.AlignVCenter)

        self.cprog = CircularProgress(size=95, value=prog_value, thickness=18, pg_color="#00bcd4")
        self.sc_layout.addWidget(self.cprog, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self.left_col.addWidget(self.school_card, 2)

        # -- Chart Card --
        self.chart_card = QFrame()
        self.chart_card.setObjectName("CardWidget")
        self.chart_card.setStyleSheet("QFrame#CardWidget { background-color: #00897B; }")
        self.ch_layout = QVBoxLayout(self.chart_card)
        self.ch_layout.setContentsMargins(20, 20, 20, 20)
        self.ch_layout.setSpacing(10)

        self.ch_lbl = QLabel()
        self.ch_lbl.setProperty("CardText", True)
        self.chart_sim = BarChartFrame()
        self.ch_layout.addWidget(self.ch_lbl)
        self.ch_layout.addWidget(self.chart_sim)
        self.left_col.addWidget(self.chart_card, 3)

        self.dashboard_layout.addLayout(self.left_col)

        # -- Right Column (Purple Card + Calendar) --
        self.right_col = QVBoxLayout()
        self.right_col.setSpacing(20)

        # Purple Card with user info
        self.purple_card = QFrame()
        self.purple_card.setObjectName("PurpleCard")
        self.purple_card.setStyleSheet("QFrame#PurpleCard { background-color: #701c9c; }")
        self.p_layout = QVBoxLayout(self.purple_card)
        self.p_layout.setContentsMargins(20, 20, 20, 20)
        self.p_layout.setSpacing(10)

        self.purple_name_label.setFont(QFont("Maven Pro", 18, QFont.Bold))
        self.purple_name_label.setStyleSheet("background:none; color:#ffffff;")
        self.purple_name_label.setAlignment(Qt.AlignCenter)

        self.purple_rank_label.setStyleSheet("background:none; color:#ffffff;")
        self.purple_rank_label.setAlignment(Qt.AlignCenter)

        self.purple_best_label.setStyleSheet("background:none; color:#ffffff;")
        self.purple_best_label.setAlignment(Qt.AlignCenter)

        self.purple_message_label.setStyleSheet("background:none; color:#ffffff;")
        self.purple_message_label.setAlignment(Qt.AlignCenter)

        self.p_layout.addWidget(self.purple_name_label)
        self.p_layout.addWidget(self.purple_rank_label)
        self.p_layout.addWidget(self.purple_best_label)
        self.p_layout.addWidget(self.purple_message_label)

        self.right_col.addWidget(self.purple_card)

        self.purple_card.setFixedHeight(
            self.section_card.sizeHint().height()
            + self.school_card.sizeHint().height()
            + 50
        )
        self.update_purple_card_text()

        self.calendar_card = QFrame()
        self.calendar_card.setObjectName("CardWidget")
        self.cal_layout = QVBoxLayout(self.calendar_card)
        self.cal_layout.setContentsMargins(20, 20, 20, 20)
        self.cal_layout.setSpacing(10)
        self.calendar_title = QLabel()
        # Custom calendar widget
        self.calendar = MyCalendarWidget()
        self.calendar.setNavigationBarVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        # DS period: March 15–22, 2025 – purple
        ds_format = QTextCharFormat()
        ds_format.setBackground(QBrush(QColor("#DDDDDD")))
        for day in range(15, 23):  # days 15 through 22
            self.calendar.setDateTextFormat(QDate(2025, 3, day), ds_format)

        # Spring holiday: March 23, 2025 – green
        holiday_format = QTextCharFormat()
        holiday_format.setBackground(QBrush(QColor("#C5E1A5")))
        self.calendar.setDateTextFormat(QDate(2025, 3, 23), holiday_format)

        # Exam period: May 22–31, 2025 – orange
        exam_format = QTextCharFormat()
        exam_format.setBackground(QBrush(QColor("#FFAB91")))
        for day in range(22, 32):  # days 22 through 31
            self.calendar.setDateTextFormat(QDate(2025, 5, day), exam_format)

        self.calendar.clicked.connect(self.on_calendar_activated)

        self.cal_layout.addWidget(self.calendar_title)
        self.cal_layout.addWidget(self.calendar)
        self.right_col.addWidget(self.calendar_card)

        self.dashboard_layout.addLayout(self.right_col)
    def on_calendar_activated(self, date):
    # Only dates in 2025 
        if date.year() == 2025:
            if date.month() == 3:
                if 15 <= date.day() <= 22:
                    QMessageBox.information(
                        self,
                        "DS Period",
                        f"{date.toString(Qt.DefaultLocaleLongDate)} is part of the DS period."
                    )
                elif date.day() == 23:
                    QMessageBox.information(
                        self,
                        "Spring Holidays",
                        f"{date.toString(Qt.DefaultLocaleLongDate)} is the first day of the spring holidays."
                    )
            elif date.month() == 5 and 22 <= date.day() <= 31:
                QMessageBox.information(
                    self,
                    "Exam Period",
                    f"{date.toString(Qt.DefaultLocaleLongDate)} is part of the exam period."
                )

    def populate_dashboard_chart(self):
        """
        Populate the dashboard chart with the user's and section's averages.
        """
        if not self.current_user:
            return

        user_student = next(
            (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
            None
        )
        if not user_student or not user_student.get('section'):
            self.chart_sim.bars = []
            self.chart_sim.update()
            self.ch_lbl.setText("No data for your section.")
            return

        user_ds_list = []
        section_ds_list = []
        user_exam_list = []
        section_exam_list = []

        user_weighted_sum = 0.0
        section_weighted_sum = 0.0
        total_weights = 0.0

        # Filter matieres by the user's section
        section_matieres = [m for m in (self.matieres_s1 + self.matieres_s2)
                            if m['section'].strip().lower() == user_student['section'].strip().lower()]
        students_in_section = [
            st for st in self.all_students_data
            if st.get('section', '').strip().lower() == user_student['section'].strip().lower()
        ]

        for mat in section_matieres:
            mat_id_str = str(mat['id'])
            sem = mat['semester']
            w = mat['overall_weight']
            has_tp = mat['has_tp']

            # ---------- For the current user ----------
            if sem == 1:
                ds_val = user_student['grades_s1'].get(mat_id_str, {}).get('DS')
                exam_val = user_student['grades_s1'].get(mat_id_str, {}).get('Exam')
                final_val = user_student['grades_s1'].get(mat_id_str, {}).get('Final')
            else:
                ds_val = user_student['grades_s2'].get(mat_id_str, {}).get('DS')
                exam_val = user_student['grades_s2'].get(mat_id_str, {}).get('Exam')
                final_val = user_student['grades_s2'].get(mat_id_str, {}).get('Final')

            if ds_val is not None:
                user_ds_list.append(float(ds_val))
            if exam_val is not None:
                user_exam_list.append(float(exam_val))
            if final_val is not None:
                user_weighted_sum += float(final_val) * w

            # ---------- For the entire section ----------
            ds_vals_sec = []
            exam_vals_sec = []
            final_vals_sec = []

            for st in students_in_section:
                if sem == 1:
                    ds_s = st['grades_s1'].get(mat_id_str, {}).get('DS')
                    exam_s = st['grades_s1'].get(mat_id_str, {}).get('Exam')
                    final_s = st['grades_s1'].get(mat_id_str, {}).get('Final')
                else:
                    ds_s = st['grades_s2'].get(mat_id_str, {}).get('DS')
                    exam_s = st['grades_s2'].get(mat_id_str, {}).get('Exam')
                    final_s = st['grades_s2'].get(mat_id_str, {}).get('Final')

                if ds_s is not None:
                    ds_vals_sec.append(float(ds_s))
                if exam_s is not None:
                    exam_vals_sec.append(float(exam_s))
                if final_s is not None:
                    final_vals_sec.append(float(final_s))

            if ds_vals_sec:
                section_ds_list.append(sum(ds_vals_sec) / len(ds_vals_sec))
            if exam_vals_sec:
                section_exam_list.append(sum(exam_vals_sec) / len(exam_vals_sec))
            if final_vals_sec:
                section_weighted_sum += (sum(final_vals_sec) / len(final_vals_sec)) * w

            total_weights += w

        # Per-subject averages
        user_ds_avg = sum(user_ds_list)/len(user_ds_list) if user_ds_list else 0
        sec_ds_avg = sum(section_ds_list)/len(section_ds_list) if section_ds_list else 0
        user_exam_avg = sum(user_exam_list)/len(user_exam_list) if user_exam_list else 0
        sec_exam_avg = sum(section_exam_list)/len(section_exam_list) if section_exam_list else 0

        # Weighted final
        if total_weights > 0:
            user_weighted_avg = user_weighted_sum / total_weights
            sec_weighted_avg = section_weighted_sum / total_weights
        else:
            user_weighted_avg = 0
            sec_weighted_avg = 0

        # Caped at ~17.5 to avoid huge bars
        def clamp17(x):
            return round(x, 2) if x < 17.5 else 17.5
        user_ds_avg = clamp17(user_ds_avg)
        sec_ds_avg = clamp17(sec_ds_avg)
        user_exam_avg = clamp17(user_exam_avg)
        sec_exam_avg = clamp17(sec_exam_avg)
        user_weighted_avg = clamp17(user_weighted_avg)
        sec_weighted_avg = clamp17(sec_weighted_avg)

        bars = [
            user_ds_avg/17.5, sec_ds_avg/17.5,
            user_exam_avg/17.5, sec_exam_avg/17.5,
            user_weighted_avg/17.5, sec_weighted_avg/17.5
        ]
        if self.current_language == 'ar':
            bars.reverse()

        self.chart_sim.bars = bars
        self.ch_lbl.setText(
            f"{self.tr('ds_comparison')}: {user_ds_avg:.2f} {self.tr('vs')} {sec_ds_avg:.2f} | "
            f"{self.tr('exam_comparison')}: {user_exam_avg:.2f} {self.tr('vs')} {sec_exam_avg:.2f} | "
            f"{self.tr('weighted_comparison')}: {user_weighted_avg:.2f} {self.tr('vs')} {sec_weighted_avg:.2f}"
        )
        self.chart_sim.update()

    # -------------------------------------------------------------------------
    #                           STATISTICS PAGE
    # -------------------------------------------------------------------------  
    def setup_stats_page(self):
        """Sets up stats page with tabs based on student section."""
        
        self.stats_layout = QVBoxLayout(self.stats_page)
        self.stats_layout.setContentsMargins(20, 20, 20, 20)
        self.stats_layout.setSpacing(20)
    
        self.stats_tab_widget = QTabWidget()
        self.stats_layout.addWidget(self.stats_tab_widget)
    
        self.stats_overview_tab = QWidget()
        self.stats_detailed_tab = QWidget()
        self.stats_simulation_tab = QWidget()
        self.stats_ai_advice_tab = QWidget()
    
        found_student = None
        if self.current_user:
            found_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )
        is_mpi = (found_student and found_student.get('section', '').lower() == 'mpi')
    
        if is_mpi:
            self.stats_tab_widget.addTab(self.stats_overview_tab, "Overview")
            self.stats_tab_widget.addTab(self.stats_detailed_tab, "Detailed")
            self.stats_tab_widget.addTab(self.stats_simulation_tab, "Simulation")
            self.stats_tab_widget.addTab(self.stats_ai_advice_tab, "AI Advice")
            
            # Set up all tabs
            self.setup_stats_overview_tab()
            self.setup_stats_detailed_tab()
            self.setup_stats_simulation_tab()
            self.setup_stats_ai_advice_tab()
        else:
            self.stats_tab_widget.addTab(self.stats_detailed_tab, "Statistics")
            
            self.setup_stats_detailed_tab()
    
            if self.stats_tab_widget.count() == 1:
                self.stats_tab_widget.setTabBarAutoHide(True)

    def get_student_means(self, student):
        """Calculate all means needed for orientation scoring"""
        def get_final(subject):
            s1 = student['grades_s1'].get(subject, {}).get('Final', 0.0)
            s2 = student['grades_s2'].get(subject, {}).get('Final', 0.0)
            return (float(s1) if s1 is not None else 0.0, float(s2) if s2 is not None else 0.0)
        
        total_weighted_sum = 0.0
        total_weight = 0.0
        for mat in self.matieres_s1 + self.matieres_s2:
            mat_name = mat['name']
            w = mat['overall_weight']
            semester = 'grades_s1' if mat_name in [m['name'] for m in self.matieres_s1] else 'grades_s2'
            final = student[semester].get(mat_name, {}).get('Final')
            if final is not None:
                total_weighted_sum += float(final) * w
                total_weight += w
        mg = total_weighted_sum / total_weight if total_weight > 0 else 0.0
        
        math_subjects = ["analyse1", "analyse2", "algebre1", "algebre2"]
        math_mean = sum(sum(get_final(subj))/2 for subj in math_subjects) / len(math_subjects)
        
        algo1 = sum(get_final("algo1"))/2
        algo2 = sum(get_final("algo2"))/2
        prog1 = sum(get_final("prog1"))/2
        prog2 = sum(get_final("prog2"))/2
        info_mean = (2*algo1 + 2*algo2 + prog1 + prog2)/6.0
        
        sl_value = sum(get_final("sys logique"))/2
        en_value = sum(get_final("electronique"))/2
        circuit = sum(get_final("circuit"))/2
        if circuit == 0:
            circuit = sum(get_final("circuits"))/2
            
        return mg, math_mean, info_mean, sl_value, en_value, circuit

    def compute_orientation_rank(self, orientation, current_score):
        scores_with_ids = []  
        mpi = []
        for student in self.all_students_data:
            if student['section'] == "mpi":
                mpi.append(student)
        
        # Get current user's ID
        current_user_id = self.current_user['national_id']
        
        for student in mpi:
            mg, math_mean, info_mean, sl_value, en_value, circuit = self.get_student_means(student)
            
            if orientation == "GL":
                score = self.compute_score_gl_for_user(mg, math_mean, info_mean, sl_value)
            elif orientation == "RT":
                score = self.compute_score_rt_for_user(mg, math_mean, info_mean, sl_value)
            elif orientation == "IIA":
                score = self.compute_score_iia_for_user(mg, math_mean, info_mean, sl_value, en_value, circuit)
            elif orientation == "IMI":
                score = mg
            else:
                score = 0.0
            scores_with_ids.append((score, student['id']))
        
        # Sort by score (descending)
        scores_with_ids.sort(reverse=True, key=lambda x: x[0])
        
        # Find current user's rank
        for rank, (score, student_id) in enumerate(scores_with_ids, 1):
            if student_id == current_user_id:
                return rank, len(scores_with_ids)
                
        return len(scores_with_ids), len(scores_with_ids)  # If not found
    def calculate_rank_probability(self, rank, total, orientation):
            """
            Calculate probability based on rank position:
            - Q1 (0-25%): Very good chance for all orientations
            - Q2 (25-50%): Good chance for RT, IIA, IMI
            - Q3 (50-75%): Only chance for IIA
            - Q4 (75-100%): Low chance for any
            """
            q1 = total * 0.25
            q2 = total * 0.50
            q3 = total * 0.75
            
            # Base probability from rank position
            if rank <= q1:  # Top 25%
                rank_prob = 100
            elif rank <= q2:  # Top 25-50%
                if orientation in ["RT", "IIA", "IMI"]:
                    rank_prob = 75
                else:
                    rank_prob = 25
            elif rank <= q3:  # Top 50-75%
                if orientation == "IIA":
                    rank_prob = 50
                else:
                    rank_prob = 0
            else:  # Bottom 25%
                rank_prob = 0
                
            quartile_size = total / 4
            position_in_quartile = rank % quartile_size
            quartile_factor = 1 - (position_in_quartile / quartile_size)
            
            return rank_prob * quartile_factor
    def setup_stats_overview_tab(self):
        

        # -------------------------------------------------------------------------
        # Historical averages dictionaries (provided data)
        # -------------------------------------------------------------------------
        GL_2022_AVERAGES = {
            "analyse1": 13.72,
            "algebre1": 15.87,
            "algo1": 13.09,
            "programmation": 16.01,
            "analyse2": 12.65,
            "algebre2": 14.74,
            "algo2": 15.36,
            "prog2": 16.71,
            "sys logique": 14.83
        }
        GL_2023_AVERAGES = {
            "analyse1": 16.30,
            "algebre1": 12.96,
            "algo1": 14.84,
            "programmation": 15.42,
            "analyse2": 13.22,
            "algebre2": 16.29,
            "algo2": 16.17,
            "prog2": 15.80,
            "sys logique": 15.05
        }
        RT_2022_AVERAGES = {
            "analyse1": 10.47,
            "algebre1": 13.19,
            "algo1": 10.87,
            "programmation": 14.89,
            "analyse2": 9.02,
            "algebre2": 12.01,
            "algo2": 12.29,
            "prog2": 15.68,
            "sys logique": 13.46
        }
        RT_2023_AVERAGES = {
            "analyse1": 13.02,
            "algebre1": 11.02,
            "algo1": 12.27,
            "programmation": 14.23,
            "analyse2": 10.01,
            "algebre2": 13.95,
            "algo2": 14.14,
            "prog2": 14.87,
            "sys logique": 13.05
        }
        IIA_2022_AVERAGES = {
            "analyse1": 7.78,
            "algebre1": 11.73,
            "algo1": 9.34,
            "prog1": 14.02,
            "circuits": 9.52,
            "electronique": 11.01,
            "sys logique": 12.10,
            "analyse2": 6.36,
            "algebre2": 11.37,
            "algo2": 11.63,
            "prog2": 15.05
        }
        IIA_2023_AVERAGES = {
            "analyse1": 10.80,
            "algebre1": 8.86,
            "algo1": 11.09,
            "prog1": 13.46,
            "circuits": 11.67,
            "electronique": 11.66,
            "sys logique": 11.65,
            "analyse2": 7.89,
            "algebre2": 11.06,
            "algo2": 12.92,
            "prog2": 14.10
        }

        layout = QVBoxLayout(self.stats_overview_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.overview_sub_frames = []
        self.overview_labels = []
        self.orientation_gauges = []

        overview_title = QLabel(self.tr("orientation_overview"))
        overview_title.setStyleSheet("margin: 0; padding: 0; margin-top: 30px;")
        overview_title.setContentsMargins(0, 0, 0, 0)
        overview_title.setObjectName("SectionTitle")
        layout.addWidget(overview_title, 0, Qt.AlignTop)
        layout.addSpacing(60)

        # Colors based on theme.
        if self.theme == 'dark':
            sub_frame_bg = "#2f2f2f"
            label_color = "#ffffff"
            gauge_scale_color = "#dddddd"
            summary_color = "#ffffff"
        else:
            sub_frame_bg = "#fafafa"
            label_color = "#222222"
            gauge_scale_color = "#555555"
            summary_color = "#222222"

        user_student = None
        if self.current_user:
            user_student = next((s for s in self.all_students_data 
                                if s['id'] == self.current_user['national_id']), None)
        if not user_student:
            mg = 0.0
        else:
            total_weighted_sum = 0.0
            total_weight = 0.0
            for mat in self.matieres_s1:
                mat_name = mat['name']
                w = mat['overall_weight']
                real_final = user_student['grades_s1'].get(mat_name, {}).get('Final')
                if real_final is not None:
                    total_weighted_sum += float(real_final) * w
                    total_weight += w
            for mat in self.matieres_s2:
                mat_name = mat['name']
                w = mat['overall_weight']
                real_final = user_student['grades_s2'].get(mat_name, {}).get('Final')
                if real_final is not None:
                    total_weighted_sum += float(real_final) * w
                    total_weight += w
            mg = total_weighted_sum / total_weight if total_weight > 0 else 0.0

        def get_final(subject):
            vals = []
            if user_student:
                s1 = user_student['grades_s1'].get(subject, {}).get('Final')
                s2 = user_student['grades_s2'].get(subject, {}).get('Final')
                if s1 is not None:
                    vals.append(float(s1))
                if s2 is not None:
                    vals.append(float(s2))
            return sum(vals) / len(vals) if vals else 0.0

        math_subjects = ["analyse1", "analyse2", "algebre1", "algebre2"]
        moy_math = sum(get_final(subj) for subj in math_subjects) / len(math_subjects) if math_subjects else 0.0

        algo1_val = get_final("algo1")
        algo2_val = get_final("algo2")
        prog1_val = get_final("prog1")
        prog2_val = get_final("prog2")
        info_total = 2 * algo1_val + 2 * algo2_val + prog1_val + prog2_val
        moy_info = info_total / 6.0 if info_total else 0.0
        self.projected_avg = mg
        self.user_moy_math = moy_math 
        self.user_moy_info = moy_info
        sl = get_final("sys logique")

        electronique = get_final("electronique")
        circuit = get_final("circuit")
        if circuit == 0:
            circuit = get_final("circuits")
        self.user_sl = sl
        self.user_en = electronique
        self.user_circuit = circuit
        score_GL = self.compute_score_gl_for_user(mg, moy_math, moy_info, sl)
        score_RT = self.compute_score_rt_for_user(mg, moy_math, moy_info, sl)
        score_IIA = self.compute_score_iia_for_user(mg, moy_math, moy_info, sl, electronique, circuit)
        score_IMI = 50.0 if mg >= self.orientation_thresholds["IMI"] else 0.0

        def hist_avg(subject, hist2022, hist2023):
            return (hist2022.get(subject, 0) + hist2023.get(subject, 0)) / 2.0

        MG_target = 10.0

        # For GL benchmark:
        math_hist_GL = (hist_avg("analyse1", GL_2022_AVERAGES, GL_2023_AVERAGES) +
                        hist_avg("analyse2", GL_2022_AVERAGES, GL_2023_AVERAGES) +
                        hist_avg("algebre1", GL_2022_AVERAGES, GL_2023_AVERAGES) +
                        hist_avg("algebre2", GL_2022_AVERAGES, GL_2023_AVERAGES)) / 4.0
        info_hist_GL = (2 * hist_avg("algo1", GL_2022_AVERAGES, GL_2023_AVERAGES) +
                        2 * hist_avg("algo2", GL_2022_AVERAGES, GL_2023_AVERAGES) +
                        hist_avg("programmation", GL_2022_AVERAGES, GL_2023_AVERAGES) +
                        hist_avg("prog2", GL_2022_AVERAGES, GL_2023_AVERAGES)) / 6.0
        sl_hist_GL = hist_avg("sys logique", GL_2022_AVERAGES, GL_2023_AVERAGES)
        benchmark_GL = 2 * MG_target + math_hist_GL + 2 * info_hist_GL + sl_hist_GL

        # For RT benchmark :
        math_hist_RT = (hist_avg("analyse1", RT_2022_AVERAGES, RT_2023_AVERAGES) +
                        hist_avg("analyse2", RT_2022_AVERAGES, RT_2023_AVERAGES) +
                        hist_avg("algebre1", RT_2022_AVERAGES, RT_2023_AVERAGES) +
                        hist_avg("algebre2", RT_2022_AVERAGES, RT_2023_AVERAGES)) / 4.0
        info_hist_RT = (2 * hist_avg("algo1", RT_2022_AVERAGES, RT_2023_AVERAGES) +
                        2 * hist_avg("algo2", RT_2022_AVERAGES, RT_2023_AVERAGES) +
                        hist_avg("programmation", RT_2022_AVERAGES, RT_2023_AVERAGES) +
                        hist_avg("prog2", RT_2022_AVERAGES, RT_2023_AVERAGES)) / 6.0
        sl_hist_RT = hist_avg("sys logique", RT_2022_AVERAGES, RT_2023_AVERAGES)
        benchmark_RT = 2 * MG_target + math_hist_RT + info_hist_RT + sl_hist_RT

        # For IIA benchmark :
        math_hist_iia = (hist_avg("analyse1", IIA_2022_AVERAGES, IIA_2023_AVERAGES) +
                        hist_avg("analyse2", IIA_2022_AVERAGES, IIA_2023_AVERAGES) +
                        hist_avg("algebre1", IIA_2022_AVERAGES, IIA_2023_AVERAGES) +
                        hist_avg("algebre2", IIA_2022_AVERAGES, IIA_2023_AVERAGES)) / 4.0
        info_hist_iia = (2 * hist_avg("algo1", IIA_2022_AVERAGES, IIA_2023_AVERAGES) +
                        2 * hist_avg("algo2", IIA_2022_AVERAGES, IIA_2023_AVERAGES) +
                        hist_avg("prog1", IIA_2022_AVERAGES, IIA_2023_AVERAGES) +
                        hist_avg("prog2", IIA_2022_AVERAGES, IIA_2023_AVERAGES)) / 6.0
        sl_hist_iia = hist_avg("sys logique", IIA_2022_AVERAGES, IIA_2023_AVERAGES)
        electronique_hist = hist_avg("electronique", IIA_2022_AVERAGES, IIA_2023_AVERAGES)
        circuit_hist = hist_avg("circuits", IIA_2022_AVERAGES, IIA_2023_AVERAGES)
        benchmark_IIA = 2 * MG_target + math_hist_iia + 2 * info_hist_iia + sl_hist_iia + (electronique_hist + circuit_hist) / 2.0

        # -------------------------------------------------------------------------
        # Compute Probabilities for Each Orientation.
        # -------------------------------------------------------------------------
        rank_GL, total_GL = self.compute_orientation_rank("GL", score_GL)
        rank_RT, total_RT = self.compute_orientation_rank("RT", score_RT)
        rank_IIA, total_IIA = self.compute_orientation_rank("IIA", score_IIA)
        rank_IMI, total_IMI = self.compute_orientation_rank("IMI", score_IMI)
           
        prob_GL = min((score_GL / benchmark_GL) * 100 * self.calculate_rank_probability(rank_GL, total_GL, "GL") / 100, 100) if benchmark_GL > 0 else 0
        prob_RT = min((score_RT / benchmark_RT) * 100 * self.calculate_rank_probability(rank_RT, total_RT, "RT") / 100, 100) if benchmark_RT > 0 else 0
        prob_IIA = min((score_IIA / benchmark_IIA) * 100 * self.calculate_rank_probability(rank_IIA, total_IIA, "IIA") / 100, 100) if benchmark_IIA > 0 else 0
        prob_IMI = 90.0 * self.calculate_rank_probability(rank_IMI, 521, "IMI") / 100 if mg >= self.orientation_thresholds["IMI"] else 0.0     # -------------------------------------------------------------------------
        
        orientation_data = [
            ("GL", round(prob_GL, 2)),
            ("RT", round(prob_RT, 2)),
            ("IIA", round(prob_IIA, 2)),
            ("IMI", round(prob_IMI, 2)),
        ]

       
        gauge_card = QFrame()
        gauge_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        gauge_card_layout = QHBoxLayout(gauge_card)
        gauge_card_layout.setContentsMargins(0, 0, 0, 0)
        gauge_card_layout.setSpacing(30)

        for name, val in orientation_data:
            sub_frame = QFrame()
            sub_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            sub_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {sub_frame_bg};
                    border: none;
                    border-radius: 8px;
                }}
            """)
            sub_layout = QVBoxLayout(sub_frame)
            sub_layout.setContentsMargins(10, 10, 10, 10)
            sub_layout.setSpacing(5)
            sub_layout.setAlignment(Qt.AlignTop)

            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(f"""
                margin: 0;
                padding: 0;
                font-weight: bold;
                font-size: 16px;
                color: {label_color};
            """)

            gauge = NeedleGauge(
                min_val=0,
                max_val=100,
                value=val,
                angle_min=-120,
                angle_max=120,
                arc_width=14,
                needle_color="#3949AB",
                arc_color="#cccccc",
                fill_color="#7E57C2",
                scale_color=gauge_scale_color,
                theme=self.theme,
                parent=self
            )

            self.overview_sub_frames.append(sub_frame)
            self.overview_labels.append(label)
            self.orientation_gauges.append(gauge)

            sub_layout.addWidget(label, 0, Qt.AlignHCenter)
            sub_layout.addWidget(gauge, 0, Qt.AlignHCenter | Qt.AlignTop)
            gauge_card_layout.addWidget(sub_frame)

        layout.addWidget(gauge_card, 0, Qt.AlignTop)
        layout.addSpacing(60)

        """Build a textual summary of the orientation eligibility."""
        rank_summary = self.tr("rank_summary").format(
            gl_rank=rank_GL, total_gl=total_GL,
            rt_rank=rank_RT, total_rt=total_RT, 
            iia_rank=rank_IIA, total_iia=total_IIA,
            imi_rank=rank_IMI, total_imi=total_IMI
        )
        
        self.overview_summary_label = QLabel(self.tr("placeholder_orientation_summary"))
        self.overview_summary_label.setText(rank_summary)
        self.overview_summary_label.setWordWrap(True)
        self.overview_summary_label.setStyleSheet(
            f"margin: 0; padding: 0; font-size: 14px; color: {summary_color};"
        )
        self.overview_summary_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.overview_summary_label, 0, Qt.AlignTop)
        layout.addStretch()
        
        if not hasattr(self, "orientation_label"):
            self.orientation_label = QLabel()
        def color_ok_or_no(prob):
            return f"<span style='color:#4CAF50;font-weight:bold;'>OK</span>" if prob >= 50 else \
                f"<span style='color:#f44336;font-weight:bold;'>No</span>"
        gl_str = color_ok_or_no(prob_GL)
        rt_str = color_ok_or_no(prob_RT)
        iia_str = color_ok_or_no(prob_IIA)
        imi_str = color_ok_or_no(prob_IMI)
        final_html = " | ".join([
            f"GL: {gl_str} ({round(prob_GL,1)}%)",
            f"RT: {rt_str} ({round(prob_RT,1)}%)",
            f"IIA: {iia_str} ({round(prob_IIA,1)}%)",
            f"IMI: {imi_str} ({round(prob_IMI,1)}%)"
        ])
        styled_summary = f"<b>Orientation Eligibility:</b> {final_html}"
        self.orientation_label.setTextFormat(Qt.RichText)
        self.orientation_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.orientation_label.setOpenExternalLinks(False)
        self.orientation_label.setText(styled_summary)

    def toggle_spider_chart(self):
        self.show_spider_mode = not self.show_spider_mode
        self.refresh_stats_chart()

    def refresh_overview_tab_styles(self):
        """Refresh styles of the overview tab based on the current theme."""
        if not hasattr(self, 'overview_sub_frames'):
            return  

        if self.theme == 'dark':
            sub_frame_bg = "#2f2f2f"
            label_color = "#ffffff"
            gauge_scale_color = "#dddddd"
            summary_color = "#ffffff"
        else:
            sub_frame_bg = "#fafafa"
            label_color = "#222222"
            gauge_scale_color = "#555555"
            summary_color = "#222222"

        for frame in self.overview_sub_frames:
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {sub_frame_bg};
                    border: none;
                    border-radius: 8px;
                }}
            """)

        # Update each label
        for lbl in self.overview_labels:
            lbl.setStyleSheet(f"""
                margin: 0;
                padding: 0;
                font-weight: bold;
                font-size: 16px;
                color: {label_color};
            """)

        if hasattr(self, 'overview_summary_label'):
            self.overview_summary_label.setStyleSheet(f"""
                margin: 0;
                padding: 0;
                font-size: 16px;
                color: {summary_color};
            """)

        if hasattr(self, 'orientation_gauges'):
            for g in self.orientation_gauges:
                g.setScaleColor(gauge_scale_color)  
                g.setTheme(self.theme)             
                g.update()

        # Force a repaint of the tab
        self.stats_overview_tab.update()



      # ================== [1] GL 2022 & 2023 AVERAGES + SEMESTER MAP ==================
    GL_2023_AVERAGES = {
        "analyse1": 16.30,
        "algebre1": 12.96,
        "algo1": 14.84,
        "programmation": 15.42,   
        "analyse2": 13.22,
        "algebre2": 16.29,
        "algo2": 16.17,
        "prog2": 15.80,           
        "sys logique": 15.05
    }

    GL_2022_AVERAGES = {
        "analyse1": 13.72,
        "algebre1": 15.87,
        "algo1": 13.09,
        "programmation": 16.01,   
        "analyse2": 12.65,        
        "algebre2": 14.74,
        "algo2": 15.36,           
        "prog2": 16.71,           
        "sys logique": 14.83
    }

    # used to figure out whether a matiere is S1 or S2
    GL_MATIERE_SEMESTER_MAP = {
        "analyse1": 1,
        "algebre1": 1,
        "algo1": 1,
        "programmation": 1,   # S1
        "analyse2": 2,
        "algebre2": 2,
        "algo2": 2,
        "prog2": 2,
        "sys logique": 2
    }

    def build_spider_chart_for_mpi_spider(self, user_student):
        
        

        matiere_order = [
            "analyse1", "algebre1", "algo1", "programmation",
            "analyse2", "algebre2", "algo2", "prog2", "sys logique"
        ]

        if self.theme == "light":
            text_color = QColor("#000000")
            bg_color = QColor("#ffffff")
            plot_bg_color = QColor("#f0f0f0")
        else:
            text_color = QColor("#ffffff")
            bg_color = QColor("#1f1f1f")
            plot_bg_color = QColor("#444444")

        def get_student_final(u_stud, mat):
            sem = self.GL_MATIERE_SEMESTER_MAP.get(mat, 1)
            if sem == 1:
                final_val = u_stud['grades_s1'].get(mat, {}).get('Final')
            else:
                final_val = u_stud['grades_s2'].get(mat, {}).get('Final')
            return float(final_val) if final_val is not None else 0.0

        series_2022 = QLineSeries()
        series_2022.setName("2022 Avg")
        pen_2022 = QPen(QColor("#e53935"))  # red
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        series_2023 = QLineSeries()
        series_2023.setName("2023 Avg")
        pen_2023 = QPen(QColor("#1e88e5"))  # blue
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        series_user = QLineSeries()
        series_user.setName("Student")
        pen_user = QPen(QColor("#43a047"))  # green
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        # Distribute matieres around 360
        n = len(matiere_order)
        angle_step = 360.0 / n

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            val_2022 = self.GL_2022_AVERAGES.get(mat, 0.0)
            val_2023 = self.GL_2023_AVERAGES.get(mat, 0.0)
            val_user = get_student_final(user_student, mat)

            series_2022.append(angle_deg, val_2022)
            series_2023.append(angle_deg, val_2023)
            series_user.append(angle_deg, val_user)

        # Close polygons
        first_2022 = series_2022.at(0)
        series_2022.append(first_2022.x(), first_2022.y())

        first_2023 = series_2023.at(0)
        series_2023.append(first_2023.x(), first_2023.y())

        first_user = series_user.at(0)
        series_user.append(first_user.x(), first_user.y())

        # Create the polar chart
        chart = QPolarChart()
        # Insert extra line-breaks so the chart title is pushed down
        chart.setTitle("\n\nSpider Chart (GL): 2022 vs 2023 vs You")
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setAnimationOptions(QPolarChart.NoAnimation)
        chart.setBackgroundRoundness(0)
        chart.setBackgroundBrush(bg_color)
        chart.setPlotAreaBackgroundBrush(plot_bg_color)
        chart.setPlotAreaBackgroundVisible(True)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setTitleBrush(text_color)
        chart.legend().setLabelColor(text_color)

        radial_axis = QValueAxis()
        radial_axis.setRange(0, 20)
        radial_axis.setTickCount(5)   
        radial_axis.setLabelFormat("%.0f")
        radial_axis.setLabelsColor(text_color)
        radial_axis.setLabelsVisible(True)
        radial_axis.setGridLineVisible(True)
        radial_axis.setMinorTickCount(0)
        radial_axis.setTitleText("")  

        angular_axis = QCategoryAxis()
        angular_axis.setLabelsColor(text_color)
        angular_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        angular_axis.setGridLineVisible(True)

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            # If the mat is "analyse1" we rename it to "sys logique | analyse1"
            if mat == "analyse1":
                display_label = "sys logique | analyse1"
            else:
                display_label = mat

            angular_axis.append(display_label, angle_deg)

        angular_axis.append("", 360)

        chart.addAxis(radial_axis, QPolarChart.PolarOrientationRadial)
        chart.addAxis(angular_axis, QPolarChart.PolarOrientationAngular)

        for s in (series_2022, series_2023, series_user):
            s.attachAxis(radial_axis)
            s.attachAxis(angular_axis)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")

        return chart_view






    # ================== BUILD GL MULTI-LINE CHART FOR MPI STUDENTS ==================
    def build_gl_multi_line_chart_for_mpi(self, user_student):
        """
        Returns a QChartView with 3 lines:
        - 2022 Averages (red)
        - 2023 Averages (blue)
        - Current user's Final (green) for each GL matiere.
        This is only shown if the user is in MPI.
        """

        matiere_order = [
            "analyse1", "algebre1", "algo1", "programmation",
            "analyse2", "algebre2", "algo2", "prog2", "sys logique"
        ]

        series_2022 = QLineSeries()
        series_2022.setName("2022 Average")

        series_2023 = QLineSeries()
        series_2023.setName("2023 Average")

        series_user = QLineSeries()
        series_user.setName("Student")

        if self.theme == "dark":
            text_color = QColor("#ffffff")
        else:
            text_color = QColor("#000000")

        pen_2022 = QPen(QColor("#e53935"))  # red
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        pen_2023 = QPen(QColor("#1e88e5"))  # blue
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        pen_user = QPen(QColor("#43a047"))  # green
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        series_2022.setPointsVisible(True)
        series_2023.setPointsVisible(True)
        series_user.setPointsVisible(True)
       

        def get_student_final(user_stud, mat_name):
            sem = self.GL_MATIERE_SEMESTER_MAP.get(mat_name, 1)
            if sem == 1:
                mat_dict = user_stud['grades_s1'].get(mat_name, {})
            else:
                mat_dict = user_stud['grades_s2'].get(mat_name, {})
            final_val = mat_dict.get('Final')
            if final_val is None:
                return None
            try:
                return float(final_val)
            except:
                return None

        # Append data
        for i, mat in enumerate(matiere_order):
            avg_2022 = self.GL_2022_AVERAGES.get(mat, 0.0)
            series_2022.append(float(i), avg_2022)

            avg_2023 = self.GL_2023_AVERAGES.get(mat, 0.0)
            series_2023.append(float(i), avg_2023)

            stud_val = get_student_final(user_student, mat)
            if stud_val is None:
                stud_val = 0.0
            series_user.append(float(i), stud_val)

        # Create chart
        chart = QChart()
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setTitle("GL Orientation - Multi-Line Chart")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)

        chart.setBackgroundVisible(False)
        chart.setTitleBrush(QColor(text_color))
        chart.legend().setLabelColor(text_color)

        axisY = QValueAxis()
        axisY.setRange(0, 20)
        axisY.setTitleText("Grade")
        axisY.setLabelFormat("%.1f")  
        axisY.setTickCount(6)          
        axisY.setMinorTickCount(0)
        axisY.setLabelsColor(text_color)
        axisY.setTitleBrush(QColor(text_color))

        
        axisY.setGridLineVisible(True)
        axisY.setMinorGridLineVisible(False)

        chart.addAxis(axisY, Qt.AlignLeft)
        series_2022.attachAxis(axisY)
        series_2023.attachAxis(axisY)
        series_user.attachAxis(axisY)

        axisX = QCategoryAxis()
        axisX.setTitleText("Matières (GL)")
        axisX.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        axisX.setLabelsColor(text_color)
        axisX.setTitleBrush(QColor(text_color))

        axisX.setGridLineVisible(True)
        axisX.setMinorGridLineVisible(False)

        axisX.setLabelsAngle(-20)

        for i, mat in enumerate(matiere_order):
            axisX.append(mat, float(i))

        axisX.setRange(0.0, float(len(matiere_order) - 0.5))

        chart.addAxis(axisX, Qt.AlignBottom)
        series_2022.attachAxis(axisX)
        series_2023.attachAxis(axisX)
        series_user.attachAxis(axisX)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")

        return chart_view



    def switch_chart_mode(self, forward: bool):
        idx = self.MODES.index(self.chart_mode)  # self.MODES = ["GL", "RT", "IIA", "IMI"]
        if forward:
            new_idx = (idx + 1) % len(self.MODES)
        else:
            new_idx = (idx - 1) % len(self.MODES)

        self.chart_mode = self.MODES[new_idx]  
        self.carousel_label.setText(self.chart_mode)
        self.refresh_stats_chart()



    RT_2023_AVERAGES = {
    "analyse1": 13.02,
    "algebre1": 11.02,
    "algo1": 12.27,
    "programmation": 14.23,
    "analyse2": 10.01,
    "algebre2": 13.95,
    "algo2": 14.14,
    "prog2": 14.87,
    "sys logique": 13.05
    }

    RT_2022_AVERAGES = {
        "analyse1": 10.47,
        "algebre1": 13.19,
        "algo1": 10.87,
        "programmation": 14.89,  
        "analyse2": 9.02,        
        "algebre2": 12.01,
        "algo2": 12.29,        
        "prog2": 15.68,
        "sys logique": 13.46
    }

    RT_MATIERE_SEMESTER_MAP = {
        "analyse1": 1,
        "algebre1": 1,
        "algo1": 1,
        "programmation": 1,
        "analyse2": 2,
        "algebre2": 2,
        "algo2": 2,
        "prog2": 2,
        "sys logique": 2

    }




    # ============== BUILD RT EQUIVALENT SPIDER / MULTI-LINE ==============
    def build_spider_chart_for_rt_spider(self, user_student):

        matiere_order = [
            "analyse1", "algebre1", "algo1", "programmation",
            "analyse2", "algebre2", "algo2", "prog2", "sys logique"
        ]

        if self.theme == "light":
            text_color = QColor("#000000")
            bg_color = QColor("#ffffff")
            plot_bg_color = QColor("#f0f0f0")
        else:
            text_color = QColor("#ffffff")
            bg_color = QColor("#1f1f1f")
            plot_bg_color = QColor("#444444")

        def get_student_final(u_stud, mat):
            sem = self.RT_MATIERE_SEMESTER_MAP.get(mat, 1)
            if sem == 1:
                final_val = u_stud['grades_s1'].get(mat, {}).get('Final')
            else:
                final_val = u_stud['grades_s2'].get(mat, {}).get('Final')
            return float(final_val) if final_val is not None else 0.0

        series_2022 = QLineSeries()
        series_2022.setName("2022 Avg")
        pen_2022 = QPen(QColor("#e53935"))
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        series_2023 = QLineSeries()
        series_2023.setName("2023 Avg")
        pen_2023 = QPen(QColor("#1e88e5"))
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        series_user = QLineSeries()
        series_user.setName("Student")
        pen_user = QPen(QColor("#43a047"))
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        n = len(matiere_order)
        angle_step = 360.0 / n

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            val_2022 =  self.RT_2022_AVERAGES.get(mat, 0.0)
            val_2023 =  self.RT_2023_AVERAGES.get(mat, 0.0)
            val_user = get_student_final(user_student, mat)

            series_2022.append(angle_deg, val_2022)
            series_2023.append(angle_deg, val_2023)
            series_user.append(angle_deg, val_user)

        # close polygons
        series_2022.append(series_2022.at(0).x(), series_2022.at(0).y())
        series_2023.append(series_2023.at(0).x(), series_2023.at(0).y())
        series_user.append(series_user.at(0).x(), series_user.at(0).y())

        chart = QPolarChart()
        chart.setTitle("\n\nSpider Chart (RT): 2022 vs 2023 vs You")
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setAnimationOptions(QPolarChart.NoAnimation)
        chart.setBackgroundRoundness(0)
        chart.setBackgroundBrush(bg_color)
        chart.setPlotAreaBackgroundBrush(plot_bg_color)
        chart.setPlotAreaBackgroundVisible(True)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setTitleBrush(text_color)
        chart.legend().setLabelColor(text_color)

        radial_axis = QValueAxis()
        radial_axis.setRange(0, 20)
        radial_axis.setTickCount(5)
        radial_axis.setLabelFormat("%.0f")
        radial_axis.setLabelsColor(text_color)
        radial_axis.setLabelsVisible(True)
        radial_axis.setGridLineVisible(True)
        radial_axis.setMinorTickCount(0)
        radial_axis.setTitleText("")

        angular_axis = QCategoryAxis()
        angular_axis.setLabelsColor(text_color)
        angular_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        angular_axis.setGridLineVisible(True)

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            if mat == "analyse1":
                display_label = "sys logique | analyse1"
            else:
                display_label = mat
            angular_axis.append(display_label, angle_deg)
        angular_axis.append("", 360)

        chart.addAxis(radial_axis, QPolarChart.PolarOrientationRadial)
        chart.addAxis(angular_axis, QPolarChart.PolarOrientationAngular)

        for s in (series_2022, series_2023, series_user):
            s.attachAxis(radial_axis)
            s.attachAxis(angular_axis)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view


    def build_rt_multi_line_chart_for_mpi(self, user_student):

        matiere_order = [
            "analyse1", "algebre1", "algo1", "programmation",
            "analyse2", "algebre2", "algo2", "prog2", "sys logique"
        ]

        series_2022 = QLineSeries()
        series_2022.setName("2022 Average")

        series_2023 = QLineSeries()
        series_2023.setName("2023 Average")

        series_user = QLineSeries()
        series_user.setName("Student")

        if self.theme == "dark":
            text_color = QColor("#ffffff")
        else:
            text_color = QColor("#000000")

        pen_2022 = QPen(QColor("#e53935"))
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        pen_2023 = QPen(QColor("#1e88e5"))
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        pen_user = QPen(QColor("#43a047"))
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        series_2022.setPointsVisible(True)
        series_2023.setPointsVisible(True)
        series_user.setPointsVisible(True)

        def get_student_final(u_stud, mat_name):
            sem = self.RT_MATIERE_SEMESTER_MAP.get(mat_name, 1)
            if sem == 1:
                mat_dict = u_stud['grades_s1'].get(mat_name, {})
            else:
                mat_dict = u_stud['grades_s2'].get(mat_name, {})
            final_val = mat_dict.get('Final')
            return float(final_val) if final_val else 0.0

        for i, mat in enumerate(matiere_order):
            avg_2022 = self.RT_2022_AVERAGES.get(mat, 0.0)
            series_2022.append(float(i), avg_2022)

            avg_2023 = self.RT_2023_AVERAGES.get(mat, 0.0)
            series_2023.append(float(i), avg_2023)

            stud_val = get_student_final(user_student, mat)
            series_user.append(float(i), stud_val)

        chart = QChart()
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setTitle("RT Orientation - Multi-Line Chart")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)

        chart.setBackgroundVisible(False)
        chart.setTitleBrush(QColor(text_color))
        chart.legend().setLabelColor(text_color)

        axisY = QValueAxis()
        axisY.setRange(0, 20)
        axisY.setTitleText("Grade")
        axisY.setLabelFormat("%.1f")
        axisY.setTickCount(6)
        axisY.setMinorTickCount(0)
        axisY.setLabelsColor(text_color)
        axisY.setTitleBrush(QColor(text_color))
        axisY.setGridLineVisible(True)
        axisY.setMinorGridLineVisible(False)

        chart.addAxis(axisY, Qt.AlignLeft)
        series_2022.attachAxis(axisY)
        series_2023.attachAxis(axisY)
        series_user.attachAxis(axisY)

        axisX = QCategoryAxis()
        axisX.setTitleText("Matières (RT)")
        axisX.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        axisX.setLabelsColor(text_color)
        axisX.setTitleBrush(QColor(text_color))
        axisX.setGridLineVisible(True)
        axisX.setMinorGridLineVisible(False)
        axisX.setLabelsAngle(-20)

        for i, mat in enumerate(matiere_order):
            axisX.append(mat, float(i))
        axisX.setRange(0.0, float(len(matiere_order) - 0.5))

        chart.addAxis(axisX, Qt.AlignBottom)
        series_2022.attachAxis(axisX)
        series_2023.attachAxis(axisX)
        series_user.attachAxis(axisX)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view





# ----------------------------------------------------------------
#  IIA Averages + Semester Map
# ----------------------------------------------------------------

    IIA_2022_AVERAGES = {
        "analyse1": 7.78,
        "algebre1": 11.73,
        "algo1": 9.34,
        "prog1": 14.02,
        "circuits": 9.52,
        "electronique": 11.01,
        "sys logique": 12.10,
        "analyse2":6.36,
        "algebre2": 11.37,
        "algo2": 11.63,
        "prog2": 15.05
    }

    IIA_2023_AVERAGES = {
        "analyse1": 10.80,
        "algebre1": 8.86,
        "algo1": 11.09,
        "prog1": 13.46,
        "circuits": 11.67,
        "electronique": 11.66,
        "sys logique": 11.65,
        "analyse2": 7.89,
        "algebre2": 11.06,
        "algo2": 12.92,
        "prog2": 14.10
    }

    IIA_MATIERE_SEMESTER_MAP = {
        "analyse1": 1,
        "algebre1": 1,
        "algo1": 1,
        "prog1": 1,
        "circuits": 1,
        "electronique": 2,
        "sys logique": 2,
        "analyse2": 2,
        "algebre2": 2,
        "algo2": 2,
        "prog2": 2
    }

    def build_spider_chart_for_iia_spider(self, user_student):

        # 11 matieres for IIA
        matiere_order = [
            "analyse1",
            "algebre1",
            "algo1",
            "prog1",
            "circuits",
            "analyse2",
            "algebre2",
            "electronique",
            "sys logique",
            "algo2",
            "prog2"
        ]

        if self.theme == "light":
            text_color = QColor("#000000")
            bg_color = QColor("#ffffff")
            plot_bg_color = QColor("#f0f0f0")
        else:
            text_color = QColor("#ffffff")
            bg_color = QColor("#1f1f1f")
            plot_bg_color = QColor("#444444")

        def get_student_final(u_stud, mat):
            sem = self.IIA_MATIERE_SEMESTER_MAP.get(mat, 1)
            if sem == 1:
                final_val = u_stud['grades_s1'].get(mat, {}).get('Final')
            else:
                final_val = u_stud['grades_s2'].get(mat, {}).get('Final')
            return float(final_val) if final_val is not None else 0.0

        series_2022 = QLineSeries()
        series_2022.setName("2022 Avg")
        pen_2022 = QPen(QColor("#e53935"))  # red
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        series_2023 = QLineSeries()
        series_2023.setName("2023 Avg")
        pen_2023 = QPen(QColor("#1e88e5"))  # blue
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        series_user = QLineSeries()
        series_user.setName("Student")
        pen_user = QPen(QColor("#43a047"))  # green
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        n = len(matiere_order)
        angle_step = 360.0 / n

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            val_2022 = self.IIA_2022_AVERAGES.get(mat, 0.0)
            val_2023 = self.IIA_2023_AVERAGES.get(mat, 0.0)
            val_user = get_student_final(user_student, mat)

            series_2022.append(angle_deg, val_2022)
            series_2023.append(angle_deg, val_2023)
            series_user.append(angle_deg, val_user)

        # close polygon
        series_2022.append(series_2022.at(0).x(), series_2022.at(0).y())
        series_2023.append(series_2023.at(0).x(), series_2023.at(0).y())
        series_user.append(series_user.at(0).x(), series_user.at(0).y())

        chart = QPolarChart()
        chart.setTitle("\n\nSpider Chart (IIA): 2022 vs 2023 vs You")
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setAnimationOptions(QPolarChart.NoAnimation)
        chart.setBackgroundRoundness(0)
        chart.setBackgroundBrush(bg_color)
        chart.setPlotAreaBackgroundBrush(plot_bg_color)
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setTitleBrush(text_color)
        chart.legend().setLabelColor(text_color)

        radial_axis = QValueAxis()
        radial_axis.setRange(0, 20)
        radial_axis.setTickCount(5)
        radial_axis.setLabelFormat("%.0f")
        radial_axis.setLabelsColor(text_color)
        radial_axis.setLabelsVisible(True)
        radial_axis.setGridLineVisible(True)
        radial_axis.setMinorTickCount(0)
        radial_axis.setTitleText("")

        angular_axis = QCategoryAxis()
        angular_axis.setLabelsColor(text_color)
        angular_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        angular_axis.setGridLineVisible(True)

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            if mat == "analyse1":
                display_label = " prog2|analyse1"
            else:
                display_label = mat
            angular_axis.append(display_label, angle_deg)
        angular_axis.append("", 360)

        chart.addAxis(radial_axis, QPolarChart.PolarOrientationRadial)
        chart.addAxis(angular_axis, QPolarChart.PolarOrientationAngular)

        for s in (series_2022, series_2023, series_user):
            s.attachAxis(radial_axis)
            s.attachAxis(angular_axis)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view


    def build_iia_multi_line_chart_for_iia(self, user_student):

        matiere_order = [
            "analyse1",
            "algebre1",
            "algo1",
            "prog1",
            "circuits",
            "analyse2",
            "algebre2",
            "electronique",
            "sys logique",
            "algo2",
            "prog2"
        ]

        series_2022 = QLineSeries()
        series_2022.setName("2022 Average")

        series_2023 = QLineSeries()
        series_2023.setName("2023 Average")

        series_user = QLineSeries()
        series_user.setName("Student")

        if self.theme == "dark":
            text_color = QColor("#ffffff")
        else:
            text_color = QColor("#000000")

        pen_2022 = QPen(QColor("#e53935"))
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        pen_2023 = QPen(QColor("#1e88e5"))
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        pen_user = QPen(QColor("#43a047"))
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        series_2022.setPointsVisible(True)
        series_2023.setPointsVisible(True)
        series_user.setPointsVisible(True)

        def get_student_final(u_stud, mat_name):
            sem = self.IIA_MATIERE_SEMESTER_MAP.get(mat_name, 1)
            if sem == 1:
                val = u_stud['grades_s1'].get(mat_name, {}).get('Final')
            else:
                val = u_stud['grades_s2'].get(mat_name, {}).get('Final')
            return float(val) if val is not None else 0.0

        for i, mat in enumerate(matiere_order):
            avg_2022 = self.IIA_2022_AVERAGES.get(mat, 0.0)
            avg_2023 = self.IIA_2023_AVERAGES.get(mat, 0.0)
            series_2022.append(float(i), avg_2022)
            series_2023.append(float(i), avg_2023)

            stud_val = get_student_final(user_student, mat)
            series_user.append(float(i), stud_val)

        chart = QChart()
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setTitle("IIA Orientation - Multi-Line Chart")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setBackgroundVisible(False)
        chart.setTitleBrush(QColor(text_color))
        chart.legend().setLabelColor(text_color)

        axisY = QValueAxis()
        axisY.setRange(0, 20)
        axisY.setTitleText("Grade")
        axisY.setLabelFormat("%.1f")
        axisY.setTickCount(6)
        axisY.setMinorTickCount(0)
        axisY.setLabelsColor(text_color)
        axisY.setTitleBrush(QColor(text_color))
        axisY.setGridLineVisible(True)
        axisY.setMinorGridLineVisible(False)

        chart.addAxis(axisY, Qt.AlignLeft)
        series_2022.attachAxis(axisY)
        series_2023.attachAxis(axisY)
        series_user.attachAxis(axisY)

        axisX = QCategoryAxis()
        axisX.setTitleText("Matières (IIA)")
        axisX.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        axisX.setLabelsColor(text_color)
        axisX.setTitleBrush(QColor(text_color))
        axisX.setGridLineVisible(True)
        axisX.setMinorGridLineVisible(False)
        axisX.setLabelsAngle(-20)

        for i, mat in enumerate(matiere_order):
            axisX.append(mat, float(i))
        axisX.setRange(0.0, float(len(matiere_order) - 0.5))

        chart.addAxis(axisX, Qt.AlignBottom)
        series_2022.attachAxis(axisX)
        series_2023.attachAxis(axisX)
        series_user.attachAxis(axisX)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view

           

    ################ IMI 2022 & 2023 AVERAGES ################

    IMI_2022_AVERAGES = {
        # -- SEMESTRE 1 --
        "analyse1":         5.78,
        "algebre1":         9.32,
        "algo1":            6.76,
        "prog1":            12.74, 
        "circuits":         8.44,
        "mecanique":        13.01,
        
        # -- SEMESTRE 2 --
        "analyse2":         4.37,   
        "algebre2":         9.28,
        "algo2":            6.70,   
        "prog2":            12.40,  
        "thermo":           10.50,
        "sys logique":      10.30,
        "electronique":     8.90
    }

    IMI_2023_AVERAGES = {
        # -- SEMESTRE 1 --
        "analyse1":         8.74,
        "algebre1":         7.28,
        "algo1":            8.69,
        "prog1":            11.95,   
        "circuits":         9.59,
        "mecanique":        10.00,

        # -- SEMESTRE 2 --
        "analyse2":         5.79,
        "algebre2":         8.31,
        "algo2":            10.01,
        "prog2":            12.43,
        "electronique":     9.97,
        "thermo":           8.56,
        "sys logique":      10.37,
        
    }


    IMI_MATIERE_SEMESTER_MAP = {
        # -- SEMESTRE 1 --
        "analyse1":         1,
        "algebre1":         1,
        "algo1":            1,
        "prog1":            1,
        "circuits":         1,
        "mecanique":        1,
    

        # -- SEMESTRE 2 --
        "analyse2":         2,
        "algebre2":         2,
        "algo2":            2,
        "prog2":            2,
        "thermo":           2,
        "sys logique":      2,
        "electronique":     2
        
    }



    def build_spider_chart_for_imi_spider(self, user_student):

        # Decide which matieres to show on the spider
        matiere_order = [
            "analyse1","algebre1","algo1","prog1",
            "circuits","mecanique",
            

            "analyse2","algebre2","algo2","prog2",
            "thermo","sys logique","electronique",
            
        ]

        if self.theme == "light":
            text_color = QColor("#000000")
            bg_color   = QColor("#ffffff")
            plot_bg_color = QColor("#f0f0f0")
        else:
            text_color = QColor("#ffffff")
            bg_color   = QColor("#1f1f1f")
            plot_bg_color = QColor("#444444")

        def get_student_final(u_stud, mat):
            sem = self.IMI_MATIERE_SEMESTER_MAP.get(mat, 1)
            if sem == 1:
                final_val = u_stud['grades_s1'].get(mat, {}).get('Final')
            else:
                final_val = u_stud['grades_s2'].get(mat, {}).get('Final')
            return float(final_val) if final_val is not None else 0.0

        series_2022 = QLineSeries()
        series_2022.setName("2022 Avg")
        pen_2022 = QPen(QColor("#e53935"))  # red
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        series_2023 = QLineSeries()
        series_2023.setName("2023 Avg")
        pen_2023 = QPen(QColor("#1e88e5"))  # blue
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        series_user = QLineSeries()
        series_user.setName("Student")
        pen_user = QPen(QColor("#43a047"))  # green
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        n = len(matiere_order)
        angle_step = 360.0 / n

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            val_2022  = self.IMI_2022_AVERAGES.get(mat, 0.0)
            val_2023  = self.IMI_2023_AVERAGES.get(mat, 0.0)
            val_user  = get_student_final(user_student, mat)

            series_2022.append(angle_deg, val_2022)
            series_2023.append(angle_deg, val_2023)
            series_user.append(angle_deg, val_user)

        # Close the polygons
        series_2022.append(series_2022.at(0).x(), series_2022.at(0).y())
        series_2023.append(series_2023.at(0).x(), series_2023.at(0).y())
        series_user.append(series_user.at(0).x(), series_user.at(0).y())

        chart = QPolarChart()
        chart.setTitle("\n\nSpider Chart (IMI): 2022 vs 2023 vs You")
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setBackgroundRoundness(0)
        chart.setBackgroundBrush(bg_color)
        chart.setPlotAreaBackgroundBrush(plot_bg_color)
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setTitleBrush(text_color)
        chart.legend().setLabelColor(text_color)

        radial_axis = QValueAxis()
        radial_axis.setRange(0, 20)
        radial_axis.setTickCount(5)
        radial_axis.setLabelFormat("%.0f")
        radial_axis.setLabelsColor(text_color)
        radial_axis.setGridLineVisible(True)
        radial_axis.setMinorTickCount(0)
        radial_axis.setTitleText("")

        angular_axis = QCategoryAxis()
        angular_axis.setLabelsColor(text_color)
        angular_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        angular_axis.setGridLineVisible(True)

        for i, mat in enumerate(matiere_order):
            angle_deg = i * angle_step
            if mat == "analyse1":
                display_label = " electro|analyse1"
            else:
                display_label = mat
            angular_axis.append(display_label, angle_deg)
        angular_axis.append("", 360)

        chart.addAxis(radial_axis, QPolarChart.PolarOrientationRadial)
        chart.addAxis(angular_axis, QPolarChart.PolarOrientationAngular)

        for s in [series_2022, series_2023, series_user]:
            s.attachAxis(radial_axis)
            s.attachAxis(angular_axis)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view


    def build_imi_multi_line_chart_for_imi(self, user_student):

        matiere_order = [
            "analyse1","algebre1","algo1","prog1",
            "circuits","mecanique",
        

            "analyse2","algebre2","algo2","prog2",
            "thermo","sys logique","electronique",
            
        ]

        if self.theme == "dark":
            text_color = QColor("#ffffff")
        else:
            text_color = QColor("#000000")

        series_2022 = QLineSeries()
        series_2022.setName("2022 Average")
        pen_2022 = QPen(QColor("#e53935"))
        pen_2022.setWidth(3)
        series_2022.setPen(pen_2022)

        series_2023 = QLineSeries()
        series_2023.setName("2023 Average")
        pen_2023 = QPen(QColor("#1e88e5"))
        pen_2023.setWidth(3)
        series_2023.setPen(pen_2023)

        series_user = QLineSeries()
        series_user.setName("Student")
        pen_user = QPen(QColor("#43a047"))
        pen_user.setWidth(4)
        series_user.setPen(pen_user)

        series_2022.setPointsVisible(True)
        series_2023.setPointsVisible(True)
        series_user.setPointsVisible(True)

        def get_student_final(u_stud, mat):
            sem = self.IMI_MATIERE_SEMESTER_MAP.get(mat, 1)
            if sem == 1:
                final_val = u_stud['grades_s1'].get(mat, {}).get('Final')
            else:
                final_val = u_stud['grades_s2'].get(mat, {}).get('Final')
            return float(final_val) if final_val is not None else 0.0

        for i, mat in enumerate(matiere_order):
            avg_2022 = self.IMI_2022_AVERAGES.get(mat, 0.0)
            avg_2023 = self.IMI_2023_AVERAGES.get(mat, 0.0)
            stud_val = get_student_final(user_student, mat)

            series_2022.append(float(i), avg_2022)
            series_2023.append(float(i), avg_2023)
            series_user.append(float(i), stud_val)

        chart = QChart()
        chart.addSeries(series_2022)
        chart.addSeries(series_2023)
        chart.addSeries(series_user)
        chart.setTitle("IMI Orientation - Multi-Line Chart")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)

        chart.setBackgroundVisible(False)
        chart.setTitleBrush(QColor(text_color))
        chart.legend().setLabelColor(text_color)

        axisY = QValueAxis()
        axisY.setRange(0, 20)
        axisY.setTitleText("Grade")
        axisY.setLabelFormat("%.1f")
        axisY.setTickCount(6)
        axisY.setMinorTickCount(0)
        axisY.setLabelsColor(text_color)
        axisY.setTitleBrush(QColor(text_color))
        axisY.setGridLineVisible(True)
        axisY.setMinorGridLineVisible(False)
        chart.addAxis(axisY, Qt.AlignLeft)

        series_2022.attachAxis(axisY)
        series_2023.attachAxis(axisY)
        series_user.attachAxis(axisY)

        axisX = QCategoryAxis()
        axisX.setTitleText("Matières (IMI)")
        axisX.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        axisX.setLabelsColor(text_color)
        axisX.setTitleBrush(QColor(text_color))
        axisX.setGridLineVisible(True)
        axisX.setMinorGridLineVisible(False)
        axisX.setLabelsAngle(-20)

        for i, mat in enumerate(matiere_order):
            axisX.append(mat, float(i))
        axisX.setRange(0.0, float(len(matiere_order) - 0.5))

        chart.addAxis(axisX, Qt.AlignBottom)
        series_2022.attachAxis(axisX)
        series_2023.attachAxis(axisX)
        series_user.attachAxis(axisX)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view

    def setup_stats_detailed_tab(self):
        layout = QVBoxLayout(self.stats_detailed_tab)
        layout.setSpacing(20)
    
        self.stats_title_label = QLabel(self.tr("Statistics"))
        self.stats_title_label.setObjectName("SectionTitle")
        layout.addWidget(self.stats_title_label)
    
        # Check if user is MPI
        found_student = None
        if self.current_user:
            found_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )
        is_mpi = (found_student and found_student.get('section', '').lower() == 'mpi')
    
        # Only create carousel for MPI students
        if is_mpi:
            # --------- Carousel row  ---------
            carousel_layout = QHBoxLayout()
            carousel_layout.setContentsMargins(0,0,0,0)
            carousel_layout.setSpacing(20)
    
            self.prev_button = QPushButton("←")
            self.prev_button.setCursor(Qt.PointingHandCursor)
            self.prev_button.setFixedWidth(40)
            self.prev_button.clicked.connect(lambda: self.switch_chart_mode(forward=False))
    
            self.next_button = QPushButton("→")
            self.next_button.setCursor(Qt.PointingHandCursor)
            self.next_button.setFixedWidth(40)
            self.next_button.clicked.connect(lambda: self.switch_chart_mode(forward=True))
    
            self.carousel_label = QLabel(self.chart_mode)
            f_ = self.carousel_label.font()
            f_.setPointSize(13)
            f_.setBold(True)
            self.carousel_label.setFont(f_)
    
            carousel_layout.addWidget(self.prev_button, alignment=Qt.AlignLeft)
            carousel_layout.addStretch()
            carousel_layout.addWidget(self.carousel_label, alignment=Qt.AlignCenter)
            carousel_layout.addStretch()
            carousel_layout.addWidget(self.next_button, alignment=Qt.AlignRight)
    
            layout.addLayout(carousel_layout)
    
            # Toggle spider chart layout
            toggle_layout = QHBoxLayout()
            toggle_layout.setContentsMargins(0, 0, 0, 0)
            toggle_layout.setSpacing(8)
    
            spider_label = QLabel("Spider Chart Mode")
            font_ = spider_label.font()
            font_.setPointSize(12)
            spider_label.setFont(font_)
    
            toggle_layout.addStretch()
            toggle_layout.addWidget(spider_label, alignment=Qt.AlignRight)
    
            self.spider_toggle_switch = ToggleSwitch(checked=self.show_spider_mode)
            self.spider_toggle_switch.toggled.connect(self.on_spider_toggled)
    
            toggle_layout.addWidget(self.spider_toggle_switch, alignment=Qt.AlignRight)
            layout.addLayout(toggle_layout)
    
        # Card for the chart (shown for all students)
        self.stats_chart_card = QFrame()
        self.stats_chart_card.setObjectName("CardWidget")
        card_layout = QVBoxLayout(self.stats_chart_card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)
        layout.addWidget(self.stats_chart_card)
    
    # Build initial chart
        self.refresh_stats_chart()

    def on_spider_toggled(self, checked):
        """Custom slot for the toggle switch signal."""
        self.show_spider_mode = checked
        self.refresh_stats_chart()
    



    ###############################################################################
    #                            SIMULATION CODE SECTION
    ###############################################################################

    

    def fix_comma_and_recalc(self, line_edit, row_idx):
        """
        1) Replace any commas with dots in the current text.
        2) Clamp the resulting value to [0..20.0].
        3) Recompute the simulation for row_idx.
        """
        text = line_edit.text()
        if ',' in text:
            # Replace commas with dots
            old_cursor = line_edit.cursorPosition()
            text = text.replace(',', '.')
            line_edit.setText(text)
            line_edit.setCursorPosition(old_cursor)

        self.clamp_grade_lineedit(line_edit)

        # recalc
        self.recalc_simulation(row_idx)

    def clamp_grade_lineedit(self, line_edit):
        """Clamps the text in line_edit to [0..20.0] if user typed something out of range."""
        txt = line_edit.text().strip()
        if not txt:
            return
        try:
            val = float(txt)
            if val > 20.0:
                line_edit.setText("20.0")
            elif val < 0.0:
                line_edit.setText("0.0")
        except ValueError:
            # If typed non-numeric, do nothing or clear
            pass

    def gather_matieres_for_simulation(self, user_student):
        """
        Return a list of (matiere_dict, semester) for matieres
        where the user does NOT yet have an 'Exam' in DB.
        """
        if not user_student:
            return []

        matieres_to_simulate = []
        # S1
        for mat_dict in self.matieres_s1:
            mat_name = mat_dict['name']
            exam_val = user_student['grades_s1'].get(mat_name, {}).get('Exam')
            if exam_val is None:
                matieres_to_simulate.append((mat_dict, 1))
        # S2
        for mat_dict in self.matieres_s2:
            mat_name = mat_dict['name']
            exam_val = user_student['grades_s2'].get(mat_name, {}).get('Exam')
            if exam_val is None:
                matieres_to_simulate.append((mat_dict, 2))

        return matieres_to_simulate


    def setup_stats_simulation_tab(self):
        """
        Setup the simulation tab with a table for the user to input grades
        and see the projected final average.
        """
        layout = QVBoxLayout(self.stats_simulation_tab)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 30, 20, 30)

        title_label = QLabel("Simulation: Predict Your Grades (S1 & S2)")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        user_student = None
        if self.current_user:
            user_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )
        if not user_student or (not self.matieres_s1 and not self.matieres_s2):
            warn_label = QLabel("No data available for simulation.")
            warn_label.setStyleSheet("color: red; font-size: 14px;")
            layout.addWidget(warn_label)
            return

        filtered_mat_list = self.gather_matieres_for_simulation(user_student)
        if not filtered_mat_list:
            warn_label = QLabel("No matieres left to simulate (Exam grades already exist).")
            warn_label.setStyleSheet("color: orange; font-size: 14px;")
            layout.addWidget(warn_label)
            return

        self.sim_table = QTableWidget()
        self.sim_table.setColumnCount(6)
        self.sim_table.setHorizontalHeaderLabels(["Matière", "Sem", "DS", "TP", "Exam", "Final"])
        self.sim_table.setRowCount(len(filtered_mat_list))
        self.sim_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sim_table.setShowGrid(False)

        self.sim_table.horizontalHeader().setSectionResizeMode(self.QHeaderView.Stretch)
        self.sim_table.verticalHeader().setSectionResizeMode(self.QHeaderView.ResizeToContents)
        self.sim_table.verticalHeader().setVisible(False)
        self.sim_table.setStyleSheet("""
            QTableWidget {
                margin-top: 10px;
                margin-bottom: 10px;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)

        for row_idx in range(len(filtered_mat_list)):
            self.sim_table.setRowHeight(row_idx, 44)

        self.sim_lineedits = {}

        validator = QDoubleValidator(0.0, 20.0, 2)
        validator.setNotation(self.QDoubleValidator.StandardNotation)
        locale_c = self.QLocale(self.QLocale.C)
        validator.setLocale(locale_c)

        for row_idx, (mat_dict, sem) in enumerate(filtered_mat_list):
            mat_name = mat_dict['name']
            has_tp = mat_dict['has_tp']

            #  Matière
            item_mat = QTableWidgetItem(mat_name)
            self.sim_table.setItem(row_idx, 0, item_mat)

            # Semester
            item_sem = QTableWidgetItem(str(sem))
            self.sim_table.setItem(row_idx, 1, item_sem)

            # DS input
            ds_edit = QLineEdit()
            ds_edit.setPlaceholderText("0 - 20")
            ds_edit.setValidator(validator)
            ds_edit.textChanged.connect(lambda _, le=ds_edit, r=row_idx: self.fix_comma_and_recalc(le, r))
            self.sim_table.setCellWidget(row_idx, 2, ds_edit)

            # TP input
            tp_edit = QLineEdit()
            if has_tp:
                tp_edit.setPlaceholderText("0 - 20")
                tp_edit.setValidator(validator)
                tp_edit.textChanged.connect(lambda _, le=tp_edit, r=row_idx: self.fix_comma_and_recalc(le, r))
            else:
                tp_edit.setPlaceholderText("-")
                tp_edit.setEnabled(False)
            self.sim_table.setCellWidget(row_idx, 3, tp_edit)

            # Exam input
            exam_edit = QLineEdit()
            exam_edit.setPlaceholderText("0 - 20")
            exam_edit.setValidator(validator)
            exam_edit.textChanged.connect(lambda _, le=exam_edit, r=row_idx: self.fix_comma_and_recalc(le, r))
            self.sim_table.setCellWidget(row_idx, 4, exam_edit)

            # Final (read-only)
            final_item = QTableWidgetItem("")
            final_item.setFlags(final_item.flags() & ~Qt.ItemIsEditable)
            self.sim_table.setItem(row_idx, 5, final_item)

            self.sim_lineedits[row_idx] = {
                "matiere": mat_dict,
                "semester": sem,
                "ds_edit": ds_edit,
                "tp_edit": tp_edit,
                "exam_edit": exam_edit,
                "final_item": final_item
            }

        layout.addWidget(self.sim_table)

        self.projected_avg_label = QLabel("Projected Overall Average: 0.00")
        self.projected_avg_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.projected_avg_label)

        self.orientation_thresholds = {
            "IMI": 10
        }
        self.orientation_label = QLabel("Orientation Eligibility: N/A")
        self.orientation_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.orientation_label)

        self.recalc_simulation(force_all_rows=True)


    def recalc_simulation(self, changed_row=None, force_all_rows=False):
        """
        Recalculate the simulation for all rows or just the changed row.
        """
        if not hasattr(self, 'sim_lineedits'):
            return

        total_weighted_sum = 0.0
        total_overall_weight = 0.0

        user_student = None
        if self.current_user:
            user_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )

        if user_student:
            # For Semester 1
            for mat in self.matieres_s1:
                mat_id_str = str(mat['id'])
                if not any(d["matiere"] == mat for d in self.sim_lineedits.values()):
                    real_final = user_student['grades_s1'].get(mat_id_str, {}).get('Final')
                    if real_final is not None:
                        total_weighted_sum += float(real_final) * mat['overall_weight']
                    total_overall_weight += mat['overall_weight']

            # For Semester 2
            for mat in self.matieres_s2:
                mat_id_str = str(mat['id'])
                if not any(d["matiere"] == mat for d in self.sim_lineedits.values()):
                    real_final = user_student['grades_s2'].get(mat_id_str, {}).get('Final')
                    if real_final is not None:
                        total_weighted_sum += float(real_final) * mat['overall_weight']
                    total_overall_weight += mat['overall_weight']

        for row_idx, row_data in self.sim_lineedits.items():
            mat_dict = row_data["matiere"]
            mat_id_str = str(mat_dict['id'])
            sem = row_data["semester"]
            has_tp = mat_dict['has_tp']

            ds_str = row_data["ds_edit"].text().strip()
            tp_str = row_data["tp_edit"].text().strip() if has_tp else ""
            exam_str = row_data["exam_edit"].text().strip()

            try:
                ds_val = float(ds_str) if ds_str else 0.0
            except:
                ds_val = 0.0
            try:
                tp_val = float(tp_str) if (tp_str and has_tp) else 0.0
            except:
                tp_val = 0.0
            try:
                exam_val = float(exam_str) if exam_str else 0.0
            except:
                exam_val = 0.0

            ds_w = mat_dict['weights_ds']
            tp_w = mat_dict['weights_tp'] if has_tp else 0.0
            exam_w = mat_dict['weights_exam']

            weighted_final = (ds_val * ds_w) + (tp_val * tp_w) + (exam_val * exam_w)
            weighted_final_rounded = round(weighted_final, 2)
            row_data["final_item"].setText(f"{weighted_final_rounded:.2f}")

            total_weighted_sum += weighted_final_rounded * mat_dict['overall_weight']
            total_overall_weight += mat_dict['overall_weight']

        projected_avg = 0.0
        if total_overall_weight > 0:
            projected_avg = total_weighted_sum / total_overall_weight
        self.projected_avg_label.setText(f"Projected Overall Average: {projected_avg:.2f}")

        # ---------- ORIENTATION CHECKS ----------
        user_mg = projected_avg

        # Compute average math grade (analyse1, analyse2, algebre1, algebre2)
        math_names = ["analyse1", "analyse2", "algebre1", "algebre2"]
        math_sum = 0.0
        for mn in math_names:
            math_sum += self._compute_user_final_or_simulated(mn)
        user_moy_math = math_sum / len(math_names) if math_names else 0.0

        # Compute average info grade: (2*algo1 + 2*algo2 + prog1 + prog2) / 6
        algo1_val = self._compute_user_final_or_simulated("algo1")
        algo2_val = self._compute_user_final_or_simulated("algo2")
        prog1_val = self._compute_user_final_or_simulated("prog1")
        prog2_val = self._compute_user_final_or_simulated("prog2")
        info_sum = 2 * algo1_val + 2 * algo2_val + prog1_val + prog2_val
        user_moy_info = info_sum / 6.0 if info_sum else 0.0

        # Get 'sys logique' grade
        user_sl = self._compute_user_final_or_simulated("sys logique")

        # Compute orientation scores using the formulas
        user_score_gl = self.compute_score_gl_for_user(user_mg, user_moy_math, user_moy_info, user_sl)
        user_score_rt = self.compute_score_rt_for_user(user_mg, user_moy_math, user_moy_info, user_sl)
        en_val = self._compute_user_final_or_simulated("electronique")
        circuit_val = self._compute_user_final_or_simulated("circuit")  
        user_score_iia = self.compute_score_iia_for_user(user_mg, user_moy_math, user_moy_info, user_sl, en_val, circuit_val)

        # Instead of a DB query we filter the loaded students to get MPI students (read the readme file for more details)
        mpi_students = [s for s in self.all_students_data if s.get('section', '').lower() == 'mpi']

        scores_for_mpi_GL = []
        scores_for_mpi_RT = []
        scores_for_mpi_IIA = []

        for student in mpi_students:
            if student['id'] == self.current_user['national_id']:
                mg = user_mg
            else:
                mg = self._compute_real_mg_for_student_dict(student)

            if mg > 10.0:
                a1 = self._compute_final_or_simulated_for_others(student, student, "analyse1")
                a2 = self._compute_final_or_simulated_for_others(student, student, "analyse2")
                al1 = self._compute_final_or_simulated_for_others(student, student, "algebre1")
                al2 = self._compute_final_or_simulated_for_others(student, student, "algebre2")
                math_val = (a1 + a2 + al1 + al2) / 4.0 if (a1 + a2 + al1 + al2) != 0 else 0.0

                algo1_ = self._compute_final_or_simulated_for_others(student, student, "algo1")
                algo2_ = self._compute_final_or_simulated_for_others(student, student, "algo2")
                prog1_ = self._compute_final_or_simulated_for_others(student, student, "prog1")
                prog2_ = self._compute_final_or_simulated_for_others(student, student, "prog2")
                info_val = (2 * algo1_ + 2 * algo2_ + prog1_ + prog2_) / 6.0 if (algo1_ + algo2_ + prog1_ + prog2_ != 0) else 0.0

                sl_val = self._compute_final_or_simulated_for_others(student, student, "sys logique")

                gl_score = self.compute_score_gl_for_user(mg, math_val, info_val, sl_val)
                scores_for_mpi_GL.append((student['id'], gl_score))

                rt_score = self.compute_score_rt_for_user(mg, math_val, info_val, sl_val)
                scores_for_mpi_RT.append((student['id'], rt_score))

                en_ = self._compute_final_or_simulated_for_others(student, student, "electronique")
                circ_ = self._compute_final_or_simulated_for_others(student, student, "circuit")
                iia_score = self.compute_score_iia_for_user(mg, math_val, info_val, sl_val, en_, circ_)
                scores_for_mpi_IIA.append((student['id'], iia_score))

        scores_for_mpi_GL.sort(key=lambda x: x[1], reverse=True)
        scores_for_mpi_RT.sort(key=lambda x: x[1], reverse=True)
        scores_for_mpi_IIA.sort(key=lambda x: x[1], reverse=True)
        
        # ---------- GL Orientation Check (Top 25%) ----------
        gl_result_str = "No"
        user_rank_gl = None
        if user_mg > 10:
            for i, (sid, score) in enumerate(scores_for_mpi_GL, start=1):
                if sid == self.current_user['national_id']:
                    user_rank_gl = i
                    break
            if user_rank_gl is not None:
                n_gl = len(scores_for_mpi_GL)
                top25 = (n_gl // 4) + (1 if n_gl % 4 else 0)
                if user_rank_gl <= top25:
                    gl_result_str = "OK"

        # ---------- RT Orientation Check (Top 50%) ----------
        rt_result_str = "No"
        user_rank_rt = None
        if user_mg > 10:
            for i, (sid, score) in enumerate(scores_for_mpi_RT, start=1):
                if sid == self.current_user['national_id']:
                    user_rank_rt = i
                    break
            if user_rank_rt is not None:
                n_rt = len(scores_for_mpi_RT)
                top50_rt = math.ceil(n_rt / 2)
                if user_rank_rt <= top50_rt:
                    rt_result_str = "OK"

        # ---------- IIA Orientation Check (Top 50% or auto-OK if GL/RT are OK) ----------
        iia_result_str = "No"
        if gl_result_str == "OK" or rt_result_str == "OK":
            iia_result_str = "OK"
        else:
            if user_mg > 10:
                user_rank_iia = None
                for i, (sid, score) in enumerate(scores_for_mpi_IIA, start=1):
                    if sid == self.current_user['national_id']:
                        user_rank_iia = i
                        break
                if user_rank_iia is not None:
                    n_iia = len(scores_for_mpi_IIA)
                    top50_iia = math.ceil(n_iia / 2)
                    if user_rank_iia <= top50_iia:
                        iia_result_str = "OK"

        # ---------- IMI Orientation Check (Threshold-based) ----------
        imi_result_str = "No"
        needed_avg_imi = self.orientation_thresholds["IMI"]
        if user_mg >= needed_avg_imi:
            imi_result_str = "OK"

        def color_ok_or_no(x):
            return f"<span style='color:#4CAF50;font-weight:bold;'>OK</span>" if x == "OK" else \
                f"<span style='color:#f44336;font-weight:bold;'>No</span>"

        gl_styled = color_ok_or_no(gl_result_str)
        rt_styled = color_ok_or_no(rt_result_str)
        iia_styled = color_ok_or_no(iia_result_str)
        imi_styled = color_ok_or_no(imi_result_str)

        final_html = " | ".join([
            f"GL: {gl_styled}",
            f"RT: {rt_styled}",
            f"IIA: {iia_styled}",
            f"IMI: {imi_styled}"
        ])
        styled_label = f"<b>Orientation Eligibility:</b> {final_html}"
        self.orientation_label.setTextFormat(Qt.RichText)
        self.orientation_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.orientation_label.setOpenExternalLinks(False)
        self.orientation_label.setText(styled_label)



    def _compute_final_or_simulated_for_others(self, user_db_obj, stud_dict, mat_id_str):
        """
        Compute the final for a given student based on the mat_id_str.
        If the student is the current user, use the simulated final.
        Otherwise, use the real final from the database.
        """
        if user_db_obj['id'] == self.current_user['id']:
            return self._compute_user_final_or_simulated(mat_id_str)
        else:
            # Use the real final from 'stud_dict'
            mat = next((m for m in (self.matieres_s1 + self.matieres_s2)
                        if str(m['id']) == mat_id_str), None)
            if not mat:
                return 0.0

            if mat['semester'] == 1:
                final_val = stud_dict['grades_s1'].get(mat_id_str, {}).get('Final')
            else:
                final_val = stud_dict['grades_s2'].get(mat_id_str, {}).get('Final')

            return float(final_val) if final_val else 0.0



    def _compute_real_mg_for_student_dict(self, stud_dict):
        """
        Compute the real MG for a given student dictionary.
        This function calculates the average based on the grades
        and weights of all matieres in both semesters.
        """
        total_sum = 0.0
        total_w = 0.0

        for mat in (self.matieres_s1 + self.matieres_s2):
            mat_id_str = str(mat['id'])
            w = mat['overall_weight']
            sem = mat['semester']

            if sem == 1:
                final_val = stud_dict['grades_s1'].get(mat_id_str, {}).get('Final')
            else:
                final_val = stud_dict['grades_s2'].get(mat_id_str, {}).get('Final')

            if final_val is not None:
                try:
                    fv = float(final_val)
                    total_sum += (fv * w)
                    total_w += w
                except ValueError:
                    pass

        if total_w == 0:
            return 0.0
        return round(total_sum / total_w, 2)


    def _compute_real_final_or_zero_dict(self, st_dict, mat_id_str, semester):
        """
        Helper used in rank calculations or simulation code.
        Returns the real final from st_dict, or 0 if none.
        """
        if not st_dict:
            return 0.0

        if semester == 1:
            final_val = st_dict['grades_s1'].get(mat_id_str, {}).get('Final')
        else:
            final_val = st_dict['grades_s2'].get(mat_id_str, {}).get('Final')

        if final_val is None:
            return 0.0
        try:
            return float(final_val)
        except:
            return 0.0


    def _compute_user_final_or_simulated(self, mat_id_str):
        """
        If user is simulating that matiere, use the simulated final.
        Otherwise, fallback to the real final in DB.
        'mat_id_str' must be str(mat['id']).
        """
        if not self.current_user:
            return 0.0

        if hasattr(self, 'sim_lineedits'):
            for row_data in self.sim_lineedits.values():
                if str(row_data["matiere"]["id"]) == mat_id_str:
                    txt_final = row_data["final_item"].text().strip()
                    try:
                        return float(txt_final)
                    except:
                        return 0.0

        stud_dict = next(
            (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
            None
        )
        if not stud_dict:
            return 0.0
        mat = next((m for m in (self.matieres_s1 + self.matieres_s2)
                    if str(m['id']) == mat_id_str), None)
        if not mat:
            return 0.0

        if mat['semester'] == 1:
            f_val = stud_dict['grades_s1'].get(mat_id_str, {}).get('Final')
        else:
            f_val = stud_dict['grades_s2'].get(mat_id_str, {}).get('Final')

        if f_val is None:
            return 0.0
        return float(f_val)



    def compute_score_gl_for_user(self, mg_value, math_mean, info_mean, sl_value):
        """
        Formula for GL:
        GL Score = 2.0 * mg_value + math_mean + 2.0 * info_mean + sl_value
        """
        return 2.0 * mg_value + math_mean + 2.0 * info_mean + sl_value


    def compute_score_rt_for_user(self, mg_value, math_mean, info_mean, sl_value):
        """
        Formula for RT:
        RT Score = 2.0 * mg_value + math_mean + 1.0 * info_mean + sl_value
        """
        return 2.0 * mg_value + math_mean + 1.0 * info_mean + sl_value
    def compute_score_iia_for_user(self, mg_value, math_mean, info_mean, sl_value, en_value, circuit_value):
        """
        Formula for IIA:
        IIA = 2 * MG + math_mean + info_mean + sl_value + ((en_value + circuit_value) / 2)
        """
        return (2.0 * mg_value) + math_mean + info_mean + sl_value + ((en_value + circuit_value) / 2.0)


    def setup_stats_ai_advice_tab(self):
        # Create the main layout for the tab
        layout = QVBoxLayout(self.stats_ai_advice_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.ai_advice_card = QFrame()
        self.ai_advice_card.setObjectName("AiAdviceCard")
        card_layout = QVBoxLayout(self.ai_advice_card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.ai_advice_title_label = QLabel("AI Advice / Report")
        
        self.ai_advice_beta_text_label = QLabel("BETA")

        top_row.addWidget(self.ai_advice_title_label, alignment=Qt.AlignVCenter)
        
        top_row.addWidget(self.ai_advice_beta_text_label, alignment=Qt.AlignVCenter)
        top_row.addStretch()
        card_layout.addLayout(top_row)

        # Text box for the AI advice
        self.ai_advice_text = QTextEdit()
        self.ai_advice_text.setReadOnly(True)
        card_layout.addWidget(self.ai_advice_text)

        # Load the student's AI report immediately (if any)
        self.load_student_ai_report()

        # Put the card into the tab layout
        layout.addWidget(self.ai_advice_card)


    def load_student_ai_report(self):
        """
        Loads the AI-generated report using the API and updates the AI Advice section.
        """
        if not self.current_user:
            self.ai_advice_text.setPlainText("No user is logged in.")
            return

        student_id = self.current_user.get('national_id')
        if not student_id:
            self.ai_advice_text.setPlainText("Student ID not found.")
            return

        # Use the API function with auth token
        ai_report = get_student_ai_report(student_id, bearer_token=self.auth_token)
        if ai_report:
            self.ai_advice_text.setPlainText(ai_report)
        else:
            self.ai_advice_text.setPlainText("The report has not been generated yet, please come back later.")


    def refresh_ai_advice_tab_style(self):
        """Reapply dark/light colors and icons for the AI Advice card."""

        if self.theme == 'dark':
            card_bg      = "#2C2C2C"
            border_color = "#444444"
            textedit_bg  = "#333333"
            textedit_fg  = "#DDDDDD"
            title_fg     = "#FFFFFF"
            beta_fg      = "#FFD54F"
        else:
            card_bg      = "#F2F2F2"
            border_color = "#CCCCCC"
            textedit_bg  = "#FFFFFF"
            textedit_fg  = "#333333"
            title_fg     = "#111111"
            beta_fg      = "#FF9800"

        self.ai_advice_card.setStyleSheet(f"""
            QFrame#AiAdviceCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
        """)

        self.ai_advice_title_label.setStyleSheet(
            f"color: {title_fg}; font-weight: 600;"
        )

        self.ai_advice_beta_text_label.setStyleSheet(
            f"color: {beta_fg}; font-weight: bold;"
        )
        self.ai_advice_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {textedit_bg};
                color: {textedit_fg};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 8px;
            }}
        """)

        self.ai_advice_card.update()

    
    def compute_rank_progress(self):
        """
        Gathers rank data for DS1, Final1, DS2, Final2 – always displays them.
        If user has no data for an event but others do => user gets lowest rank.
        If nobody in the section has data => rank = 0.
        """

        if not self.current_user:
            return []

        user_student = next(
            (s for s in self.all_students_data 
            if s['id'] == self.current_user['national_id']), 
            None
        )
        if not user_student or not user_student.get('section'):
            return []

        section_students = [
            st for st in self.all_students_data
            if st.get('section') == user_student['section']
        ]

        events = [
            ("DS1", 1, "DS"),
            ("Final1", 1, "Final"),
            ("DS2", 2, "DS"),
            ("Final2", 2, "Final"),
        ]

        rank_data = []

        for (label, sem, key) in events:
            user_sum = self._compute_sum_for_event(user_student, sem, key)
            
            rank_val = self._compute_rank_for_event(user_student, section_students, sem, key)

            if rank_val is None:
                
                rank_val =  len(section_students)

            rank_data.append((label, rank_val))

        return rank_data



    def build_rank_line_chart(self):
        rank_data = self.compute_rank_progress()
        if not rank_data:
            # If there's no data to display at all, show a placeholder chart
            empty_chart = QChart()
            empty_chart.setTitle(self.tr("No Rank Data Available"))
            chart_view = QChartView(empty_chart)
            chart_view.setRenderHint(QPainter.Antialiasing)
            chart_view.setStyleSheet("background: transparent;")
            return chart_view

        series = QLineSeries()
        series.setName(self.tr("Student Rank"))

        for i, (label, rank_val) in enumerate(rank_data):
            series.append(float(i), float(rank_val))

        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setBackgroundBrush(Qt.transparent)
        chart.setPlotAreaBackgroundVisible(False)
        chart.legend().hide()

        chart.addSeries(series)
        chart.setTitle(self.tr("Rank Over Time"))

        if self.theme == 'light':
            axis_color = QColor("#000000")
            label_color = QColor("#000000")
        else:
            axis_color = QColor("#ffffff")
            label_color = QColor("#ffffff")

        chart.setTitleBrush(QBrush(label_color))

        self.axisY = QValueAxis()
        self.axisY.setLabelFormat("%d")
        self.axisY.setTitleText(self.tr("Rank"))
        self.axisY.setReverse(True)  # rank=1 at the top
        self.axisY.setGridLineVisible(False)
        self.axisY.setMinorGridLineVisible(False)
        self.axisY.setLinePen(QPen(axis_color))
        self.axisY.setLabelsColor(label_color)
        self.axisY.setTitleBrush(QBrush(label_color))

        all_ranks = [rd[1] for rd in rank_data]
        min_rank = int(min(all_ranks))
        max_rank = int(max(all_ranks))

        if min_rank == max_rank:
            min_rank -= 1
            max_rank += 1
            if min_rank < 0:
                min_rank = 0

        self.axisY.setRange(min_rank, max_rank)

        total_range = max_rank - min_rank
        if total_range < 1:
            total_range = 1  # avoid division by zero

        raw_tick_count = total_range + 1

        max_desired_ticks = 10
        if raw_tick_count > max_desired_ticks:
            self.axisY.setTickCount(max_desired_ticks)
        else:
            self.axisY.setTickCount(raw_tick_count)

        self.axisY.setMinorTickCount(0)

        chart.addAxis(self.axisY, Qt.AlignLeft)
        series.attachAxis(self.axisY)

        self.catAxisX = QCategoryAxis()
        self.catAxisX.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        self.catAxisX.setGridLineVisible(False)
        self.catAxisX.setMinorGridLineVisible(False)
        self.catAxisX.setLinePen(QPen(axis_color))
        self.catAxisX.setLabelsColor(label_color)

        self.catAxisX.setStartValue(0)
        for i, (label, _) in enumerate(rank_data):
            self.catAxisX.append(label, i)
        self.catAxisX.setRange(0, len(rank_data) - 1)

        chart.addAxis(self.catAxisX, Qt.AlignBottom)
        series.attachAxis(self.catAxisX)

        pen = QPen(QColor("#ff9800"))
        pen.setWidth(3)
        series.setPen(pen)
        series.setPointsVisible(True)
        series.setPointLabelsVisible(False)
        series.setPointLabelsColor(label_color)
        series.setPointLabelsFormat("@yPoint")

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent;")
        return chart_view
    
    def _compute_sum_for_event(self, student_dict, semester, key):
        """
        Computes the sum of grades for a given event (DS or Final) in the specified semester.
        Returns 0.0 if no grades found.
        """
        if semester == 1:
            grades_dict = student_dict['grades_s1']
            matieres_in_sem = self.matieres_s1
        else:
            grades_dict = student_dict['grades_s2']
            matieres_in_sem = self.matieres_s2

        total_val = 0.0
        found_any = False

        for mat in matieres_in_sem:
            mat_id_str = str(mat['id'])
            val = grades_dict.get(mat_id_str, {}).get(key, None)
            if val is not None:
                found_any = True
                total_val += float(val)

        if not found_any:
            return 0.0
        return total_val




    def _compute_rank_for_event(self, user_student, section_students, semester, key):
        """
        Computes the rank of the user for a given event (DS or Final) in the specified semester.
        Returns None if the user has no data for that event.
        """
        user_sum = self._compute_sum_for_event(user_student, semester, key)
        if user_sum <= 0:
            return None

        scores_section = []
        for st in section_students:
            val = self._compute_sum_for_event(st, semester, key)
            scores_section.append((st['id'], val))

        scores_section.sort(key=lambda x: x[1], reverse=True)
        rank_val = None
        current_rank = 0
        last_score = None
        used_position = 0

        for (sid, sc) in scores_section:
            used_position += 1
            if sc != last_score:
                current_rank = used_position
            if sid == user_student['id']:
                rank_val = current_rank
                break
            last_score = sc

        return rank_val
    # -------------------------------------------------------------------------
    #                           MATIERE PAGE
    # -------------------------------------------------------------------------
    def setup_matiere_page(self):
        """
        Setup the matiere page with a table to display matieres and grades.
        """
        self.matiere_label = QLabel()
        self.matiere_label.setObjectName("SectionTitle")
        self.matiere_label.setText("Matières and Grades")
        matiere_layout = QVBoxLayout(self.matiere_page)
        matiere_layout.setContentsMargins(20, 20, 20, 20)
        matiere_layout.setSpacing(30)

        matiere_layout.addWidget(self.matiere_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        vbox = QVBoxLayout(container)

        self.matiere_table = QTableWidget()
        self.matiere_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        vbox.addWidget(self.matiere_table)
        scroll_area.setWidget(container)

        matiere_layout.addWidget(scroll_area)
    def populate_matiere_table(self):
        """
        Populate the matiere table with data from the current user.
        """
        if not hasattr(self, 'matiere_table'):
            return

        all_mat = [(m, 1) for m in self.matieres_s1] + [(m, 2) for m in self.matieres_s2]
        any_tp = any(m['has_tp'] for m, _ in all_mat)

        columns = ['Matiere', 'Semester', 'DS']
        if any_tp:
            columns.append('TP')
        columns += ['Exam', 'Final', 'Average DS']
        if any_tp:
            columns.append('Average TP')
        columns += ['Average Exam', 'Average Final', 'Rank']

        self.matiere_table.setColumnCount(len(columns))
        self.matiere_table.setHorizontalHeaderLabels(columns)
        self.matiere_table.setRowCount(len(all_mat))

        found_student = None
        if self.current_user:
            found_student = next(
                (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                None
            )

        current_section = found_student['section'] if found_student else None
        students_for_avg = [
            s for s in self.all_students_data
            if s.get('section') == current_section
        ]

        for i, (mat, sem) in enumerate(all_mat):
            mat_name = mat['name']
            mat_id_str = str(mat['id'])
            has_tp = mat['has_tp']

            # Gather DS/TP/Exam/Final across entire section
            mat_grades = {'DS': [], 'TP': [], 'Exam': [], 'Final': []}
            final_grades_with_ids = []

            for st in students_for_avg:
                if sem == 1:
                    g_dict = st['grades_s1'].get(mat_id_str, {})
                else:
                    g_dict = st['grades_s2'].get(mat_id_str, {})

                ds = g_dict.get('DS')
                tp = g_dict.get('TP') if has_tp else None
                exam = g_dict.get('Exam')
                final_ = g_dict.get('Final')

                if ds is not None:
                    mat_grades['DS'].append(float(ds))
                if tp is not None:
                    mat_grades['TP'].append(float(tp))
                if exam is not None:
                    mat_grades['Exam'].append(float(exam))
                if final_ is not None:
                    f_ = float(final_)
                    mat_grades['Final'].append(f_)
                    final_grades_with_ids.append((st['id'], f_))

            # Average
            def safe_avg(vals):
                return round(sum(vals)/len(vals), 2) if vals else '-'
            ds_avg = safe_avg(mat_grades['DS'])
            tp_avg = safe_avg(mat_grades['TP']) if has_tp else '-'
            exam_avg = safe_avg(mat_grades['Exam'])
            final_avg = safe_avg(mat_grades['Final'])

            # For current user
            if found_student and final_grades_with_ids:
                if sem == 1:
                    user_g_dict = found_student['grades_s1'].get(mat_id_str, {})
                else:
                    user_g_dict = found_student['grades_s2'].get(mat_id_str, {})

                ds_grade = user_g_dict.get('DS')
                tp_grade = user_g_dict.get('TP') if has_tp else '-'
                exam_grade = user_g_dict.get('Exam')
                final_grade = user_g_dict.get('Final')

                ds_grade = round(float(ds_grade), 2) if ds_grade else '-'
                if has_tp and tp_grade not in [None, '-']:
                    tp_grade = round(float(tp_grade), 2)
                exam_grade = round(float(exam_grade), 2) if exam_grade else '-'
                final_grade = round(float(final_grade), 2) if final_grade else '-'

                # Compute rank
                if final_grade != '-':
                    # Sort final desc
                    sorted_final = sorted(final_grades_with_ids, key=lambda x: x[1], reverse=True)
                    rank = None
                    current_rank = 0
                    used_position = 0
                    last_val = None
                    for (sid, fv) in sorted_final:
                        used_position += 1
                        if fv != last_val:
                            current_rank = used_position
                        if sid == found_student['id']:
                            rank = current_rank
                            break
                        last_val = fv
                else:
                    rank = '-'
            else:
                ds_grade = '-'
                tp_grade = '-'
                exam_grade = '-'
                final_grade = '-'
                rank = '-'

            col_index = 0
            self.matiere_table.setItem(i, col_index, QTableWidgetItem(mat_name))
            col_index += 1
            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(sem)))
            col_index += 1
            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(ds_grade)))
            col_index += 1

            if any_tp:
                self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(tp_grade)))
                col_index += 1

            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(exam_grade)))
            col_index += 1
            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(final_grade)))
            col_index += 1

            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(ds_avg)))
            col_index += 1

            if any_tp:
                self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(tp_avg)))
                col_index += 1

            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(exam_avg)))
            col_index += 1
            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(final_avg)))
            col_index += 1

            self.matiere_table.setItem(i, col_index, QTableWidgetItem(str(rank)))

        self.matiere_table.resizeColumnsToContents()

    # -------------------------------------------------------------------------
    #                           NOTIFICATIONS PAGE
    # -------------------------------------------------------------------------
    def setup_notifications_page(self):
        notifs_layout = QVBoxLayout(self.notif_page)
        notifs_layout.setContentsMargins(20, 20, 20, 20)
        notifs_layout.setSpacing(20)
        notifs_layout.setAlignment(Qt.AlignTop)

        self.notif_label = QLabel(self.tr("notifications"))
        self.notif_label.setObjectName("SectionTitle") 
        notifs_layout.addWidget(self.notif_label)       

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        self.notif_layout = QVBoxLayout(container)
        self.notif_layout.setSpacing(20)
        self.notif_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(container)

        notifs_layout.addWidget(scroll_area)

    def show_notifications_page(self):
        """
        Show the notifications page and load notifications from the API.
        """
        if not self.current_user:
            QMessageBox.warning(self, "Not Logged In", "Please log in first.")
            return

        user_id = self.current_user['id']

        try:
            notifications_result = get_notifications(user_id, bearer_token=self.auth_token)
            if isinstance(notifications_result, list):
                self.load_user_notifications_cards(notifications_result)
            elif isinstance(notifications_result, dict) and notifications_result.get("success"):
                notifications = notifications_result.get("notifications", [])
                self.load_user_notifications_cards(notifications)
            else:
                err_msg = "Unknown error"
                if isinstance(notifications_result, dict):
                    err_msg = notifications_result.get("message", err_msg)
                QMessageBox.critical(self, "Error loading notifications", err_msg)
                self.load_user_notifications_cards([])
        except Exception as e:
            QMessageBox.critical(self, "Error loading notifications", str(e))
            self.load_user_notifications_cards([])

        self.main_stack.setCurrentWidget(self.notif_page)



    def load_user_notifications_cards(self, notifications):
        while self.notif_layout.count():
            item = self.notif_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not notifications:
            empty_label = QLabel(self.tr("No new notifications yet."))
            empty_label.setStyleSheet("font-size: 24px; color: gray;")
            self.notif_layout.addWidget(empty_label, alignment=Qt.AlignCenter)
        else:
            for n in notifications:
                card = QFrame()
                card.setObjectName("NotificationCard")
                c_layout = QVBoxLayout(card)
                c_layout.setSpacing(5)
                c_layout.setContentsMargins(10, 10, 10, 10)

                title_label = QLabel(n.get("title", ""))
                title_label.setObjectName("NotificationTitle")
                body_label = QLabel(n.get("body", ""))
                body_label.setObjectName("NotificationBody")

                date_str = n.get("date", "")
                try:
                    dt = datetime.fromisoformat(date_str)
                    date_label = QLabel(dt.strftime("%Y-%m-%d %H:%M"))
                except Exception:
                    date_label = QLabel(date_str)
                date_label.setObjectName("NotificationDate")

                c_layout.addWidget(title_label)
                c_layout.addWidget(body_label)
                c_layout.addWidget(date_label, alignment=Qt.AlignRight)

                self.notif_layout.addWidget(card)
        self.notif_layout.addStretch()

    # -------------------------------------------------------------------------
    #                           RECLAMATION PAGE
    # -------------------------------------------------------------------------
    def setup_reclamation_page(self):
        """
        Setup the reclamation page with a form to submit reclamations.
        """
        rec_layout = QVBoxLayout(self.reclamation_page)
        rec_layout.setContentsMargins(20, 20, 20, 20)
        rec_layout.setSpacing(20)

        self.reclam_label = QLabel()
        self.reclam_label.setObjectName("SectionTitle")
        rec_layout.addWidget(self.reclam_label)

        form_layout = QFormLayout()
        self.reclamation_type_box = QComboBox()
        self.reclamation_desc = QTextEdit()

        self.reclamation_type_label = QLabel()
        self.description_label = QLabel()

        form_layout.addRow(self.reclamation_type_label, self.reclamation_type_box)
        form_layout.addRow(self.description_label, self.reclamation_desc)

        self.btn_submit_reclam = QPushButton(self.tr("Submit Reclamation"))
        self.btn_submit_reclam.setCursor(Qt.PointingHandCursor)
        self.btn_submit_reclam.clicked.connect(self.submit_reclamation)

        self.btn_view_own_reclam = QPushButton(self.tr("View My Reclamations"))
        self.btn_view_own_reclam.setCursor(Qt.PointingHandCursor)
        self.btn_view_own_reclam.clicked.connect(self.view_own_reclamations)

        rec_layout.addLayout(form_layout)
        rec_layout.addWidget(self.btn_submit_reclam)
        rec_layout.addWidget(self.btn_view_own_reclam)

        self.reclamation_type_box.addItems([self.tr("wrong_grade"), self.tr("missing_grade"), self.tr("other")])

    def submit_reclamation(self):
        """
        Submit the reclamation form to the API.
        """
        if not self.current_user:
            QMessageBox.warning(self, self.tr("Not Logged In"), "Please log in first.")
            return

        if self.system_status == "offline":
            QMessageBox.critical(self, self.tr("No Internet"), self.tr("reset_internet"))
            return

        desc = self.reclamation_desc.toPlainText().strip()
        r_type = self.reclamation_type_box.currentText()

        if not desc:
            QMessageBox.warning(self, self.tr("Empty"), "Please enter a description.")
            return

        result = submit_reclamation(
            user_id=self.current_user['id'],
            reclamation_type=r_type,
            description=desc,
            bearer_token=self.auth_token 
        )
        if result.get("success"):
            QMessageBox.information(self, self.tr("Submitted"), "Your reclamation has been submitted.")
            self.reclamation_desc.clear()

            user_result = get_user(self.current_user['id'], bearer_token=self.auth_token)
            if user_result.get("success"):
                user_db = user_result.get("user")
            else:
                user_db = None

            if user_db:
                student_email = user_db.get("email", self.current_user["email"])
                student_section = user_db.get("section", self.current_user.get("section", "unknown"))
            else:
                student_email = self.current_user.get("email", "Unknown")
                student_section = self.current_user.get("section", "Unknown")

            subject = f"New Reclamation from {student_email}"
            body_lines = [
                "Hello Admin,",
                "",
                f"You have a new reclamation from: {student_email}",
                f"Section: {student_section}",
                f"Type: {r_type}",
                f"Description: {desc}",
                "",
                "Best Regards,",
                "Student Grades System"
            ]
            body = "\n".join(body_lines)

            send_email(
                to="example@mail.com",#email of admin 
                subject=subject,
                body=body,
                bearer_token=self.auth_token
            )

        else:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                f"Failed to submit reclamation: {result.get('message', '')}"
            )
    def view_own_reclamations(self):
        """
        View the user's own reclamations in a dialog.
        """
        if not self.current_user:
            QMessageBox.warning(self, "Not Logged In", "Please log in first.")
            return

        reclamations_data = get_reclamations(
            user_id=self.current_user['id'],
            bearer_token=self.auth_token  
        )
        if not reclamations_data:
            QMessageBox.information(self, self.tr("No Reclamations"),
                "You didn't send any reclamations or all your reclamations were solved.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("My Reclamations")
        dialog.setFixedSize(900, 500)
        layout = QVBoxLayout(dialog)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['ID', 'Type', 'Description', 'Timestamp', 'Status'])
        table.setRowCount(len(reclamations_data))

        for row, rec in enumerate(reclamations_data):
            table.setItem(row, 0, QTableWidgetItem(str(rec.get("id"))))
            table.setItem(row, 1, QTableWidgetItem(rec.get("reclamation_type", "")))
            table.setItem(row, 2, QTableWidgetItem(rec.get("description", "")))
            ts = rec.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                ts_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_str = ts
            table.setItem(row, 3, QTableWidgetItem(ts_str))
            status_text = "Solved" if rec.get("is_solved") else "Pending"
            table.setItem(row, 4, QTableWidgetItem(status_text))

        table.resizeColumnsToContents()
        layout.addWidget(table)
        dialog.exec_()

    # -------------------------------------------------------------------------
    #                           SETTINGS PAGE
    # -------------------------------------------------------------------------
    def setup_settings_page(self):
        set_layout = QVBoxLayout(self.settings_page)
        set_layout.setContentsMargins(20, 20, 20, 20)
        set_layout.setSpacing(20)
        set_layout.setAlignment(Qt.AlignTop)

        self.settings_label = QLabel()
        self.settings_label.setObjectName("SectionTitle")
        set_layout.addWidget(self.settings_label, alignment=Qt.AlignTop)

        self.settings_card = QFrame()
        self.settings_card.setObjectName("SettingsCard")
        sc_layout = QVBoxLayout(self.settings_card)
        sc_layout.setContentsMargins(20, 20, 20, 20)
        sc_layout.setSpacing(25)  
        font_label = QLabel()
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setMinimum(8)
        self.font_slider.setMaximum(24)
        self.font_slider.setValue(self.app_config.get('font_size', 10))
        self.font_slider.setTickPosition(QSlider.TicksBelow)
        self.font_slider.setTickInterval(1)

        self.font_size_value_label = QLabel(str(self.font_slider.value()))
        self.font_slider.valueChanged.connect(lambda val: self.font_size_value_label.setText(str(val)))

        font_h_layout = QHBoxLayout()
        font_h_layout.addWidget(font_label)
        font_h_layout.addWidget(self.font_slider)
        font_h_layout.addWidget(self.font_size_value_label)
        theme_label = QLabel()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(self.tr("Dark"))
        self.theme_combo.addItem(self.tr("Light"))
        if self.theme == 'dark':
            self.theme_combo.setCurrentIndex(0)
        else:
            self.theme_combo.setCurrentIndex(1)

        self.notifications_checkbox = QCheckBox()
        if self.current_user:
            user_data = get_user(self.current_user['id'])
            if user_data:
                self.notifications_checkbox.setChecked(user_data.get("subscribed_to_notifications", False))

        def toggle_notifications():
            if self.current_user:
                result = update_notifications(self.current_user['id'], self.notifications_checkbox.isChecked())
                if not result.get("success"):
                    QMessageBox.warning(self, self.tr("Error"), "Failed to update notification settings: " + result.get("message", ""))

        self.notifications_checkbox.clicked.connect(toggle_notifications)

        self.btn_save_settings = QPushButton()
        self.btn_save_settings.setCursor(Qt.PointingHandCursor)
        self.btn_save_settings.clicked.connect(self.save_user_settings)

        sc_layout.addLayout(font_h_layout)
        sc_layout.addWidget(theme_label)
        sc_layout.addWidget(self.theme_combo)
        sc_layout.addWidget(self.notifications_checkbox)
        sc_layout.addWidget(self.btn_save_settings, alignment=Qt.AlignCenter)

        self.settings_font_label = font_label
        self.settings_theme_label = theme_label

        set_layout.addWidget(self.settings_card, alignment=Qt.AlignTop)


    def save_user_settings(self):
        new_font_size = self.font_slider.value()
        new_theme = 'dark' if self.theme_combo.currentIndex() == 0 else 'light'
        self.app_config['font_size'] = new_font_size
        self.app_config['theme'] = new_theme

        lang_map = {0: 'en', 1: 'fr', 2: 'ar'}
        new_lang = lang_map.get(self.lang_combo.currentIndex(), 'en')
        self.app_config['language'] = new_lang
        self.current_language = new_lang

        with open(resource_path('config.json'), 'w') as f:
            json.dump(self.app_config, f)

        font = QFont("Maven Pro", new_font_size)
        QApplication.instance().setFont(font)

        self.set_theme(new_theme)
        self.animate_theme_change(new_theme)
        self.refresh_stats_chart()
        self.apply_translations()
        self.update_footer_html()
        self.populate_dashboard_chart()
        QMessageBox.information(self.settings_page, self.tr("Saved"), "Settings saved successfully.")

    # -------------------------------------------------------------------------
    #                           PROFILE PAGE
    # -------------------------------------------------------------------------
    def setup_profile_page(self):
        profile_layout = QVBoxLayout(self.profile_page)
        profile_layout.setContentsMargins(20, 20, 20, 20)
        profile_layout.setSpacing(20)
        profile_layout.setAlignment(Qt.AlignTop)

        self.profile_label = QLabel()
        self.profile_label.setObjectName("SectionTitle")
        profile_layout.addWidget(self.profile_label, alignment=Qt.AlignTop | Qt.AlignHCenter)
        profile_card = QFrame()
        profile_card.setObjectName("ProfileCard")
        pc_layout = QVBoxLayout(profile_card)
        pc_layout.setContentsMargins(20, 20, 20, 20)
        pc_layout.setSpacing(20)

        info_text = f"Email: {self.current_user['email']}" if self.current_user else "No user info"
        self.profile_info_label = QLabel(info_text)
        pc_layout.addWidget(self.profile_info_label, alignment=Qt.AlignTop | Qt.AlignCenter)

        self.pic_btn = QPushButton()
        self.pic_btn.setCursor(Qt.PointingHandCursor)
        self.pic_btn.setObjectName("ProfilePicButton")
        self.pic_btn.clicked.connect(self.change_profile_picture)

        self.profile_pic_label = QLabel()
        self.profile_pic_label.setAlignment(Qt.AlignCenter)

        user_data = None
        if self.current_user:
            user_data = get_user(self.current_user['id'])
        pic_path_db = user_data.get("profile_pic_url") if user_data else None

        if pic_path_db:
            if pic_path_db.startswith("http"):
                loaded_pix = self.load_pixmap_from_url(pic_path_db)
                if loaded_pix:
                    self.profile_pic_label.setPixmap(
                        loaded_pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                else:
                    self.profile_pic_label.setPixmap(
                        QPixmap(resource_path("resources/user.svg")).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
            else:
                if os.path.exists(pic_path_db):
                    self.profile_pic_label.setPixmap(
                        QPixmap(pic_path_db).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                else:
                    self.profile_pic_label.setPixmap(
                       QPixmap(resource_path("resources/user.svg")).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
        else:
            self.profile_pic_label.setPixmap(
                QPixmap(resource_path("resources/user.svg")).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        pc_layout.addWidget(self.profile_pic_label, alignment=Qt.AlignCenter)
        pc_layout.addWidget(self.pic_btn, alignment=Qt.AlignCenter)

        pass_form = QFormLayout()

        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.Password)
        self.show_current_pass_btn = QToolButton(self.current_password_input)
        self.show_current_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
        )
        self.show_current_pass_btn.setCheckable(True)
        self.show_current_pass_btn.hide()
        self.show_current_pass_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 0 5px;
            }
        """)
        self.current_password_input.setStyleSheet("padding-right: 20px;")
        self.show_current_pass_btn.setCursor(Qt.PointingHandCursor)

        def toggle_current_pass_visibility():
            if self.show_current_pass_btn.isChecked():
                self.current_password_input.setEchoMode(QLineEdit.Normal)
                self.show_current_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.current_password_input.setEchoMode(QLineEdit.Password)
                self.show_current_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        def show_hide_current_eye(text):
            self.show_current_pass_btn.setVisible(bool(text))

        self.show_current_pass_btn.clicked.connect(toggle_current_pass_visibility)
        self.current_password_input.textChanged.connect(show_hide_current_eye)

        # --- New Password ---
        self.new_password_input_profile = QLineEdit()
        self.new_password_input_profile.setEchoMode(QLineEdit.Password)
        self.show_new_pass_btn = QToolButton(self.new_password_input_profile)
        self.show_new_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
        )
        self.show_new_pass_btn.setCheckable(True)
        self.show_new_pass_btn.hide()
        self.show_new_pass_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 0 5px;
            }
        """)
        self.new_password_input_profile.setStyleSheet("padding-right: 20px;")
        self.show_new_pass_btn.setCursor(Qt.PointingHandCursor)

        def toggle_new_pass_visibility():
            if self.show_new_pass_btn.isChecked():
                self.new_password_input_profile.setEchoMode(QLineEdit.Normal)
                self.show_new_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.new_password_input_profile.setEchoMode(QLineEdit.Password)
                self.show_new_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        def show_hide_new_eye(text):
            self.show_new_pass_btn.setVisible(bool(text))

        self.show_new_pass_btn.clicked.connect(toggle_new_pass_visibility)
        self.new_password_input_profile.textChanged.connect(show_hide_new_eye)

        # --- Confirm New Password ---
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.show_confirm_pass_btn = QToolButton(self.confirm_password_input)
        self.show_confirm_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
        )
        self.show_confirm_pass_btn.setCheckable(True)
        self.show_confirm_pass_btn.hide()
        self.show_confirm_pass_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 0 5px;
            }
        """)
        self.confirm_password_input.setStyleSheet("padding-right: 20px;")
        self.show_confirm_pass_btn.setCursor(Qt.PointingHandCursor)

        def toggle_confirm_pass_visibility():
            if self.show_confirm_pass_btn.isChecked():
                self.confirm_password_input.setEchoMode(QLineEdit.Normal)
                self.show_confirm_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.confirm_password_input.setEchoMode(QLineEdit.Password)
                self.show_confirm_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        def show_hide_confirm_eye(text):
            self.show_confirm_pass_btn.setVisible(bool(text))

        self.show_confirm_pass_btn.clicked.connect(toggle_confirm_pass_visibility)
        self.confirm_password_input.textChanged.connect(show_hide_confirm_eye)

        def resizeEvent(event):
            buttonSize = self.show_current_pass_btn.sizeHint()
            self.show_current_pass_btn.move(
                self.current_password_input.width() - buttonSize.width() - 5,
                (self.current_password_input.height() - buttonSize.height()) // 2
            )
            self.show_new_pass_btn.move(
                self.new_password_input_profile.width() - buttonSize.width() - 5,
                (self.new_password_input_profile.height() - buttonSize.height()) // 2
            )
            self.show_confirm_pass_btn.move(
                self.confirm_password_input.width() - buttonSize.width() - 5,
                (self.confirm_password_input.height() - buttonSize.height()) // 2
            )

        self.current_password_input.resizeEvent = resizeEvent
        self.new_password_input_profile.resizeEvent = resizeEvent
        self.confirm_password_input.resizeEvent = resizeEvent

        self.profile_current_password_label = QLabel()
        self.profile_new_password_label = QLabel()
        self.profile_confirm_password_label = QLabel()

        pass_form.addRow(self.profile_current_password_label, self.current_password_input)
        pass_form.addRow(self.profile_new_password_label, self.new_password_input_profile)
        pass_form.addRow(self.profile_confirm_password_label, self.confirm_password_input)

        self.btn_change_pass = QPushButton()
        self.btn_change_pass.setCursor(Qt.PointingHandCursor)
        self.btn_change_pass.clicked.connect(self.change_user_password)

        pc_layout.addLayout(pass_form)
        pc_layout.addWidget(self.btn_change_pass, alignment=Qt.AlignCenter)
        profile_layout.addWidget(profile_card, alignment=Qt.AlignTop | Qt.AlignCenter)

    def change_profile_picture(self):
        """
        Allows the user to change their profile picture via a file dialog.
        """
        if not self.current_user:
            QMessageBox.warning(self, "Not Logged In", "Please log in first.")
            return

        file_name = None

        # 1) Attempt Zenity on Linux
        if platform.system() == 'Linux':
            try:
                result = subprocess.run(
                    [
                        'zenity', '--file-selection',
                        '--title=Select Profile Picture',
                        '--file-filter=Images | *.png *.jpg *.jpeg *.svg'
                    ],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    file_name = result.stdout.strip()
            except (FileNotFoundError, subprocess.SubprocessError):
                pass

        if not file_name:
            file_dialog_options = QFileDialog.Options()
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "Select Profile Picture",
                "",
                "Images (*.png *.jpg *.jpeg *.svg)",
                options=file_dialog_options
            )
            if not file_name:
                return  

        if not os.path.exists(file_name):
            QMessageBox.critical(self, "Error", "File does not exist.")
            return
        if os.path.getsize(file_name) > 3 * 1024 * 1024:
            QMessageBox.critical(self, "Error", "File too large (max 3MB).")
            return

        # Check if valid image
        pixmap_test = QPixmap(file_name)
        if pixmap_test.isNull():
            QMessageBox.critical(self, "Error", "Invalid image file.")
            return

        # Actually upload to the Worker route with Bearer token
        cloud_url = self.upload_profile_pic(file_name) 
        if not cloud_url:
            QMessageBox.critical(self, "Error", "Failed to upload image to Cloud.")
            return

        # Update DB record with the new Cloud URL (pass token)
        result = update_profile_pic(
            user_id=self.current_user['id'],
            profile_pic_url=cloud_url,
            bearer_token=self.auth_token
        )
        if not result.get("success"):
            QMessageBox.critical(self, "Error", "Failed to update profile picture: " + result.get("message", ""))
            return

        # Show local preview
        scaled_pix = pixmap_test.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.profile_pic_label.setPixmap(scaled_pix)
        self.update_icons()
        log_action(f"User {self.current_user['email']} uploaded new pic.")



    def change_user_password(self):
        """
        Change the user's password via a form.
        """
        if not self.current_user:
            QMessageBox.warning(self, "Not Logged In", "Please log in first.")
            return

        current_pass = self.current_password_input.text().strip()
        new_pass = self.new_password_input_profile.text().strip()
        confirm_pass = self.confirm_password_input.text().strip()

        if not current_pass or not new_pass or not confirm_pass:
            QMessageBox.warning(self.profile_page, "Empty fields", "Please fill all password fields.")
            return

        if new_pass != confirm_pass:
            QMessageBox.warning(self.profile_page, "Mismatch", "New password and confirm password do not match.")
            return

        result = update_password(
            user_id=self.current_user['id'],
            current_password=current_pass,
            new_password=new_pass,
            bearer_token=self.auth_token  
        )
        if not result.get("success"):
            QMessageBox.critical(self.profile_page, "Error", result.get("message", "Failed to change password."))
            return

        QMessageBox.information(self.profile_page, "Success", "Password changed successfully.")
        self.current_password_input.clear()
        self.new_password_input_profile.clear()
        self.confirm_password_input.clear()



    def logout_user(self):
        """
        Logs the user out: clears the token in the local file + server DB + memory.
        Also updates their time_spent_seconds if needed.
        """
        if self.current_user and self.login_time:
            spent_seconds = (datetime.now() - self.login_time).total_seconds()
            update_time_spent(self.current_user['id'], spent_seconds, bearer_token=self.auth_token)
            clear_auth_token(self.current_user, self.auth_token)

        self.current_user = None
        self.students_data = []
        self.matieres_s1 = []
        self.matieres_s2 = []
        self.login_time = None

        if os.path.exists("remember_user.pkl"):
            os.remove("remember_user.pkl")

        if hasattr(self, 'login_email'):
            self.login_email.clear()
        if hasattr(self, 'login_password'):
            self.login_password.clear()

        self.stack.setCurrentWidget(self.login_page)
        self.apply_translations()



    # -------------------------------------------------------------------------
    #                           THEME / LANGUAGE / ICONS
    # -------------------------------------------------------------------------
    def toggle_theme(self):
        new_theme = 'light' if self.theme == 'dark' else 'dark'
        
        self.animate_theme_change(new_theme)
        self.apply_translations()
        self.update_footer_html()
        self.refresh_stats_chart()  

    def set_theme(self, theme):
        self.theme = theme

        # Read config and update 'theme'
        with open(resource_path('config.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['theme'] = theme
        with open(resource_path('config.json'), 'w') as f:
            json.dump(self.app_config, f)

        self.app_config = data

        # If QSS file exists, load it
        qss_file = resource_path(f"resources/style_{theme}.qss")
        if os.path.exists(qss_file):
            with open(qss_file, 'r') as f:
                qss = f.read()
            QApplication.instance().setStyleSheet(qss)
        else:
            return
        # If AI Advice tab is built, re-style it
        if hasattr(self, 'ai_advice_card'):
            self.refresh_ai_advice_tab_style()

        # If orientation gauges exist, set their theme
        if hasattr(self, 'orientation_gauges'):
            for g in self.orientation_gauges:
                g.setTheme(self.theme)

        # If overview tab has an inline refresh, call it
        if hasattr(self, 'refresh_overview_tab_styles'):
            self.refresh_overview_tab_styles()

        # Update icons, footer, etc.
        self.update_icons()
        self.update_logo()
        self.update_active_icons()
        self.update_footer_html()

        # Force repaint
        self.repaint()



    def update_logo(self):
        if hasattr(self, 'logo_label'):
            if self.theme == 'dark':
                path = resource_path("resources/dark/logo.svg")
            else:
                path = resource_path("resources/light/logo.svg")
            self.logo_label.setPixmap(QPixmap(path).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def update_icons(self):
        icon_size = QSize(40, 40)
        icon_path = "resources/" + self.theme + "/"
        icon_path = resource_path(icon_path)
        if hasattr(self, 'btn_toggle_theme_top'):
            self.btn_toggle_theme_top.setIcon(
                QIcon(icon_path + ("light.svg" if self.theme == 'dark' else "dark.svg"))
            )
            self.btn_toggle_theme_top.setIconSize(QSize(42, 42) if self.theme != 'dark' else QSize(40, 40))

        if hasattr(self, 'btn_home'):
            self.btn_home.setIcon(QIcon(icon_path + "home.svg"))
            self.btn_home.setIconSize(QSize(41, 41) if self.theme == 'dark' else icon_size)
            self.btn_matiere.setIcon(QIcon(icon_path + "matiere.svg"))
            self.btn_matiere.setIconSize(QSize(41, 41) if self.theme == 'dark' else icon_size)
            
            self.btn_stats.setIcon(QIcon(icon_path + "stats.svg"))
            self.btn_stats.setIconSize(QSize(40, 40))
            self.btn_reclam.setIcon(QIcon(icon_path + "reclam.svg"))
            self.btn_reclam.setIconSize(QSize(45, 45) if self.theme == 'light' else QSize(48, 48))
            self.btn_settings.setIcon(QIcon(icon_path + "settings.svg"))
            self.btn_settings.setIconSize(QSize(42, 42) if self.theme == 'light' else icon_size)
            self.btn_notif.setIcon(QIcon(icon_path + "notif.svg"))
            self.btn_notif.setIconSize(icon_size)

            if self.current_user:
                user_data = get_user(self.current_user['id'])
                if user_data and user_data.get("profile_pic_url"):
                    pic_url = user_data.get("profile_pic_url")

                    if pic_url.startswith("http"):
                        loaded_pix = self.load_pixmap_from_url(pic_url)
                        if loaded_pix:
                            pixmap = loaded_pix.scaled(
                                40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                            )
                        else:
                            pixmap = QPixmap(icon_path + "user.svg").scaled(
                                40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                            )
                    else:
                        if os.path.exists(pic_url):
                            pixmap = QPixmap(pic_url).scaled(
                                40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                            )
                        else:
                            pixmap = QPixmap(icon_path + "user.svg").scaled(
                                40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                            )

                    rounded_pixmap = QPixmap(pixmap.size())
                    rounded_pixmap.fill(Qt.transparent)

                    painter = QPainter(rounded_pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, pixmap.width(), pixmap.height())
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.end()

                    self.btn_profile.setIcon(QIcon(rounded_pixmap))
                    self.btn_profile.setIconSize(QSize(40, 40))
                else:
                    self.btn_profile.setIcon(QIcon(icon_path + "user.svg"))
                    self.btn_profile.setIconSize(QSize(40, 40))
            else:
                self.btn_profile.setIcon(QIcon(icon_path + "user.svg"))
            self.btn_profile.setIconSize(icon_size)

            self.btn_logout.setIcon(QIcon(icon_path + "logout.svg"))
            self.btn_logout.setIconSize(icon_size)

        if hasattr(self, 'show_login_pass_btn'):
            if self.show_login_pass_btn.isChecked():
                self.show_login_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.show_login_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        if hasattr(self, 'show_reg_pass_btn'):
            if self.show_reg_pass_btn.isChecked():
                self.show_reg_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.show_reg_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        if hasattr(self, 'show_current_pass_btn'):
            if self.show_current_pass_btn.isChecked():
                self.show_current_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.show_current_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        if hasattr(self, 'show_new_pass_btn'):
            if self.show_new_pass_btn.isChecked():
                self.show_new_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.show_new_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

        if hasattr(self, 'show_confirm_pass_btn'):
            if self.show_confirm_pass_btn.isChecked():
                self.show_confirm_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_open.svg" if self.theme == 'light' else "resources/eye_open_white.svg"))
                )
            else:
                self.show_confirm_pass_btn.setIcon(
                    QIcon(resource_path("resources/eye_closed.svg" if self.theme == 'light' else "resources/eye_closed_white.svg"))
                )

    def update_active_icons(self):
        pass  #can add this 

    def update_footer_html(self):
        """Rebuild the footer HTML whenever needed (theme/language changes)."""
        if hasattr(self, 'status_label'):
            url = "https://rentry.org/wh6d9ewk"
            footer_html = (
                f"{self.tr('system_status')} {self.tr(self.system_status)} | "
                f"{self.tr('made_by')} "
                f'<a href="{url}" style="color: #00bcd4; text-decoration: none;">'
                f'{self.tr("ahmed_saad")}</a>'
            )
            self.status_label.setTextFormat(Qt.RichText)
            self.status_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self.status_label.setOpenExternalLinks(True)
            self.status_label.setText(footer_html)

    # -------------------------------------------------------------------------
    #                           TRANSLATIONS
    # -------------------------------------------------------------------------
    def tr(self, key):
        return self.translations[self.current_language].get(key, key)

    def change_language(self):
        index = self.lang_combo.currentIndex()
        if index == 0:
            self.current_language = 'en'
            self.setLayoutDirection(Qt.LeftToRight)
        elif index == 1:
            self.current_language = 'fr'
            self.setLayoutDirection(Qt.LeftToRight)
        else:
            self.current_language = 'ar'
            self.setLayoutDirection(Qt.RightToLeft)

        self.app_config['language'] = self.current_language
        with open(resource_path('config.json'), 'w', encoding='utf-8') as f:
            json.dump(self.app_config, f)

        
        self.apply_translations()
        self.populate_dashboard_chart()

        # Force a relayout
        self.update_footer_html()
        self.layout().invalidate()
        self.layout().update()
        self.updateGeometry()
        self.repaint()
    def calculate_weighted_average(self, student_dict):
        """
        Calculate the weighted average for a student based on their grades and matiere weights.
        Returns the weighted average as a float, or None if no data is available.
        """
        if not student_dict:
            return None

        total_weighted_sum = 0.0
        total_weight = 0.0

        # Iterate through all matieres (S1 and S2)
        for mat in self.matieres_s1 + self.matieres_s2:
            mat_name = mat['name']
            weight = mat['overall_weight']
            semester = mat['semester']

            # Get the final grade for the matiere
            if semester == 1:
                final_grade = student_dict['grades_s1'].get(mat_name, {}).get('Final')
            else:
                final_grade = student_dict['grades_s2'].get(mat_name, {}).get('Final')

            if final_grade is not None:
                try:
                    final_grade = float(final_grade)
                    total_weighted_sum += final_grade * weight
                    total_weight += weight
                except ValueError:
                    continue

        if total_weight == 0:
            return None

        return round(total_weighted_sum / total_weight, 2)
    
    def apply_translations(self):
        """
        Applies translations to all widgets and labels in the app.
        This includes setting text for buttons, labels, and other UI elements.
        """
        widget_text_map = {
            # --- Login Page ---
            'login_title_label':      "main_title",
            'login_subtitle_label':   "main_subtitle",
            'login_email_label':      "email_label",
            'login_password_label':   "password_label",
            'btn_login':              "login_button",
            'btn_goto_register':      "no_account",
            'btn_forgot':             "forgot_password",
            'btn_not_verified':       "verify_title",  

            # --- Registration Page ---
            'register_title':         "register_title",
            'univ_email_label':       "univ_email",
            'password_label_reg':     "password_label",
            'nid_label':              "nid",
            'btn_register':           "register_button",
            'btn_back_login':         "back_to_login",

            # --- Reset Request Page ---
            'reset_title_label':      "reset_title",
            'btn_send_token':         "send_reset_token",
            'btn_back_to_login_reset':"back_to_login",
            'btn_goto_reset_page':    "already_have_token",

            # --- Actual Reset Page ---
            'reset_page_title':       "reset_page_title",
            'token_label_w':          "token_label",
            'new_password_label_w':   "new_password_label",
            'btn_reset_pass':         "reset_password_button",
            'btn_back_reset':         "back_to_login",

            # --- Reclamation Page ---
            'reclam_label':           "section_title_reclamations",
            'reclamation_type_label': "reclamation_type_label",
            'description_label':      "description_label",
            'btn_submit_reclam':      "submit_reclamation",
            'btn_view_own_reclam':    "view_my_reclamations",

            # --- Settings Page ---
            'settings_label':         "settings_section",
            'settings_font_label':    "font_size",
            'settings_theme_label':   "theme_label",
            'btn_save_settings':      "save_settings",

            # --- Profile Page ---
            'profile_label':          "profile_section",
            'pic_btn':                "change_profile_pic",
            'profile_current_password_label': "current_password_label",
            'profile_new_password_label':     "new_password_label",
            'profile_confirm_password_label': "confirm_new_password_label",
            'btn_change_pass':               "profile_change_password_button",

            # --- Notifications Page ---
            'notif_label':            "notifications",

            # --- Dashboard Calendar ---
            'calendar_title':         "calendar_title",
        }

        for widget_attr, translation_key in widget_text_map.items():
            if hasattr(self, widget_attr):
                widget_obj = getattr(self, widget_attr)
                if widget_obj:
                    widget_obj.setText(self.tr(translation_key))

        if hasattr(self, 'overview_summary_label'):
            rank_GL, total_GL = self.compute_orientation_rank("GL", self.compute_score_gl_for_user(
                self.projected_avg, self.user_moy_math, self.user_moy_info, self.user_sl))
                
            rank_RT, total_RT = self.compute_orientation_rank("RT", self.compute_score_rt_for_user(
                self.projected_avg, self.user_moy_math, self.user_moy_info, self.user_sl))
                
            rank_IIA, total_IIA = self.compute_orientation_rank("IIA", self.compute_score_iia_for_user(
                self.projected_avg, self.user_moy_math, self.user_moy_info, self.user_sl, 
                self.user_en, self.user_circuit))
                
            rank_IMI, total_IMI = self.compute_orientation_rank("IMI", self.projected_avg)

            # Update the summary with new translation
            rank_summary = self.tr("rank_summary").format(
                gl_rank=rank_GL, total_gl=total_GL,
                rt_rank=rank_RT, total_rt=total_RT, 
                iia_rank=rank_IIA, total_iia=total_IIA,
                imi_rank=rank_IMI, total_imi=total_IMI
            )
            
            self.overview_summary_label.setText(rank_summary)
        if hasattr(self, 'reset_email_input'):
            self.reset_email_input.setPlaceholderText(self.tr("enter_email_reset"))


        if hasattr(self, 'welcome_label'):
            if self.current_user and self.current_user['email']:
                raw_name = self.current_user['email'].split('@')[0]
                display_name = raw_name.replace('.', ' ').title()
                self.welcome_label.setText(f"{self.tr('welcome_again')} {display_name}")
            else:
                self.welcome_label.setText(self.tr("welcome"))

        if hasattr(self, 'status_label'):
            url = "https://rentry.org/wh6d9ewk"
            footer_html = (
                f"{self.tr('system_status')} {self.tr(self.system_status)} | "
                f"{self.tr('made_by')} "
                f'<a href="{url}" style="color: #00bcd4; text-decoration: none;">'
                f'{self.tr("ahmed_saad")}</a>'
            )
            self.status_label.setTextFormat(Qt.RichText)
            self.status_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self.status_label.setOpenExternalLinks(True)
            self.status_label.setText(footer_html)

        if (hasattr(self, 'section_label') and hasattr(self, 'moy_section_label') and hasattr(self, 'acceptance_label')):
            current_student = None
            if self.current_user and hasattr(self, 'all_students_data'):
                current_student = next(
                    (s for s in self.all_students_data if s['id'] == self.current_user['national_id']),
                    None
                )

            if current_student and current_student.get('section'):
                section_students = [
                    s for s in self.all_students_data
                    if s.get('section') == current_student['section']
                ]
                section_count = len(section_students)

                avg_section = 0.0
                non_null_students = []

                if current_student['section'].lower() == 'mpi':
                    for st in section_students:
                        weighted_avg = self.calculate_weighted_average(st)
                        if weighted_avg is not None:
                            non_null_students.append(weighted_avg)
                else:
                    for st in section_students:
                        if st.get('moy_an_year1') is not None:
                            non_null_students.append(st['moy_an_year1'])

                if non_null_students:
                    avg_section = sum(non_null_students) / len(non_null_students)

                section_name = current_student['section'].upper()

                self.section_label.setText(
                    self.tr("students_number_section").format(
                        section=section_name,
                        count=f"<b>{section_count} {self.tr('students')}</b>"
                    )
                )

                self.moy_section_label.setText(
                    self.tr("avg_moy_section").format(
                        section=section_name,
                        avg=f"<b>{round(avg_section, 2)}</b>"
                    )
                )

                # ----- RANKING LOGIC -----
                if current_student['section'].lower() == 'mpi':
                    sorted_students = []
                    for st in self.all_students_data:
                        w_avg = self.calculate_weighted_average(st)
                        if w_avg is not None:
                            sorted_students.append((st, w_avg))

                    sorted_students.sort(key=lambda x: x[1], reverse=True)

                    rank_val = None
                    for idx, (st_obj, avg) in enumerate(sorted_students, start=1):
                        if st_obj['id'] == current_student['id']:
                            rank_val = idx
                            break

                    if rank_val:
                        self.acceptance_label.setText(
                            self.tr("purple_ranked_mpi").format(rank=rank_val)
                        )
                    else:
                        self.acceptance_label.setText("No rank found for MPI.")
                else:
                    rank_val = current_student.get('year1_rank')  
                    if rank_val is not None and rank_val > 0:
                        user_avg = current_student.get('moy_an_year1', 0)
                        user_avg = round(user_avg, 2)

                        self.acceptance_label.setText(
                            self.tr("purple_ranked_with_mpi").format(
                                rank=rank_val,
                                grade=user_avg
                            )
                        )
                    else:
                        self.acceptance_label.setText("No rank assigned yet.")
            else:
                self.section_label.setText("No valid section for user.")
                self.moy_section_label.setText("")
                self.acceptance_label.setText("")

        if hasattr(self, 'sy_label'):
            prog_value = year_progress()
            self.sy_label.setText(
                self.tr("year_is_over").format(percent=f"<b>{prog_value}%</b>")
            )

        if hasattr(self, 'notifications_checkbox'):
            self.notifications_checkbox.setText(self.tr("receive_notifications_by_email"))

        if hasattr(self, 'reclamation_type_box'):
            self.reclamation_type_box.clear()  
            self.reclamation_type_box.addItems([
                self.tr("wrong_grade"),
                self.tr("missing_grade"),
                self.tr("other")
            ])

        if hasattr(self, 'update_purple_card_text'):
            self.update_purple_card_text()

        self.layout().invalidate()
        self.layout().update()
        self.updateGeometry()
        self.repaint()


    # -------------------------------------------------------------------------
    #                           ON CLOSE
    # -------------------------------------------------------------------------
    def on_closing(self):
        """
        Called before the main window closes. 
        Updates time spent if user is logged in, and  uploads logs .
        """
        if self.current_user and self.login_time:
            spent_seconds = (datetime.now() - self.login_time).total_seconds()
            update_time_spent(self.current_user['id'], spent_seconds, bearer_token=self.auth_token)




    def closeEvent(self, event):
        self.on_closing()
        self.upload_logs()  
        event.accept()

    # -------------------------------------------------------------------------
    #                           BACKUP (IF NEEDED)
    # -------------------------------------------------------------------------
    """ def backup_data(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.pkl"
        data = {
            'students': self.students_data,
            'matieres_s1': self.matieres_s1,
            'matieres_s2': self.matieres_s2
        }
        try:
            with open(backup_filename, 'wb') as f:
                pickle.dump(data, f)
            log_action(f"Data backed up to {backup_filename}.")
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), f"Failed to backup data: {str(e)}") """


# -------------------------------------------------------------------------
#                              LAUNCH
# -------------------------------------------------------------------------
if __name__ == "__main__":
    
    os.environ.pop('QT_DEVICE_PIXEL_RATIO', None) 
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
