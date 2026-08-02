# DisasterConnect – AI Powered Disaster Response Management System

## 📌 Overview

DisasterConnect is a web-based Disaster Response Management System developed to improve communication and coordination between disaster management coordinators and volunteers during emergencies.

The platform enables coordinators to assign relief tasks, monitor volunteer activities, communicate in real time, and send emergency notifications, while volunteers can register, receive assignments, update task status, and communicate with coordinators efficiently.

---

## ✨ Features

###  Coordinator
- Coordinator Login
- Dashboard
- Report Emergencies
- Assign Tasks to Volunteers
- Send Notifications
- Chat with Multiple Volunteers
- View Volunteer Details

### Volunteer
- Volunteer Registration
- Volunteer Login
- Dashboard
- View Assigned Tasks
- Accept / Reject Tasks
- Update Task Status
  - Assigned
  - Accepted
  - Pending
  - In Progress
  - Completed
  - Rejected
- Receive Notifications
- One-to-One Chat with Coordinator
- Profile Management

### Notification System
- Emergency Alerts
- Task Assignment Notifications
- System Notifications

### 💬 Chat System
- Real-time communication between Coordinator and Volunteers.
- Coordinator can communicate with multiple volunteers.
- Volunteer can communicate with the assigned coordinator.

---

## 🛠️ Technologies Used

### Frontend
- HTML5
- CSS3
- JavaScript
- Font Awesome

### Backend
- Python
- Flask

### Database
- MySQL

### Other Tools
- Git
- GitHub
- VS Code

---

## 📂 Project Structure

```
DisasterConnect/
│
├── static/
│   ├── css/
│   ├── images/
│   └── uploads/
│
├── templates/
│   ├── index.html
│   ├── volunteer_login.html
│   ├── volunteer_registration.html
│   ├── volunteer_dashboard.html
│   ├── task_details.html
│   ├── notifications.html
│   ├── chat.html
│   ├── contact.html
│   └── ...
│
├── app.py
├── requirements.txt
└── README.md
```

---

## Database

The project uses MySQL database with tables including:

- volunteers
- coordinators
- tasks
- notifications
- chat_messages
- emergencies
- contact_messages

---

## 🚀 How to Run

### Clone Repository

```bash
git clone https://github.com/bashita/disasterconnect.git
```

### Move into Project

```bash
cd disasterconnect
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

Windows

```bash
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Database

- Create MySQL Database
- Import SQL Tables
- Update database credentials in `app.py`

### Run Application

```bash
python app.py
```

Open browser:

```
http://127.0.0.1:5000
```

---

## Modules

- Home
- About
- Contact
- Volunteer Registration
- Volunteer Login
- Coordinator Login
- Volunteer Dashboard
- Coordinator Dashboard
- Task Management
- Notifications
- Chat System
- Profile

---

## 🎯 Future Enhancements

- Live GPS tracking
- Google Maps Integration
- SMS & Email Notifications
- Coordinator per city/District
- Mobile Application
- Real-time Analytics Dashboard

---

## 👩‍💻 Developed By

- **Krithiga**
- **Keerthana**
- **Bashita**
- **Lalitha Shree**
