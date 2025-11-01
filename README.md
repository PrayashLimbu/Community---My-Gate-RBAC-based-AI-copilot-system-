# Community Management App (MyGate-Style)

This project is a full-stack community management application, built as part of the Deep Learning Titans assignment. It features a React frontend, a Django (Python) backend, and a GCP Gemini-powered AI Copilot for performing actions via chat.

* **Demo Video:** Xyz`

---

## 1. 🚀 90-Second Architecture

This project is built on a modern, decoupled stack:

* **Frontend:** A **React** single-page application (built with Vite) that provides a dynamic UI for the three user roles. It uses `axios` for API calls and `react-router-dom` for navigation.
* **Backend:** A **Django** server (built with Python) using **Docker**. It exposes a secure, role-based RESTful API using Django REST Framework.
* **Database:** A **PostgreSQL** database (managed by Docker) to store all users, visitors, and audit events.
* **AI Copilot:** Uses **Google Cloud's Gemini API** (via Vertex AI) for natural language understanding and function calling.
* **Real-Time:** Uses **3-second polling** on the frontend to simulate real-time updates for the Guard and Admin dashboards.

### Deviation from Reference Architecture

[cite_start]This project fulfills all functional requirements of the assignment [cite: 2, 3] [cite_start]but deviates from the *suggested* (non-mandatory) reference stack [cite: 30] in the following ways:
* **Backend/DB:** Instead of Firebase Auth and Firestore, we implemented a more traditional and powerful backend using **Django, PostgreSQL, and JWTs**.
* **RBAC:** Instead of Firebase Custom Claims, we implemented Role-Based Access Control (RBAC) on the server using Django REST Framework's custom permission classes, which check the user's `role` field stored in our database.
* **AI:** Instead of OpenAI, we used **GCP Gemini**, as it supports the required function-calling feature and API keys were available.

---

## 2. ⚙️ Setup & Installation

The project is split into two main folders: `Community` (backend) and `community_app_frontend` (frontend).

### Backend (`Community/`)

1.  **Add Keys:**
    * Place your GCP service account key for Gemini in the root folder and name it `gen-lang-client-0431862828-44d56cb2ee6f.json`.
    * Place your Firebase service account key (for notifications) in the root folder and name it `firebase-key.json`.
2.  **Build & Run:**
    ```bash
    # Build and start the containers (db and web)
    docker-compose up --build
    ```
3.  **Create Admin User:**
    ```bash
    # In a new terminal, run:
    docker-compose run --rm web python manage.py createsuperuser
    ```
4.  **Run Seed Script:**
    ```bash
    # This creates the Guard, Resident, and a pending visitor
    docker-compose run --rm web python manage.py create_test_users
    ```
The backend is now running on `http://localhost:8000`.

### Frontend (`community_app_frontend/`)

1.  **Install Dependencies:**
    ```bash
    cd ../community_app_frontend
    npm install
    ```
2.  **Add Keys:**
    * Add your Firebase **Web App Config** to `src/firebase-config.js` and `public/firebase-messaging-sw.js`.
    * Add your Firebase **VAPID Key** to `src/services/fcmService.js`.
3.  **Run with HTTPS (Required for Notifications):**
    * Install the SSL plugin: `npm install @vitejs/plugin-basic-ssl`
    * Configure `vite.config.js` to use `https` (as per our previous steps).
    * Start the server:
        ```bash
        npm run dev
        ```
The frontend is now running on `https://localhost:5173`.

---

## 3. 🛡️ RBAC Policy (Who Can Do What)

Permissions are enforced on the Django backend using custom `IsAdmin`, `IsGuard`, and `IsResident` permission classes.

* **Resident:**
    * Can create visitors (for their own household).
    * Can view, approve, and deny visitors for their household.
    * Can use the AI Copilot to perform these actions.
* **Guard:**
    * Can view *all* visitors from *all* households.
    * Can check-in (if `APPROVED`) and check-out (if `CHECKED_IN`) any visitor.
    * Can view the "Daily Log" of completed actions.
    * *Cannot* create, approve, or deny visitors.
* **Admin:**
    * Has **full access**.
    * Can do everything a Guard can do.
    * Can view and manage all users (change roles, etc.).
    * Can view the full, immutable `Event` audit log.

---

## 4. 🤖 AI Copilot Tools

The AI Copilot uses GCP Gemini's function calling feature. The backend provides the following tools:

* `create_visitor(name, purpose, time_details)`: Creates a new `PENDING` visitor.
* `approve_visitor(visitor_id)`: Approves a `PENDING` visitor.
* `deny_visitor(visitor_id, reason)`: Denies a `PENDING` visitor.
* `checkin_visitor(visitor_id)`: Checks in an `APPROVED` visitor.
* `list_my_visitors()`: Lists all visitors for the resident's household.

---

## 5. ⚠️ Known Issues & Deviations

* **FCM Notifications (Blocked):** The entire backend and frontend logic for FCM is **100% complete**. However, the feature is non-functional due to a persistent **Google Cloud `404` error** (`The requested URL /code/batch/code was not found on this server`). This indicates a project provisioning bug on Google's side that persisted despite enabling all required APIs (`FCM`, `Pub/Sub`) and permissions (`FCM Admin`).
* [cite_start]**FCM Workaround:** To meet the "real-time" requirement [cite: 3] for the demo, the Guard and Admin dashboards **poll the server every 3 seconds** to fetch new data, simulating an instant update.
* **AI Provider:** As noted, **GCP Gemini** was used instead of OpenAI to fulfill the function-calling requirement.

---

## 6. 💸 Basic Cost Note

* **Backend (Django):** Can be deployed to **Azure Container Apps** or **Azure App Service**, both of which have free/low-cost tiers that scale with usage.
* **Database (PostgreSQL):** Can be deployed using **Azure Database for PostgreSQL**, which has flexible pricing tiers.
* **Frontend (React):** Can be deployed to **Azure Static Web Apps**, which has a generous free tier for static files and bandwidth.
* **AI (GCP Gemini):** This is the main variable cost. It's billed per-token by Google Cloud. The 3-second polling on the Resident dashboard (to check for notification simulation) also generates minor API traffic.
