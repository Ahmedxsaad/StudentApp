# Student App - INSAT Companion ✨

[![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-PyQt5-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Status](https://img.shields.io/badge/Status-Prototype-orange.svg)]()
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Repository:** [https://github.com/Ahmedxsaad/StudentApp](https://github.com/Ahmedxsaad/StudentApp)

## Overview

This repository contains my initial attempt at creating a desktop application designed for first and second-year students at INSAT (Institut National des Sciences Appliquées et de Technologie, Tunis).

The goal was to provide a helpful tool for students to:

*   Track their grades across different subjects (`Matières`).
*   Visualize their academic progress and ranking within their section (especially for MPI students considering GL, RT, IIA, IMI orientations).
*   Simulate potential future grades and see their impact on the overall average and orientation eligibility.
*   Manage reclamations regarding grades.
*   Stay updated with notifications and important dates.

This project was a learning experience. While the application **is functional and works as intended when provided with the necessary student data and backend API**, it serves primarily as a **prototype**. **Please note that I (Ahmed Saad) will not be continuing development on this application myself.**

## ✨ Demo & Screenshots

I plan to create a short video demonstration showcasing the application's features. In the meantime, here are some screenshots:

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/139ec936-9791-4ab8-8d47-2cc400076bea" alt="Screenshot 1" width="200"/></td>
    <td><img src="https://github.com/user-attachments/assets/2d75570d-079f-480e-8365-12a533d82365" alt="Screenshot 2" width="200"/></td>
    <td><img src="https://github.com/user-attachments/assets/232cff14-60da-49c0-82f8-b851a9e6496c" alt="Screenshot 3" width="200"/></td>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/a9f43799-0b57-4ad3-aaa9-0abdb1b52372" alt="Screenshot 4" width="200"/></td>
    <td><img src="https://github.com/user-attachments/assets/3a3174a5-fb2e-4d82-857c-744f53395758" alt="Screenshot 5" width="200"/></td>
    <td><img src="https://github.com/user-attachments/assets/aeeedb1f-2fcf-4a40-b0de-fa1dcc8d0ae7" alt="Screenshot 6" width="200"/></td>
  </tr>
   <tr>
    <td><img src="https://github.com/user-attachments/assets/fed6521b-0b60-498f-a87f-e35d844423cb" alt="Screenshot 7" width="200"/></td>
  </tr>
</table>

## Key Features

*   👤 **User Authentication:** Secure Login, Registration, Email Verification, Password Reset.
*   📊 **Dashboard:** At-a-glance overview, academic year progress, important dates calendar, section statistics.
*   📚 **Grades & Matières:** Detailed view of grades (DS, TP, Exam, Final), comparison with section averages, rank per subject.
*   📈 **Statistics & Orientation (MPI Focus):**
    *   Rank progression visualization.
    *   Comparative charts (Line/Spider) against historical averages (2022, 2023) for GL, RT, IIA, IMI criteria.
    *   Orientation probability gauges.
    *   Textual summary of ranking based on different orientation formulas.
*   🔮 **Simulation Tool:** Input hypothetical grades for upcoming exams to predict the final overall average (`Moyenne Générale`) and check potential orientation eligibility.
*   🤖 **AI-Powered Advice (Admin):** Feature for administrators to generate personalized orientation reports for MPI students using a local LLM (Llama-3.1-8B). This is part of the separate `admin_app.py`.
*   📝 **Reclamations:** Submit and view the status of grade-related inquiries.
*   ⚙️ **Settings:** Customize the application theme (Dark/Light), font size, and language (English, French, Arabic). Opt-in/out of email notifications.
*   🖼️ **Profile Management:** View user information, change password, upload/change profile picture (hosted on Cloudinary).
*   🔔 **Notifications:** In-app notification system for announcements or updates.
*   🌐 **Connectivity Awareness:** Checks for internet connection and adapts functionality.

## Technology Stack

*   🐍 **Frontend/Core Logic:** Python 3.x
*   🎨 **GUI:** PyQt5
*   📊 **Charting:** PyQtChart
*   🌐 **API Communication:** Requests library
*   🧠 **AI Reports (Admin):** `llama-cpp-python` (for local model inference)
*   ⚙️ **Configuration:** JSON
*   💾 **Local Storage:** Pickle (for 'Remember Me' token)
*   ☁️ **Backend (Separate Repo):**
    *   **API:** Cloudflare Workers
    *   **Database:** PostgreSQL (hosted on Neon DB)
    *   **File Storage:** Cloudinary (for profile pictures, logs)

*(Note: The backend API implementation details are in a separate repository, link to be provided soon.)*

## ⚠️ Important Considerations & Warnings ⚠️

This project is provided "as-is". While the core features are functional given the correct data and backend setup, **distributing or deploying this application in its current state is not recommended** without addressing the following:

1.  **Development Status:** This is a **prototype/first attempt**. It demonstrates various features but requires significant refinement before production use.
2.  **Refactoring & Backend Migration:**
    *   Some **code refactoring** is needed for better maintainability, scalability, and robustness.
    *   Crucially, **complex logic currently resides in the frontend** (e.g., calculations for statistics, ranking, simulation results in `main_app.py`). For a production application, **this logic must be moved to the backend API**. This is essential for:
        *   **Security:** Protecting sensitive calculation methods and data integrity.
        *   **Performance:** Offloading heavy computations from the client application.
        *   **Maintainability:** Centralizing business logic.
3.  **Backend & Hosting:**
    *   The application **requires a separate backend API** (built with Cloudflare Workers, Neon DB for PostgreSQL, and Cloudinary for file storage; repo link to be provided) to function fully (authentication, data storage, etc.).
    *   Implementing and hosting a **secure and scalable backend** for an application handling sensitive student data and complex queries (PostgreSQL) is challenging.
    *   While free tiers (like Cloudflare Workers, Neon DB, Cloudinary) are useful for development, ensuring robustness, security, and adequate performance (especially with a relational database like PostgreSQL) **likely requires paid hosting solutions** for a production environment. Free tiers may have limitations or may not be sufficient/reliable for many users and significant data processing.

## Getting Started (Development/Testing)

These steps are for setting up a local development environment. **Remember the backend requirements mentioned above.**

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Ahmedxsaad/StudentApp.git
    cd StudentApp
    ```
2.  **Set up a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    # Note: A requirements.txt file needs to be generated first.
    pip install -r requirements.txt
    # Note: You might need to install llama-cpp-python separately depending on your system setup (CPU/GPU) if using the admin app.
    ```
4.  **Set up and Deploy Backend:** Clone, configure, and deploy the separate backend repository (using Cloudflare Workers, Neon DB, and Cloudinary). Update `config.json` or relevant parts of the frontend code (`src/api_client.py`) to point to your deployed backend API endpoints and Cloudinary credentials. *(Backend repository link will be added here soon)*.
5.  **Run the Application:**
    *   Main App: `python src/main_app.py`
    *   Admin App (Optional): `python src/admin_app.py`

## Future Development / Contributing

If you are interested in taking this project further, I commend your enthusiasm! However, please prioritize the **refactoring and backend migration** mentioned in the warnings before considering distribution.

I might be able to offer some guidance or answer specific questions about the existing code's intent if you get stuck. Feel free to reach out via GitHub Issues or Discussions.

## 📧 Contact

*   **Author:** Ahmed Saad ([@Ahmedxsaad](https://github.com/Ahmedxsaad))

## 📄 License

This project is licensed under the **Apache License 2.0**.

You are free to:

*   Use the software for any purpose.
*   Modify the software.
*   Distribute the software or copies of it.
*   Sublicense the software.

You must:

*   **Include the original copyright notice and the license itself.**
*   **State any significant changes you made to the software.**
*   **Provide attribution to the original author (Ahmed Saad) if you distribute the software or derivative works.**
